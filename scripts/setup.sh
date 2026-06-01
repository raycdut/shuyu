#!/usr/bin/env bash
#
# Shuyu — Agentic Data Analyst 一键部署脚本
#
# 使用方法:
#   curl -fsSL https://raw.githubusercontent.com/.../setup.sh | bash
#   或
#   ./scripts/setup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ── 颜色 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 前置检查 ──────────────────────────────────────────────────────────────────
info "检查运行环境..."

for cmd in docker docker compose; do
    if ! command -v "$cmd" &>/dev/null; then
        err "$cmd 未安装，请先安装 Docker"
        exit 1
    fi
done
ok "Docker 环境就绪"

# ── .env 文件 ─────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        warn ".env 文件已从 .env.example 创建"
        warn "请编辑 .env 文件配置 LLM_API_KEY，然后重新运行此脚本"
        exit 1
    else
        err ".env.example 不存在，请确认项目文件完整"
        exit 1
    fi
fi

if grep -q "sk-your-api-key-here" .env 2>/dev/null; then
    warn ".env 中的 LLM_API_KEY 尚未配置"
    warn "请编辑 .env 文件填入你的 API Key"
    exit 1
fi
ok ".env 配置就绪"

# ── 注入 .env 到 shell 环境 ───────────────────────────────────────────────────
set -a
source .env
set +a

# ── 拉取镜像并启动 ────────────────────────────────────────────────────────────
info "构建并启动服务..."
docker compose up -d --build

info "等待 MySQL 就绪..."
MYSQL_SERVICE="mysql"
RETRIES=30
until docker compose exec -T "$MYSQL_SERVICE" mysqladmin ping -u root -p"${MYSQL_ROOT_PASSWORD:-rootpass123}" --silent &>/dev/null; do
    RETRIES=$((RETRIES - 1))
    if [ "$RETRIES" -le 0 ]; then
        err "MySQL 启动超时"
        exit 1
    fi
    sleep 2
done
ok "MySQL 就绪"

info "等待后端就绪..."
RETRIES=30
until curl -s http://localhost:8000/api/docs > /dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ "$RETRIES" -le 0 ]; then
        err "后端启动超时"
        exit 1
    fi
    sleep 2
done
ok "后端就绪"

# ── 完成 ──────────────────────────────────────────────────────────────────────
echo ""
ok "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "  部署完成！"
ok ""
ok "  前端: http://localhost:3000"
ok "  后端: http://localhost:8000"
ok "  API:  http://localhost:8000/api/docs"
ok "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
info "首次使用请先注册管理员账号"
info "运行 docker compose logs -f 查看实时日志"
