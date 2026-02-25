"""
技术分析路由
GET /api/technical/{symbol}  - 获取技术指标
"""

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_service.models.response import ApiResponse
from data_service.routers.auth import get_current_user
from data_service.services.technical_service import get_technical_service

router = APIRouter(prefix="/api/technical", tags=["技术分析"])

_SUPPORTED = ["ma", "ema", "macd", "rsi", "boll", "kdj", "atr"]


@router.get("/{symbol}", response_model=ApiResponse)
async def get_technical_indicators(
    symbol: str,
    market: str = Query(default="CN"),
    start_date: Optional[str] = Query(
        default=None, description="开始日期 YYYY-MM-DD，默认 90 天前"
    ),
    end_date: Optional[str] = Query(
        default=None, description="结束日期 YYYY-MM-DD，默认今天"
    ),
    indicators: Optional[str] = Query(
        default=None,
        description=f"逗号分隔的指标列表，支持: {', '.join(_SUPPORTED)}，不填则计算全部",
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    获取股票技术分析指标

    - `indicators` 示例: `ma,macd,rsi`
    """
    start = start_date or (date.today() - timedelta(days=90)).isoformat()
    end = end_date or date.today().isoformat()

    indicator_list: Optional[List[str]] = None
    if indicators:
        indicator_list = [i.strip().lower() for i in indicators.split(",") if i.strip()]
        unknown = [i for i in indicator_list if i not in _SUPPORTED]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的指标: {unknown}，支持的指标: {_SUPPORTED}",
            )

    svc = get_technical_service()
    try:
        result = await svc.get_indicators(
            symbol=symbol,
            start_date=start,
            end_date=end,
            market=market,
            indicators=indicator_list,
        )
        return ApiResponse.ok(data=result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
