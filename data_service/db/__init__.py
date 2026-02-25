"""
数据库连接管理模块
统一管理 MongoDB（异步）和 Redis（异步）连接
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from redis.asyncio import Redis, ConnectionPool

from data_service.config import settings

logger = logging.getLogger(__name__)

# ── 全局连接实例 ─────────────────────────────────────────
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None
_redis_client: Optional[Redis] = None
_redis_pool: Optional[ConnectionPool] = None


async def init_mongodb() -> bool:
    """初始化 MongoDB 异步连接，返回是否成功"""
    global _mongo_client, _mongo_db
    if not settings.MONGODB_ENABLED:
        logger.info("MongoDB 未启用，跳过初始化")
        return False
    try:
        _mongo_client = AsyncIOMotorClient(
            settings.MONGO_URI,
            maxPoolSize=settings.MONGO_MAX_CONNECTIONS,
            minPoolSize=settings.MONGO_MIN_CONNECTIONS,
            serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=settings.MONGO_CONNECT_TIMEOUT_MS,
            socketTimeoutMS=settings.MONGO_SOCKET_TIMEOUT_MS,
        )
        _mongo_db = _mongo_client[settings.MONGODB_DATABASE]
        await _mongo_client.admin.command("ping")
        logger.info(f"✅ MongoDB 连接成功: {settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        return True
    except Exception as exc:
        logger.warning(f"⚠️ MongoDB 连接失败（服务将继续以降级模式运行）: {exc}")
        _mongo_client = None
        _mongo_db = None
        return False


async def init_redis() -> bool:
    """初始化 Redis 异步连接，返回是否成功"""
    global _redis_client, _redis_pool
    if not settings.REDIS_ENABLED:
        logger.info("Redis 未启用，跳过初始化")
        return False
    try:
        _redis_pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        _redis_client = Redis(connection_pool=_redis_pool)
        await _redis_client.ping()
        logger.info(f"✅ Redis 连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        return True
    except Exception as exc:
        logger.warning(f"⚠️ Redis 连接失败（服务将继续以降级模式运行）: {exc}")
        _redis_client = None
        _redis_pool = None
        return False


async def close_connections():
    """关闭所有数据库连接"""
    global _mongo_client, _mongo_db, _redis_client, _redis_pool
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB 连接已关闭")
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
    if _redis_pool:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis 连接已关闭")


def get_mongo_db() -> Optional[AsyncIOMotorDatabase]:
    """获取 MongoDB 数据库实例（可能为 None）"""
    return _mongo_db


def get_redis() -> Optional[Redis]:
    """获取 Redis 客户端（可能为 None）"""
    return _redis_client


async def check_health() -> dict:
    """检查所有数据库连接健康状态"""
    result = {
        "mongodb": {"status": "disabled"},
        "redis": {"status": "disabled"},
    }
    if _mongo_client:
        try:
            await _mongo_client.admin.command("ping")
            result["mongodb"] = {"status": "healthy", "host": settings.MONGODB_HOST}
        except Exception as exc:
            result["mongodb"] = {"status": "unhealthy", "error": str(exc)}
    elif settings.MONGODB_ENABLED:
        result["mongodb"] = {"status": "disconnected"}

    if _redis_client:
        try:
            await _redis_client.ping()
            result["redis"] = {"status": "healthy", "host": settings.REDIS_HOST}
        except Exception as exc:
            result["redis"] = {"status": "unhealthy", "error": str(exc)}
    elif settings.REDIS_ENABLED:
        result["redis"] = {"status": "disconnected"}

    return result
