"""
Layer 3 – 数据处理层
对原始数据进行清洗、格式化、标准化，生成上层可直接使用的数据集。
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ProcessingLayer:
    """数据处理层：清洗 + 格式化 + 标准化"""

    def normalize_ohlcv(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        将原始 OHLCV 记录列表标准化为 DataFrame

        标准列：date, open, high, low, close, volume, amount, pct_chg
        """
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        # 确保必要列存在
        required = ["date", "open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                df[col] = 0.0

        # 类型转换
        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "pct_chg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # 日期格式统一
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        # 删除重复日期，保留最新数据
        df = df.drop_duplicates(subset=["date"], keep="last")
        df = df.sort_values("date").reset_index(drop=True)

        return df

    def to_records(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """DataFrame 转换为字典列表"""
        if df.empty:
            return []
        return df.to_dict(orient="records")

    def filter_date_range(
        self,
        df: pd.DataFrame,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        """按日期范围过滤数据"""
        if df.empty:
            return df
        if start_date:
            df = df[df["date"] >= start_date]
        if end_date:
            df = df[df["date"] <= end_date]
        return df.reset_index(drop=True)

    def fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """填充缺失值（前向填充收盘价相关字段）"""
        if df.empty:
            return df
        price_cols = ["open", "high", "low", "close"]
        df[price_cols] = df[price_cols].replace(0, None).ffill()
        return df

    def add_basic_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加基础衍生指标（涨跌额、振幅）"""
        if df.empty or "close" not in df.columns:
            return df
        df = df.copy()
        df["change"] = df["close"].diff().round(4)
        if "pct_chg" not in df.columns or (df["pct_chg"] == 0).all():
            df["pct_chg"] = (df["close"].pct_change() * 100).round(4)
        if "high" in df.columns and "low" in df.columns:
            prev_close = df["close"].shift(1)
            denominator = prev_close.where(prev_close != 0, df["close"])
            df["amplitude"] = ((df["high"] - df["low"]) / denominator * 100).round(4)
        return df


# ── 模块级别单例 ──────────────────────────────────────────
_processor: Optional[ProcessingLayer] = None


def get_processing_layer() -> ProcessingLayer:
    global _processor
    if _processor is None:
        _processor = ProcessingLayer()
    return _processor
