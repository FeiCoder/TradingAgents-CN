#!/usr/bin/env bash
# extract.sh – 将 data_service 从 TradingAgents-CN 抽离为独立 git 仓库
#
# 用法（在 TradingAgents-CN 项目根目录下运行）:
#   chmod +x data_service/standalone/extract.sh
#   ./data_service/standalone/extract.sh [目标目录]
#
# 例:
#   ./data_service/standalone/extract.sh ~/projects/trading-data-service
#   ./data_service/standalone/extract.sh  # 默认在 ../trading-data-service

set -euo pipefail

# ── 参数处理 ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"   # TradingAgents-CN root
DEST="${1:-"$(dirname "${SOURCE_ROOT}")/trading-data-service"}"

echo "=========================================="
echo "  trading-data-service 独立仓库提取工具"
echo "=========================================="
echo "  源目录 : ${SOURCE_ROOT}/data_service"
echo "  目标目录: ${DEST}"
echo ""

if [ -e "${DEST}" ]; then
    echo "⚠️  目标目录已存在: ${DEST}"
    read -r -p "是否继续？已有内容将被覆盖 [y/N] " confirm
    [[ "${confirm,,}" == "y" ]] || { echo "已取消。"; exit 0; }
fi

# ── 创建目标目录结构 ──────────────────────────────────────
echo "📁 创建目标目录 ..."
mkdir -p "${DEST}"

# ── 复制 Python 包 ────────────────────────────────────────
echo "📦 复制 data_service Python 包 ..."
cp -r "${SOURCE_ROOT}/data_service" "${DEST}/data_service"
# 移除 standalone/ 子目录（它属于 TradingAgents-CN 的构建产物，不属于新 repo）
rm -rf "${DEST}/data_service/standalone"
# 清理 Python 字节码缓存
find "${DEST}/data_service" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "${DEST}/data_service" -name '*.pyc' -o -name '*.pyo' | xargs rm -f 2>/dev/null || true

# ── 复制测试 ──────────────────────────────────────────────
echo "🧪 复制测试 ..."
if [ -d "${SOURCE_ROOT}/data_service/tests" ]; then
    cp -r "${SOURCE_ROOT}/data_service/tests" "${DEST}/tests"
else
    mkdir -p "${DEST}/tests"
    touch "${DEST}/tests/__init__.py"
fi

# ── 提升 standalone/ 文件到仓库根目录 ────────────────────
echo "📄 复制仓库配置文件 ..."
for f in pyproject.toml requirements.txt Dockerfile docker-compose.yml \
          VERSION README.md; do
    cp "${SCRIPT_DIR}/${f}" "${DEST}/${f}"
done

# .gitignore 和 .env.example 有前缀点号，单独处理
cp "${SCRIPT_DIR}/.gitignore"   "${DEST}/.gitignore"
cp "${SCRIPT_DIR}/.env.example" "${DEST}/.env.example"

# ── 初始化 git 仓库 ───────────────────────────────────────
echo "🔧 初始化 git 仓库 ..."
cd "${DEST}"
git init -b main
git add .
git commit -m "feat: initial commit - extracted from TradingAgents-CN"

# ── 完成 ──────────────────────────────────────────────────
echo ""
echo "✅ 提取完成！"
echo ""
echo "下一步："
echo "  cd ${DEST}"
echo "  pip install -e '.[dev]'          # 安装依赖"
echo "  cp .env.example .env             # 配置环境变量"
echo "  pytest tests/ -v                 # 运行测试"
echo "  uvicorn data_service.main:app --port 8001 --reload  # 启动服务"
echo ""
echo "推送到新的远程仓库:"
echo "  git remote add origin https://github.com/你的用户名/trading-data-service.git"
echo "  git push -u origin main"
