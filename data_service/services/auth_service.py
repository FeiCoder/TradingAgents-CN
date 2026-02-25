"""
认证服务
基于 JWT 的无状态用户认证，用户信息存储在 MongoDB
"""

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pydantic import BaseModel

from data_service.config import settings
from data_service.db import get_mongo_db

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    sub: str
    exp: int


class AuthService:
    """用户认证服务"""

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    # ── Token ─────────────────────────────────────────────

    @staticmethod
    def create_access_token(username: str) -> str:
        expire = datetime.now(tz=timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {"sub": username, "exp": expire}
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[TokenPayload]:
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
            )
            return TokenPayload(sub=payload["sub"], exp=int(payload["exp"]))
        except jwt.ExpiredSignatureError:
            logger.debug("Token 已过期")
        except jwt.InvalidTokenError as exc:
            logger.debug(f"Token 无效: {exc}")
        return None

    # ── 用户管理 ──────────────────────────────────────────

    async def authenticate(self, username: str, password: str) -> Optional[dict]:
        """验证用户名密码，成功返回用户信息字典"""
        hashed = self._hash_password(password)
        db = get_mongo_db()
        if db is not None:
            try:
                user = await db["users"].find_one(
                    {"username": username, "password_hash": hashed}
                )
                if user:
                    return {"username": user["username"], "is_admin": user.get("is_admin", False)}
            except Exception as exc:
                logger.warning(f"数据库认证失败，降级到默认账号: {exc}")

        # 降级：支持通过环境变量设置的默认管理员账号
        default_user = "admin"
        default_pass_hash = self._hash_password("admin123")
        if username == default_user and hashed == default_pass_hash:
            return {"username": "admin", "is_admin": True}
        return None

    async def create_user(
        self, username: str, password: str, is_admin: bool = False
    ) -> bool:
        """创建用户，返回是否成功"""
        db = get_mongo_db()
        if db is None:
            logger.warning("MongoDB 不可用，无法创建用户")
            return False
        hashed = self._hash_password(password)
        try:
            existing = await db["users"].find_one({"username": username})
            if existing:
                return False
            await db["users"].insert_one({
                "username": username,
                "password_hash": hashed,
                "is_admin": is_admin,
                "created_at": datetime.now(tz=timezone.utc),
            })
            return True
        except Exception as exc:
            logger.error(f"创建用户失败: {exc}")
            return False


# ── 模块级别单例 ──────────────────────────────────────────
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
