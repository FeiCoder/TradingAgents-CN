"""
股票数据服务
整合数据获取、缓存、处理三层，对外提供统一的股票数据访问接口
"""

import logging
from typing import Any, Dict, List, Optional

from data_service.config import settings
from data_service.layers.acquisition import get_acquisition_layer
from data_service.layers.cache import get_cache_layer
from data_service.layers.processing import get_processing_layer

logger = logging.getLogger(__name__)

_HISTORY_CACHE_NS = "history"
_LIST_CACHE_NS = "stock_list"


class StockService:
    """股票数据业务服务"""

    def __init__(self):
        self._acq = get_acquisition_layer()
        self._cache = get_cache_layer()
        self._proc = get_processing_layer()

    # ── 股票列表 ──────────────────────────────────────────

    async def get_stock_list(
        self, market: str = "CN", force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取指定市场的股票列表

        Args:
            market: 市场代码 CN / HK / US
            force_refresh: 是否强制刷新缓存
        """
        if not force_refresh:
            cached = await self._cache.get(_LIST_CACHE_NS, market)
            if cached is not None:
                return cached

        if market == "CN":
            records = self._acq.get_china_stock_list()
        else:
            records = []
            logger.warning(f"市场 {market} 的股票列表暂不支持批量获取")

        if records:
            await self._cache.set(records, _LIST_CACHE_NS, market, ttl=settings.CACHE_TTL)

        return records

    # ── 历史 K 线 ─────────────────────────────────────────

    async def get_stock_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        market: str = "CN",
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        获取股票历史 K 线数据（带三级缓存）

        Args:
            symbol: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            market: 市场代码
            force_refresh: 是否强制刷新
        """
        if not force_refresh:
            cached = await self._cache.get(_HISTORY_CACHE_NS, market, symbol, start_date, end_date)
            if cached is not None:
                return cached

        # 从数据提供商拉取
        if market == "CN":
            raw = self._acq.get_china_stock_history(symbol, start_date, end_date)
        elif market == "HK":
            raw = self._acq.get_hk_stock_history(symbol, start_date, end_date)
        elif market == "US":
            raw = self._acq.get_us_stock_history(symbol, start_date, end_date)
        else:
            raw = []

        if not raw:
            return []

        # 经过处理层标准化
        df = self._proc.normalize_ohlcv(raw)
        df = self._proc.filter_date_range(df, start_date, end_date)
        df = self._proc.fill_missing(df)
        df = self._proc.add_basic_metrics(df)
        records = self._proc.to_records(df)

        # 写入缓存
        ttl = settings.STOCK_DATA_CACHE_TTL
        await self._cache.set(records, _HISTORY_CACHE_NS, market, symbol, start_date, end_date, ttl=ttl)

        return records

    # ── 快速查询 ──────────────────────────────────────────

    async def search_stocks(
        self, keyword: str, market: str = "CN"
    ) -> List[Dict[str, Any]]:
        """根据关键词（代码/名称）搜索股票"""
        stocks = await self.get_stock_list(market=market)
        kw = keyword.lower()
        return [
            s for s in stocks
            if kw in s.get("symbol", "").lower() or kw in s.get("name", "").lower()
        ]


# ── 模块级别单例 ──────────────────────────────────────────
_stock_service: Optional[StockService] = None


def get_stock_service() -> StockService:
    global _stock_service
    if _stock_service is None:
        _stock_service = StockService()
    return _stock_service
