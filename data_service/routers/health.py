"""健康检查路由"""

import time
from pathlib import Path

from fastapi import APIRouter

from data_service import __version__
from data_service.db import check_health

router = APIRouter(tags=["健康检查"])


def _read_version() -> str:
    try:
        vf = Path(__file__).parent.parent.parent / "VERSION"
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return __version__


@router.get("/health")
async def health():
    """服务健康检查"""
    db_health = await check_health()
    return {
        "success": True,
        "data": {
            "status": "ok",
            "version": _read_version(),
            "timestamp": int(time.time()),
            "service": "TradingAgents-CN DataService",
            "databases": db_health,
        },
        "message": "服务运行正常",
    }


@router.get("/healthz")
async def healthz():
    """Kubernetes liveness probe"""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Kubernetes readiness probe"""
    return {"ready": True}
