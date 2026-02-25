"""
Layer 1 – 数据获取层
从多市场数据提供商（AKShare / Tushare / BaoStock / FinnHub）拉取原始数据，
统一规范化后向上层提供标准接口。
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from data_service.config import settings

logger = logging.getLogger(__name__)


# ── A 股数据提供商优先级顺序 ──────────────────────────────
_CHINA_PROVIDER_ORDER = ["akshare", "tushare", "baostock"]


class AcquisitionLayer:
    """数据获取层：封装多数据源，提供统一的数据拉取接口"""

    def __init__(self):
        self._china_source = settings.DEFAULT_CHINA_DATA_SOURCE

    # ── A 股 ──────────────────────────────────────────────

    def get_china_stock_list(self) -> List[Dict[str, Any]]:
        """获取 A 股股票列表"""
        providers = [self._china_source] + [
            p for p in _CHINA_PROVIDER_ORDER if p != self._china_source
        ]
        for provider in providers:
            try:
                result = self._fetch_china_list(provider)
                if result:
                    logger.info(f"A 股列表获取成功（来源：{provider}），共 {len(result)} 条")
                    return result
            except Exception as exc:
                logger.warning(f"A 股列表获取失败（来源：{provider}）: {exc}")
        return []

    def get_china_stock_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """获取 A 股历史 K 线数据"""
        providers = [self._china_source] + [
            p for p in _CHINA_PROVIDER_ORDER if p != self._china_source
        ]
        for provider in providers:
            try:
                result = self._fetch_china_history(provider, symbol, start_date, end_date)
                if result:
                    return result
            except Exception as exc:
                logger.warning(f"A 股历史数据获取失败（来源：{provider}）: {exc}")
        return []

    def _fetch_china_list(self, provider: str) -> List[Dict[str, Any]]:
        if provider == "akshare":
            return self._akshare_stock_list()
        if provider == "tushare":
            return self._tushare_stock_list()
        if provider == "baostock":
            return self._baostock_stock_list()
        return []

    def _fetch_china_history(
        self, provider: str, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        if provider == "akshare":
            return self._akshare_stock_history(symbol, start_date, end_date)
        if provider == "tushare":
            return self._tushare_stock_history(symbol, start_date, end_date)
        if provider == "baostock":
            return self._baostock_stock_history(symbol, start_date, end_date)
        return []

    # ── AKShare ───────────────────────────────────────────

    def _akshare_stock_list(self) -> List[Dict[str, Any]]:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return [
            {"symbol": row["code"], "name": row["name"], "market": "CN", "source": "akshare"}
            for _, row in df.iterrows()
        ]

    def _akshare_stock_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        import akshare as ak
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row.get("日期", "")),
                "open": float(row.get("开盘", 0)),
                "high": float(row.get("最高", 0)),
                "low": float(row.get("最低", 0)),
                "close": float(row.get("收盘", 0)),
                "volume": float(row.get("成交量", 0)),
                "amount": float(row.get("成交额", 0)),
                "pct_chg": float(row.get("涨跌幅", 0)),
            })
        return records

    # ── Tushare ───────────────────────────────────────────

    def _tushare_stock_list(self) -> List[Dict[str, Any]]:
        if not settings.TUSHARE_TOKEN:
            raise RuntimeError("TUSHARE_TOKEN 未配置")
        import tushare as ts
        ts.set_token(settings.TUSHARE_TOKEN)
        pro = ts.pro_api()
        df = pro.stock_basic(exchange="", list_status="L", fields="ts_code,name,market")
        return [
            {"symbol": row["ts_code"], "name": row["name"], "market": row["market"], "source": "tushare"}
            for _, row in df.iterrows()
        ]

    def _tushare_stock_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        if not settings.TUSHARE_TOKEN:
            raise RuntimeError("TUSHARE_TOKEN 未配置")
        import tushare as ts
        ts.set_token(settings.TUSHARE_TOKEN)
        pro = ts.pro_api()
        df = pro.daily(
            ts_code=symbol,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row.get("trade_date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("vol", 0)),
                "amount": float(row.get("amount", 0)),
                "pct_chg": float(row.get("pct_chg", 0)),
            })
        return records

    # ── BaoStock ──────────────────────────────────────────

    def _baostock_stock_list(self) -> List[Dict[str, Any]]:
        import baostock as bs
        lg = bs.login()
        rs = bs.query_stock_basic()
        records = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            records.append({
                "symbol": row[0],
                "name": row[2],
                "market": "CN",
                "source": "baostock",
            })
        bs.logout()
        return records

    def _baostock_stock_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        import baostock as bs
        lg = bs.login()
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,open,high,low,close,volume,amount,pctChg",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",
        )
        records = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            try:
                records.append({
                    "date": row[0],
                    "open": float(row[1]) if row[1] else 0,
                    "high": float(row[2]) if row[2] else 0,
                    "low": float(row[3]) if row[3] else 0,
                    "close": float(row[4]) if row[4] else 0,
                    "volume": float(row[5]) if row[5] else 0,
                    "amount": float(row[6]) if row[6] else 0,
                    "pct_chg": float(row[7]) if row[7] else 0,
                })
            except (ValueError, IndexError):
                continue
        bs.logout()
        return records

    # ── 港股 / 美股 ───────────────────────────────────────

    def get_hk_stock_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """获取港股历史数据（通过 AKShare）"""
        try:
            import akshare as ak
            df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            return df.rename(columns={"vol": "volume"}).to_dict("records")
        except Exception as exc:
            logger.warning(f"港股历史数据获取失败: {exc}")
            return []

    def get_us_stock_history(
        self, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """获取美股历史数据（通过 yfinance）"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            df = df.reset_index()
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row["Date"])[:10],
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
            return records
        except Exception as exc:
            logger.warning(f"美股历史数据获取失败: {exc}")
            return []


# ── 模块级别单例 ──────────────────────────────────────────
_acquisition: Optional[AcquisitionLayer] = None


def get_acquisition_layer() -> AcquisitionLayer:
    global _acquisition
    if _acquisition is None:
        _acquisition = AcquisitionLayer()
    return _acquisition
