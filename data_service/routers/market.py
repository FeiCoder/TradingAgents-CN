"""
多市场数据路由
GET /api/markets          - 支持的市场列表
GET /api/markets/{market}/providers  - 各市场可用数据提供商
"""

from fastapi import APIRouter, Depends

from data_service.models.response import ApiResponse
from data_service.routers.auth import get_current_user
from data_service.config import settings

router = APIRouter(prefix="/api/markets", tags=["多市场数据"])

_MARKETS = [
    {
        "code": "CN",
        "name": "A股",
        "name_en": "China A-Shares",
        "currency": "CNY",
        "timezone": "Asia/Shanghai",
        "trading_hours": "09:30-15:00",
    },
    {
        "code": "HK",
        "name": "港股",
        "name_en": "Hong Kong Stocks",
        "currency": "HKD",
        "timezone": "Asia/Hong_Kong",
        "trading_hours": "09:30-16:00",
    },
    {
        "code": "US",
        "name": "美股",
        "name_en": "US Stocks",
        "currency": "USD",
        "timezone": "America/New_York",
        "trading_hours": "09:30-16:00",
    },
]

_PROVIDERS: dict = {
    "CN": [
        {
            "id": "akshare",
            "name": "AKShare",
            "description": "免费开源 A 股数据库，无需 API Key",
            "enabled": True,
            "priority": 1,
        },
        {
            "id": "tushare",
            "name": "Tushare Pro",
            "description": "专业 A 股数据，需要 Token",
            "enabled": settings.TUSHARE_ENABLED,
            "priority": 2,
        },
        {
            "id": "baostock",
            "name": "BaoStock",
            "description": "证券宝，免费历史数据",
            "enabled": True,
            "priority": 3,
        },
    ],
    "HK": [
        {
            "id": "akshare",
            "name": "AKShare",
            "description": "通过 AKShare 获取港股数据",
            "enabled": True,
            "priority": 1,
        },
    ],
    "US": [
        {
            "id": "yfinance",
            "name": "Yahoo Finance",
            "description": "通过 yfinance 获取美股数据",
            "enabled": True,
            "priority": 1,
        },
        {
            "id": "finnhub",
            "name": "FinnHub",
            "description": "专业美股数据，需要 API Key",
            "enabled": bool(settings.FINNHUB_API_KEY),
            "priority": 2,
        },
    ],
}


@router.get("", response_model=ApiResponse)
async def get_markets(current_user: dict = Depends(get_current_user)):
    """获取支持的市场列表"""
    return ApiResponse.ok(
        data={"markets": _MARKETS, "count": len(_MARKETS)},
    )


@router.get("/{market}/providers", response_model=ApiResponse)
async def get_providers(
    market: str,
    current_user: dict = Depends(get_current_user),
):
    """获取指定市场的数据提供商列表"""
    providers = _PROVIDERS.get(market.upper(), [])
    return ApiResponse.ok(
        data={
            "market": market.upper(),
            "providers": providers,
            "default": settings.DEFAULT_CHINA_DATA_SOURCE if market.upper() == "CN" else providers[0]["id"] if providers else None,
        },
    )
