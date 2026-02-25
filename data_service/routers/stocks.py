"""
股票数据路由
GET /api/stocks/list               - 获取股票列表
GET /api/stocks/search             - 搜索股票
GET /api/stocks/{symbol}/history   - 获取历史 K 线
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data_service.models.response import ApiResponse
from data_service.routers.auth import get_current_user
from data_service.services.stock_service import get_stock_service

router = APIRouter(prefix="/api/stocks", tags=["股票数据"])

_DEFAULT_DAYS = 30


def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


@router.get("/list", response_model=ApiResponse)
async def list_stocks(
    market: str = Query(default="CN", description="市场代码: CN / HK / US"),
    force_refresh: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
):
    """获取股票列表"""
    svc = get_stock_service()
    try:
        stocks = await svc.get_stock_list(market=market, force_refresh=force_refresh)
        return ApiResponse.ok(
            data={"market": market, "count": len(stocks), "stocks": stocks},
            message=f"获取 {market} 市场股票列表成功",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get("/search", response_model=ApiResponse)
async def search_stocks(
    keyword: str = Query(..., description="搜索关键词（股票代码或名称）"),
    market: str = Query(default="CN"),
    current_user: dict = Depends(get_current_user),
):
    """根据关键词搜索股票"""
    svc = get_stock_service()
    results = await svc.search_stocks(keyword=keyword, market=market)
    return ApiResponse.ok(
        data={"keyword": keyword, "count": len(results), "stocks": results},
    )


@router.get("/{symbol}/history", response_model=ApiResponse)
async def get_stock_history(
    symbol: str,
    market: str = Query(default="CN"),
    start_date: Optional[str] = Query(
        default=None, description="开始日期 YYYY-MM-DD，默认 30 天前"
    ),
    end_date: Optional[str] = Query(
        default=None, description="结束日期 YYYY-MM-DD，默认今天"
    ),
    force_refresh: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
):
    """获取股票历史 K 线数据"""
    start = start_date or _days_ago(_DEFAULT_DAYS)
    end = end_date or _today()
    svc = get_stock_service()
    try:
        records = await svc.get_stock_history(
            symbol=symbol,
            start_date=start,
            end_date=end,
            market=market,
            force_refresh=force_refresh,
        )
        return ApiResponse.ok(
            data={
                "symbol": symbol,
                "market": market,
                "start_date": start,
                "end_date": end,
                "count": len(records),
                "data": records,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
