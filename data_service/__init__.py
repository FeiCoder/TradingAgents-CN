"""
TradingAgents-CN 数据管理服务
独立的数据管理微服务，提供 HTTP 接口

架构分层：
  数据获取层 (Acquisition)  → 从多市场数据提供商拉取原始数据
  缓存层     (Cache)        → Redis / MongoDB / 文件三级缓存
  处理层     (Processing)   → 数据清洗、格式化、标准化
  分析层     (Analysis)     → 技术指标计算
"""

__version__ = "1.0.0"
