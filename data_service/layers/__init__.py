"""
数据流分层架构
  Layer 1 – Acquisition  : 数据获取（多市场数据提供商）
  Layer 2 – Cache        : 多级缓存（Redis → MongoDB → 文件）
  Layer 3 – Processing   : 数据清洗与格式化
  Layer 4 – Analysis     : 技术指标计算
"""
