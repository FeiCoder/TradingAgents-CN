"""
技术分析服务
整合处理层 + 分析层，提供技术指标计算的高级接口
"""

import logging
from typing import Any, Dict, List, Optional

from data_service.layers.analysis import get_analysis_layer
from data_service.layers.processing import get_processing_layer
from data_service.services.stock_service import get_stock_service

logger = logging.getLogger(__name__)


class TechnicalService:
    """技术分析服务"""

    def __init__(self):
        self._proc = get_processing_layer()
        self._analysis = get_analysis_layer()
        self._stocks = get_stock_service()

    async def get_indicators(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        market: str = "CN",
        indicators: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        获取指定股票的技术指标

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            market: 市场代码
            indicators: 指定计算的指标列表，None 表示全部
                        可选: ma, ema, macd, rsi, boll, kdj, atr

        Returns:
            {
                "symbol": "...",
                "latest": { "MA5": ..., "RSI14": ..., ... },
                "history": [{ "date": "...", ... }, ...]
            }
        """
        # 获取历史数据
        history = await self._stocks.get_stock_history(
            symbol, start_date, end_date, market=market
        )
        if not history:
            return {"symbol": symbol, "latest": {}, "history": []}

        # 处理层标准化
        df = self._proc.normalize_ohlcv(history)
        df = self._proc.fill_missing(df)

        # 分析层计算指标
        selected = set(indicators) if indicators else None

        if selected is None or "ma" in selected:
            df = self._analysis.add_ma(df)
        if selected is None or "ema" in selected:
            df = self._analysis.add_ema(df)
        if selected is None or "macd" in selected:
            df = self._analysis.add_macd(df)
        if selected is None or "rsi" in selected:
            df = self._analysis.add_rsi(df)
        if selected is None or "boll" in selected:
            df = self._analysis.add_bollinger(df)
        if selected is None or "kdj" in selected:
            df = self._analysis.add_kdj(df)
        if selected is None or "atr" in selected:
            df = self._analysis.add_atr(df)

        latest = self._analysis.to_indicator_summary(df)
        history_with_indicators = self._proc.to_records(df)

        return {
            "symbol": symbol,
            "market": market,
            "start_date": start_date,
            "end_date": end_date,
            "latest": latest,
            "history": history_with_indicators,
        }


# ── 模块级别单例 ──────────────────────────────────────────
_technical_service: Optional[TechnicalService] = None


def get_technical_service() -> TechnicalService:
    global _technical_service
    if _technical_service is None:
        _technical_service = TechnicalService()
    return _technical_service
