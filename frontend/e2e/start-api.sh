#!/usr/bin/env bash
# 端到端测试用后端：每次在临时目录新建数据库（只含合成数据），创建管理员、导入规则后启动。
set -euo pipefail
cd "$(dirname "$0")/../.."
DATA="$(mktemp -d)"
export ZONGCE_DATABASE_URL="sqlite:///$DATA/e2e.sqlite3"
export ZONGCE_UPLOAD_DIR="$DATA/uploads"
export ZONGCE_JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
uv run --frozen zongce init-db
echo "${E2E_ADMIN_PASSWORD:?}" | uv run --frozen zongce create-admin --username e2eadmin --password-stdin
uv run --frozen zongce load-rules rules/ujn-v1.json --catalog rules/ability-catalog-xxgc-2020.json
exec uv run --frozen zongce serve --port "${E2E_API_PORT:?}"
