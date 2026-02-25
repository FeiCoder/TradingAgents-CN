# trading-data-service – 独立 Docker 镜像
# 构建: docker build -t trading-data-service .
# 运行: docker compose up -d

FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    DOCKER_CONTAINER=true

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（先复制依赖声明以利用 Docker 层缓存）
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip && \
    pip install --prefer-binary ".[dev]"

# 复制应用代码
COPY data_service ./data_service
COPY VERSION ./VERSION

# 运行时目录
RUN mkdir -p /app/logs /app/cache /app/data

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:8001/healthz || exit 1

CMD ["python", "-m", "uvicorn", "data_service.main:app", \
     "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
