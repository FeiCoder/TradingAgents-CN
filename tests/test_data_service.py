"""
数据管理服务单元测试

覆盖范围：
  - 配置模块（服务发现、环境变量解析）
  - 数据处理层（OHLCV 标准化、日期过滤、指标计算）
  - 技术分析层（MA / MACD / RSI / BOLL / KDJ / ATR）
  - 缓存键生成逻辑
  - API 响应模型
  - FastAPI 路由（通过 TestClient 测试健康检查接口）
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

# 确保项目根目录在 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────
# 辅助函数：生成示例 OHLCV 记录
# ─────────────────────────────────────────────────────────

def _sample_records(n: int = 30) -> list:
    import random
    from datetime import date, timedelta

    records = []
    close = 10.0
    start = date(2024, 1, 1)
    for i in range(n):
        d = (start + timedelta(days=i)).isoformat()
        close = round(close * (1 + random.uniform(-0.02, 0.02)), 2)
        records.append({
            "date": d,
            "open": round(close * 0.99, 2),
            "high": round(close * 1.01, 2),
            "low": round(close * 0.98, 2),
            "close": close,
            "volume": random.randint(100000, 5000000),
            "amount": random.uniform(1e6, 5e7),
            "pct_chg": round(random.uniform(-2, 2), 4),
        })
    return records


# ─────────────────────────────────────────────────────────
# 1. 配置模块测试
# ─────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self):
        """默认配置不依赖外部服务即可实例化"""
        from data_service.config import DataServiceSettings
        s = DataServiceSettings()
        assert s.PORT == 8001
        assert s.MONGODB_DATABASE == "tradingagents"

    def test_mongo_uri_no_auth(self):
        from data_service.config import DataServiceSettings
        s = DataServiceSettings(MONGODB_USERNAME="", MONGODB_PASSWORD="")
        assert s.MONGO_URI.startswith("mongodb://")
        assert "@" not in s.MONGO_URI

    def test_mongo_uri_with_auth(self):
        from data_service.config import DataServiceSettings
        s = DataServiceSettings(
            MONGODB_USERNAME="user",
            MONGODB_PASSWORD="pass",
            MONGODB_HOST="db-host",
            MONGODB_PORT=27017,
            MONGODB_DATABASE="mydb",
            MONGODB_AUTH_SOURCE="admin",
        )
        assert "user:pass@db-host:27017/mydb" in s.MONGO_URI

    def test_redis_url_no_auth(self):
        from data_service.config import DataServiceSettings
        s = DataServiceSettings(REDIS_PASSWORD="")
        assert s.REDIS_URL.startswith("redis://")

    def test_redis_url_with_auth(self):
        from data_service.config import DataServiceSettings
        s = DataServiceSettings(REDIS_PASSWORD="secret", REDIS_HOST="cache", REDIS_PORT=6379)
        assert ":secret@cache:6379" in s.REDIS_URL

    def test_docker_service_discovery(self):
        """Docker 环境下默认使用服务名而非 localhost"""
        with patch.dict(os.environ, {"DOCKER_CONTAINER": "true"}, clear=False):
            # 重新导入使默认工厂函数生效
            from data_service import config as cfg_module
            assert cfg_module._default_mongo_host() == "mongodb"
            assert cfg_module._default_redis_host() == "redis"

    def test_local_defaults(self):
        """非 Docker 环境使用 localhost"""
        with patch.dict(os.environ, {"DOCKER_CONTAINER": "false"}, clear=False):
            from data_service import config as cfg_module
            assert cfg_module._default_mongo_host() == "localhost"
            assert cfg_module._default_redis_host() == "localhost"


# ─────────────────────────────────────────────────────────
# 2. 数据处理层测试
# ─────────────────────────────────────────────────────────

class TestProcessingLayer:
    def setup_method(self):
        from data_service.layers.processing import ProcessingLayer
        self.proc = ProcessingLayer()

    def test_normalize_empty(self):
        df = self.proc.normalize_ohlcv([])
        assert df.empty

    def test_normalize_basic(self):
        records = _sample_records(10)
        df = self.proc.normalize_ohlcv(records)
        assert len(df) == 10
        assert "close" in df.columns
        assert "date" in df.columns

    def test_normalize_sorts_by_date(self):
        records = _sample_records(5)
        shuffled = records[::-1]  # 倒序
        df = self.proc.normalize_ohlcv(shuffled)
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_filter_date_range(self):
        records = _sample_records(30)
        df = self.proc.normalize_ohlcv(records)
        filtered = self.proc.filter_date_range(df, "2024-01-05", "2024-01-15")
        assert all(d >= "2024-01-05" for d in filtered["date"])
        assert all(d <= "2024-01-15" for d in filtered["date"])

    def test_add_basic_metrics(self):
        records = _sample_records(20)
        df = self.proc.normalize_ohlcv(records)
        df = self.proc.add_basic_metrics(df)
        assert "change" in df.columns
        assert "pct_chg" in df.columns

    def test_to_records(self):
        records = _sample_records(5)
        df = self.proc.normalize_ohlcv(records)
        back = self.proc.to_records(df)
        assert len(back) == 5
        assert isinstance(back[0], dict)


# ─────────────────────────────────────────────────────────
# 3. 技术分析层测试
# ─────────────────────────────────────────────────────────

class TestAnalysisLayer:
    def setup_method(self):
        from data_service.layers.analysis import AnalysisLayer
        from data_service.layers.processing import ProcessingLayer
        self.analysis = AnalysisLayer()
        self.proc = ProcessingLayer()
        self.df = self.proc.normalize_ohlcv(_sample_records(60))

    def test_add_ma(self):
        df = self.analysis.add_ma(self.df, [5, 10])
        assert "MA5" in df.columns
        assert "MA10" in df.columns

    def test_add_ema(self):
        df = self.analysis.add_ema(self.df, [12])
        assert "EMA12" in df.columns

    def test_add_macd(self):
        df = self.analysis.add_macd(self.df)
        assert "MACD_DIF" in df.columns
        assert "MACD_DEA" in df.columns
        assert "MACD_HIST" in df.columns

    def test_add_rsi(self):
        df = self.analysis.add_rsi(self.df, [14])
        assert "RSI14" in df.columns
        # RSI 值域 0-100
        valid = df["RSI14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_add_bollinger(self):
        df = self.analysis.add_bollinger(self.df)
        assert "BOLL_MID" in df.columns
        assert "BOLL_UPPER" in df.columns
        assert "BOLL_LOWER" in df.columns
        # 上轨 >= 中轨 >= 下轨
        valid = df.dropna(subset=["BOLL_UPPER", "BOLL_MID", "BOLL_LOWER"])
        assert (valid["BOLL_UPPER"] >= valid["BOLL_MID"]).all()
        assert (valid["BOLL_MID"] >= valid["BOLL_LOWER"]).all()

    def test_add_kdj(self):
        df = self.analysis.add_kdj(self.df)
        assert "KDJ_K" in df.columns
        assert "KDJ_D" in df.columns
        assert "KDJ_J" in df.columns

    def test_add_atr(self):
        df = self.analysis.add_atr(self.df, 14)
        assert "ATR14" in df.columns
        # ATR 值应非负
        valid = df["ATR14"].dropna()
        assert (valid >= 0).all()

    def test_compute_all(self):
        df = self.analysis.compute_all(self.df)
        for col in ["MA5", "EMA12", "MACD_DIF", "RSI14", "BOLL_MID", "KDJ_K", "ATR14"]:
            assert col in df.columns

    def test_empty_df_safe(self):
        """空 DataFrame 传入不应抛出异常"""
        empty = pd.DataFrame()
        result = self.analysis.compute_all(empty)
        assert result.empty

    def test_indicator_summary(self):
        df = self.analysis.add_ma(self.df, [5])
        summary = self.analysis.to_indicator_summary(df)
        assert "MA5" in summary
        assert isinstance(summary["MA5"], (float, int, type(None)))


# ─────────────────────────────────────────────────────────
# 4. 缓存键生成测试
# ─────────────────────────────────────────────────────────

class TestCacheKeys:
    def test_key_format(self):
        from data_service.layers.cache import _make_key
        key = _make_key("history", "CN", "000001", "2024-01-01", "2024-03-31")
        assert key.startswith("history:")
        assert "CN" in key

    def test_long_key_hashed(self):
        from data_service.layers.cache import _make_key
        long_parts = ["part"] * 50
        key = _make_key("ns", *long_parts)
        assert len(key) <= 250  # 超长键会被 hash 压缩

    def test_key_consistency(self):
        from data_service.layers.cache import _make_key
        k1 = _make_key("a", "b", "c")
        k2 = _make_key("a", "b", "c")
        assert k1 == k2


# ─────────────────────────────────────────────────────────
# 5. API 响应模型测试
# ─────────────────────────────────────────────────────────

class TestApiResponse:
    def test_ok(self):
        from data_service.models.response import ApiResponse
        r = ApiResponse.ok(data={"key": "value"}, message="done")
        assert r.success is True
        assert r.data == {"key": "value"}
        assert r.error is None

    def test_fail(self):
        from data_service.models.response import ApiResponse
        r = ApiResponse.fail(error="not found")
        assert r.success is False
        assert r.error == "not found"


# ─────────────────────────────────────────────────────────
# 6. HTTP 路由测试（TestClient，不需要真实数据库）
# ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """创建测试客户端，mock 数据库连接"""
    with patch("data_service.db.init_mongodb", new_callable=AsyncMock, return_value=False), \
         patch("data_service.db.init_redis", new_callable=AsyncMock, return_value=False), \
         patch("data_service.db.close_connections", new_callable=AsyncMock), \
         patch("data_service.db.check_health", new_callable=AsyncMock, return_value={
             "mongodb": {"status": "disabled"},
             "redis": {"status": "disabled"},
         }):
        from data_service.main import app
        with TestClient(app) as c:
            yield c


class TestHealthRoutes:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "ok"

    def test_healthz_endpoint(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readyz_endpoint(self, client):
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True

    def test_root_endpoint(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body
        assert "docs" in body


class TestAuthRoutes:
    def test_login_default_admin(self, client):
        """默认管理员账号 admin/admin123 应能登录"""
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "access_token" in body["data"]

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_me_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_token(self, client):
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        token = login.json()["data"]["access_token"]
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["username"] == "admin"


class TestMarketRoutes:
    def _get_token(self, client) -> str:
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        return r.json()["data"]["access_token"]

    def test_get_markets(self, client):
        token = self._get_token(client)
        resp = client.get("/api/markets", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        markets = body["data"]["markets"]
        codes = [m["code"] for m in markets]
        assert "CN" in codes
        assert "HK" in codes
        assert "US" in codes

    def test_get_cn_providers(self, client):
        token = self._get_token(client)
        resp = client.get("/api/markets/CN/providers", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        provider_ids = [p["id"] for p in body["data"]["providers"]]
        assert "akshare" in provider_ids
