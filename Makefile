.PHONY: up down restart logs build clean setup

# ── 一键启动 ───────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

restart: down up

# ── 日志 ──────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-mysql:
	docker compose logs -f mysql

# ── 构建 ──────────────────────────────────────────────────────────────────────
build:
	docker compose build

rebuild: build up

# ── 初始化 ─────────────────────────────────────────────────────────────────────
init:
	@echo "等待后端就绪..."
	@until curl -s http://localhost:8000/api/docs > /dev/null 2>&1; do sleep 2; done
	@echo "后端已就绪！"
	@echo "前端: http://localhost:3000"
	@echo "后端: http://localhost:8000"

# ── 一键设置（首次使用） ─────────────────────────────────────────────────────────
setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "已创建 .env 文件，请编辑配置 LLM_API_KEY 后重新运行 make setup"; \
		exit 1; \
	fi
	docker compose up -d
	$(MAKE) init

# ── 数据管理 ──────────────────────────────────────────────────────────────────
migrate:
	docker compose exec backend python -m app.cli init

shell-backend:
	docker compose exec backend bash

shell-mysql:
	docker compose exec mysql mysql -u root -p"${MYSQL_ROOT_PASSWORD}" shuyu_config

# ── 清理 ──────────────────────────────────────────────────────────────────────
clean: down
	docker compose down -v
	@echo "提示: 数据卷已删除，所有 MySQL 数据将丢失"
