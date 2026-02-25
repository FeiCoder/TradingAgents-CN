"""
Layer 4 – 技术分析层
计算常用技术指标：MA、EMA、MACD、RSI、BOLL、KDJ、ATR 等
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class AnalysisLayer:
    """技术分析层：在处理层输出的标准 DataFrame 上计算技术指标"""

    # ── 均线 ──────────────────────────────────────────────

    def add_ma(self, df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
        """添加简单移动平均线"""
        if df.empty:
            return df
        df = df.copy()
        for p in (periods or [5, 10, 20, 60]):
            df[f"MA{p}"] = df["close"].rolling(window=p, min_periods=1).mean().round(4)
        return df

    def add_ema(self, df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
        """添加指数移动平均线"""
        if df.empty:
            return df
        df = df.copy()
        for p in (periods or [12, 26]):
            df[f"EMA{p}"] = df["close"].ewm(span=p, adjust=False).mean().round(4)
        return df

    # ── MACD ──────────────────────────────────────────────

    def add_macd(
        self,
        df: pd.DataFrame,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> pd.DataFrame:
        """添加 MACD 指标（DIF、DEA、MACD 柱）"""
        if df.empty:
            return df
        df = df.copy()
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        df["MACD_DIF"] = (ema_fast - ema_slow).round(4)
        df["MACD_DEA"] = df["MACD_DIF"].ewm(span=signal, adjust=False).mean().round(4)
        df["MACD_HIST"] = (2 * (df["MACD_DIF"] - df["MACD_DEA"])).round(4)
        return df

    # ── RSI ───────────────────────────────────────────────

    def add_rsi(self, df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
        """添加 RSI 指标"""
        if df.empty:
            return df
        df = df.copy()
        delta = df["close"].diff()
        for p in (periods or [6, 14]):
            gain = delta.clip(lower=0).rolling(window=p, min_periods=1).mean()
            loss = (-delta.clip(upper=0)).rolling(window=p, min_periods=1).mean()
            rs = gain / loss.replace(0, float("inf"))
            df[f"RSI{p}"] = (100 - 100 / (1 + rs)).round(4)
        return df

    # ── 布林带 ────────────────────────────────────────────

    def add_bollinger(
        self, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """添加布林带（BOLL_UPPER / BOLL_MID / BOLL_LOWER）"""
        if df.empty:
            return df
        df = df.copy()
        mid = df["close"].rolling(window=period, min_periods=1).mean()
        std = df["close"].rolling(window=period, min_periods=1).std()
        df["BOLL_MID"] = mid.round(4)
        df["BOLL_UPPER"] = (mid + std_dev * std).round(4)
        df["BOLL_LOWER"] = (mid - std_dev * std).round(4)
        return df

    # ── KDJ ───────────────────────────────────────────────

    def add_kdj(
        self, df: pd.DataFrame, period: int = 9, signal: int = 3
    ) -> pd.DataFrame:
        """添加 KDJ 随机指标"""
        if df.empty or not all(c in df.columns for c in ["high", "low", "close"]):
            return df
        df = df.copy()
        low_min = df["low"].rolling(window=period, min_periods=1).min()
        high_max = df["high"].rolling(window=period, min_periods=1).max()
        denom = (high_max - low_min).replace(0, 1)
        rsv = (df["close"] - low_min) / denom * 100
        df["KDJ_K"] = rsv.ewm(com=signal - 1, adjust=False).mean().round(4)
        df["KDJ_D"] = df["KDJ_K"].ewm(com=signal - 1, adjust=False).mean().round(4)
        df["KDJ_J"] = (3 * df["KDJ_K"] - 2 * df["KDJ_D"]).round(4)
        return df

    # ── ATR ───────────────────────────────────────────────

    def add_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """添加平均真实波动范围 (ATR)"""
        if df.empty or not all(c in df.columns for c in ["high", "low", "close"]):
            return df
        df = df.copy()
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        df[f"ATR{period}"] = tr.rolling(window=period, min_periods=1).mean().round(4)
        return df

    # ── 全量指标 ──────────────────────────────────────────

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """一次性计算所有常用技术指标"""
        df = self.add_ma(df)
        df = self.add_ema(df)
        df = self.add_macd(df)
        df = self.add_rsi(df)
        df = self.add_bollinger(df)
        df = self.add_kdj(df)
        df = self.add_atr(df)
        return df

    def to_indicator_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """返回最新一行的技术指标摘要字典"""
        if df.empty:
            return {}
        last = df.iloc[-1]
        return {k: (None if pd.isna(v) else v) for k, v in last.items()}


# ── 模块级别单例 ──────────────────────────────────────────
_analysis: Optional[AnalysisLayer] = None


def get_analysis_layer() -> AnalysisLayer:
    global _analysis
    if _analysis is None:
        _analysis = AnalysisLayer()
    return _analysis
