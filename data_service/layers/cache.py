"""
Layer 2 – 缓存层
优先级：Redis（内存） → MongoDB（持久化） → 文件（本地）
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from data_service.config import settings
from data_service.db import get_redis, get_mongo_db

logger = logging.getLogger(__name__)

_CACHE_DIR = settings.CACHE_DIR


def _make_key(namespace: str, *parts: str) -> str:
    """生成规范化缓存键"""
    raw = ":".join([namespace] + list(parts))
    if len(raw) > 200:
        raw = namespace + ":" + hashlib.md5(raw.encode()).hexdigest()
    return raw


def _file_path(key: str) -> str:
    safe = key.replace(":", "_").replace("/", "_")
    return os.path.join(_CACHE_DIR, f"{safe}.json")


class CacheLayer:
    """多级缓存层，自动根据可用连接选择后端"""

    async def get(self, namespace: str, *parts: str) -> Optional[Any]:
        key = _make_key(namespace, *parts)

        # L1: Redis
        redis = get_redis()
        if redis:
            try:
                raw = await redis.get(key)
                if raw:
                    logger.debug(f"缓存命中（Redis）: {key}")
                    return json.loads(raw)
            except Exception as exc:
                logger.debug(f"Redis 读取失败: {exc}")

        # L2: MongoDB
        db = get_mongo_db()
        if db:
            try:
                doc = await db["data_cache"].find_one({"key": key})
                if doc:
                    expires_at = doc.get("expires_at")
                    if expires_at and expires_at < datetime.now(tz=timezone.utc):
                        await db["data_cache"].delete_one({"key": key})
                    else:
                        logger.debug(f"缓存命中（MongoDB）: {key}")
                        return doc.get("value")
            except Exception as exc:
                logger.debug(f"MongoDB 读取失败: {exc}")

        # L3: 文件
        path = _file_path(key)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    doc = json.load(fh)
                expires_at = doc.get("expires_at")
                if expires_at and expires_at < datetime.now(tz=timezone.utc).timestamp():
                    os.remove(path)
                else:
                    logger.debug(f"缓存命中（文件）: {key}")
                    return doc.get("value")
            except Exception as exc:
                logger.debug(f"文件缓存读取失败: {exc}")

        return None

    async def set(
        self,
        value: Any,
        namespace: str,
        *parts: str,
        ttl: int = None,
    ) -> None:
        if ttl is None:
            ttl = settings.CACHE_TTL
        key = _make_key(namespace, *parts)
        serialized = json.dumps(value, ensure_ascii=False, default=str)

        # L1: Redis
        redis = get_redis()
        if redis:
            try:
                await redis.setex(key, ttl, serialized)
                logger.debug(f"缓存写入（Redis）: {key}")
                return
            except Exception as exc:
                logger.debug(f"Redis 写入失败: {exc}")

        # L2: MongoDB
        db = get_mongo_db()
        if db:
            try:
                from datetime import timedelta
                expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)
                await db["data_cache"].update_one(
                    {"key": key},
                    {"$set": {"key": key, "value": value, "expires_at": expires_at}},
                    upsert=True,
                )
                logger.debug(f"缓存写入（MongoDB）: {key}")
                return
            except Exception as exc:
                logger.debug(f"MongoDB 写入失败: {exc}")

        # L3: 文件
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            from datetime import timedelta
            expires_ts = (datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)).timestamp()
            path = _file_path(key)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"value": value, "expires_at": expires_ts}, fh, ensure_ascii=False, default=str)
            logger.debug(f"缓存写入（文件）: {key}")
        except Exception as exc:
            logger.debug(f"文件缓存写入失败: {exc}")

    async def delete(self, namespace: str, *parts: str) -> None:
        key = _make_key(namespace, *parts)
        redis = get_redis()
        if redis:
            try:
                await redis.delete(key)
            except Exception:
                pass
        db = get_mongo_db()
        if db:
            try:
                await db["data_cache"].delete_one({"key": key})
            except Exception:
                pass
        path = _file_path(key)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    async def stats(self) -> dict:
        """返回各缓存后端统计信息"""
        result: dict = {}
        redis = get_redis()
        if redis:
            try:
                result["redis"] = {"keys": await redis.dbsize(), "status": "healthy"}
            except Exception as exc:
                result["redis"] = {"status": "error", "error": str(exc)}
        else:
            result["redis"] = {"status": "disabled"}

        db = get_mongo_db()
        if db:
            try:
                count = await db["data_cache"].count_documents({})
                result["mongodb"] = {"documents": count, "status": "healthy"}
            except Exception as exc:
                result["mongodb"] = {"status": "error", "error": str(exc)}
        else:
            result["mongodb"] = {"status": "disabled"}

        try:
            file_count = len([
                f for f in os.listdir(_CACHE_DIR) if f.endswith(".json")
            ]) if os.path.exists(_CACHE_DIR) else 0
            result["file"] = {"files": file_count, "dir": _CACHE_DIR, "status": "healthy"}
        except Exception as exc:
            result["file"] = {"status": "error", "error": str(exc)}

        return result


# ── 模块级别单例 ──────────────────────────────────────────
_cache: Optional[CacheLayer] = None


def get_cache_layer() -> CacheLayer:
    global _cache
    if _cache is None:
        _cache = CacheLayer()
    return _cache
