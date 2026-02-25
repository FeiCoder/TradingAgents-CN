"""
TradingAgents-CN 数据管理服务
独立 FastAPI 应用程序入口

启动方式:
    uvicorn data_service.main:app --host 0.0.0.0 --port 8001
    python -m data_service.main
"""

import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from data_service import __version__
from data_service.config import settings
from data_service.db import init_mongodb, init_redis, close_connections
from data_service.routers import health, auth, stocks, market, cache, technical

# ── 日志配置 ──────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── 生命周期管理 ──────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭生命周期钩子"""
    logger.info("=" * 60)
    logger.info(f"🚀 TradingAgents-CN DataService v{__version__} 启动中")
    logger.info(f"   Host      : {settings.MONGODB_HOST} / {settings.REDIS_HOST}")
    logger.info(f"   MongoDB   : {settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
    logger.info(f"   Redis     : {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    logger.info("=" * 60)

    # 初始化数据库连接（失败不阻断启动，降级运行）
    mongo_ok = await init_mongodb()
    redis_ok = await init_redis()

    if mongo_ok and redis_ok:
        logger.info("✅ 所有数据库连接就绪")
    elif mongo_ok:
        logger.warning("⚠️ Redis 不可用，缓存降级为 MongoDB + 文件模式")
    elif redis_ok:
        logger.warning("⚠️ MongoDB 不可用，降级为 Redis + 文件模式")
    else:
        logger.warning("⚠️ 数据库均不可用，降级为文件缓存模式")

    yield

    logger.info("🔄 数据管理服务正在关闭...")
    await close_connections()
    logger.info("✅ 数据管理服务已关闭")


# ── 应用实例 ──────────────────────────────────────────────
app = FastAPI(
    title="TradingAgents-CN 数据管理服务",
    description=(
        "独立的股票数据管理微服务，提供以下功能：\n"
        "- 📊 股票数据管理（A股 / 港股 / 美股）\n"
        "- 🔐 用户认证（JWT）\n"
        "- 🌐 多市场数据提供商（AKShare / Tushare / BaoStock / yfinance）\n"
        "- 🗄️ 多级缓存（Redis → MongoDB → 文件）\n"
        "- 📈 技术指标分析（MA / MACD / RSI / BOLL / KDJ / ATR）\n\n"
        "**分层架构**\n"
        "```\n"
        "Acquisition Layer  ← 从数据提供商拉取原始数据\n"
        "Cache Layer        ← Redis / MongoDB / 文件三级缓存\n"
        "Processing Layer   ← 数据清洗、格式化、标准化\n"
        "Analysis Layer     ← 技术指标计算\n"
        "```"
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS 中间件 ───────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求计时中间件 ─────────────────────────────────────────
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{(time.time() - start) * 1000:.1f}ms"
    return response


# ── 全局异常处理 ──────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "内部服务错误", "message": str(exc)},
    )


# ── 注册路由 ──────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(stocks.router)
app.include_router(market.router)
app.include_router(cache.router)
app.include_router(technical.router)


# ── 根路由 ───────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "TradingAgents-CN DataService",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


# ── 直接运行入口 ──────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "data_service.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
