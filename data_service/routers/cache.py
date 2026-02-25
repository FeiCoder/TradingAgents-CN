"""
缓存管理路由
GET  /api/cache/stats     - 缓存统计
POST /api/cache/clear     - 清理缓存
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from data_service.models.response import ApiResponse
from data_service.routers.auth import get_current_user
from data_service.layers.cache import get_cache_layer

router = APIRouter(prefix="/api/cache", tags=["缓存管理"])


class ClearRequest(BaseModel):
    namespace: str
    key_parts: Optional[list] = None


@router.get("/stats", response_model=ApiResponse)
async def cache_stats(current_user: dict = Depends(get_current_user)):
    """获取缓存统计信息（各后端键数量）"""
    stats = await get_cache_layer().stats()
    return ApiResponse.ok(data=stats)


@router.post("/clear", response_model=ApiResponse)
async def clear_cache(body: ClearRequest, current_user: dict = Depends(get_current_user)):
    """清理指定命名空间的缓存条目"""
    parts = body.key_parts or []
    await get_cache_layer().delete(body.namespace, *parts)
    return ApiResponse.ok(message=f"缓存已清理: {body.namespace}:{':'.join(parts)}")
