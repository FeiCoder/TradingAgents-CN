"""
数据管理服务配置模块
支持从环境变量读取配置，自动检测 Docker 容器环境并启用服务发现
"""

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_docker() -> bool:
    """检测当前是否运行在 Docker 容器内"""
    return (
        os.path.exists("/.dockerenv")
        or os.environ.get("DOCKER_CONTAINER", "").lower() in ("1", "true", "yes")
    )


def _default_mongo_host() -> str:
    """Docker 环境使用服务名 'mongodb'，本地使用 'localhost'"""
    return "mongodb" if _is_docker() else "localhost"


def _default_redis_host() -> str:
    """Docker 环境使用服务名 'redis'，本地使用 'localhost'"""
    return "redis" if _is_docker() else "localhost"


class DataServiceSettings(BaseSettings):
    """数据管理服务配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 基础配置 ──────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8001)
    DEBUG: bool = Field(default=False)
    ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: ["*"]
    )

    # ── MongoDB 配置（支持服务发现） ───────────────────────
    MONGODB_HOST: str = Field(default_factory=_default_mongo_host)
    MONGODB_PORT: int = Field(default=27017)
    MONGODB_USERNAME: str = Field(default="")
    MONGODB_PASSWORD: str = Field(default="")
    MONGODB_DATABASE: str = Field(default="tradingagents")
    MONGODB_AUTH_SOURCE: str = Field(default="admin")
    MONGODB_ENABLED: bool = Field(default=True)
    MONGO_MAX_CONNECTIONS: int = Field(default=50)
    MONGO_MIN_CONNECTIONS: int = Field(default=5)
    MONGO_CONNECT_TIMEOUT_MS: int = Field(default=30000)
    MONGO_SOCKET_TIMEOUT_MS: int = Field(default=60000)
    MONGO_SERVER_SELECTION_TIMEOUT_MS: int = Field(default=5000)

    @property
    def MONGO_URI(self) -> str:
        if self.MONGODB_USERNAME and self.MONGODB_PASSWORD:
            return (
                f"mongodb://{self.MONGODB_USERNAME}:{self.MONGODB_PASSWORD}"
                f"@{self.MONGODB_HOST}:{self.MONGODB_PORT}"
                f"/{self.MONGODB_DATABASE}?authSource={self.MONGODB_AUTH_SOURCE}"
            )
        return f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}/{self.MONGODB_DATABASE}"

    # ── Redis 配置（支持服务发现） ─────────────────────────
    REDIS_HOST: str = Field(default_factory=_default_redis_host)
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default="")
    REDIS_DB: int = Field(default=0)
    REDIS_ENABLED: bool = Field(default=True)
    REDIS_MAX_CONNECTIONS: int = Field(default=20)

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── JWT / 认证配置 ─────────────────────────────────────
    JWT_SECRET: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # ── 数据源配置 ─────────────────────────────────────────
    DEFAULT_CHINA_DATA_SOURCE: str = Field(default="akshare")
    TUSHARE_TOKEN: str = Field(default="")
    TUSHARE_ENABLED: bool = Field(default=False)
    FINNHUB_API_KEY: str = Field(default="")

    # ── 缓存配置 ──────────────────────────────────────────
    CACHE_TTL: int = Field(default=3600)           # 通用缓存 TTL（秒）
    STOCK_DATA_CACHE_TTL: int = Field(default=7200)  # 股票数据 TTL
    NEWS_CACHE_TTL: int = Field(default=14400)       # 新闻缓存 TTL
    CACHE_DIR: str = Field(default="./cache")        # 文件缓存目录

    # ── 日志配置 ──────────────────────────────────────────
    LOG_LEVEL: str = Field(default="INFO")
    TZ: str = Field(default="Asia/Shanghai")


@lru_cache
def get_settings() -> DataServiceSettings:
    """获取全局配置（单例）"""
    return DataServiceSettings()


settings = get_settings()
