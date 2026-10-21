#!/usr/bin/env bash
# 本机一键演示：用合成演示库启动后端，并由后端同时提供已构建的前端，浏览器打开 http://127.0.0.1:8000 即可使用。
#
# 用法（在仓库根目录）：
#   bash scripts/local-demo.sh            # 默认端口 8000
#   PORT=8080 bash scripts/local-demo.sh
#   bash scripts/local-demo.sh --reset    # 删除演示库，重新生成
#
# - 演示库、上传目录、JWT 密钥和演示密码都放在 data/local-demo/（已被 git 忽略），不含任何真实数据。
# - Python 环境按系统分开存放（如 .venv-darwin-arm64），不影响其他环境里的 .venv。
# - 只监听 127.0.0.1，局域网内的其他电脑访问不到。
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
DEMO="data/local-demo"

if ! command -v uv >/dev/null 2>&1; then
  echo "没有找到 uv。Mac 上先执行：brew install uv（或见 https://docs.astral.sh/uv/）" >&2
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  if command -v pnpm >/dev/null 2>&1; then
    (cd frontend && pnpm install --frozen-lockfile && pnpm build)
  else
    echo "缺少前端构建产物 frontend/dist。先在 frontend/ 下执行：pnpm install && pnpm build" >&2
    exit 1
  fi
fi

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv-$os-$(uname -m)}"

if [ "${1:-}" = "--reset" ]; then
  rm -rf "$DEMO"
fi
mkdir -p "$DEMO"
chmod 700 "$DEMO"

secret_file="$DEMO/jwt-secret"
password_file="$DEMO/演示密码.txt"
if [ ! -s "$secret_file" ]; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(48))' >"$secret_file"
  chmod 600 "$secret_file"
fi

export ZONGCE_DATABASE_URL="sqlite:///$PWD/$DEMO/demo.sqlite3"
export ZONGCE_UPLOAD_DIR="$PWD/$DEMO/uploads"
export ZONGCE_JWT_SECRET="$(cat "$secret_file")"
export ZONGCE_FRONTEND_DIST="$PWD/frontend/dist"
export ZONGCE_AI_PROVIDER=none

if [ ! -f "$DEMO/demo.sqlite3" ]; then
  python3 -c 'import secrets; print("Demo-" + secrets.token_urlsafe(9))' >"$password_file"
  chmod 600 "$password_file"
  uv run --frozen zongce seed-demo --password-stdin <"$password_file"
fi

cat <<EOF

演示站点：http://127.0.0.1:$PORT
  学院管理员：demo_admin
  班级审核员：TEST01001（测试1班）、TEST02001（测试2班），同时是学生
  学生：TEST01002 起（测试1班）、TEST02002 起（测试2班）
  所有演示账号共用的密码保存在 $password_file
按 Ctrl+C 停止。
EOF
exec uv run --frozen zongce serve --port "$PORT"
