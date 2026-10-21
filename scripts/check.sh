#!/usr/bin/env bash
# 本地一键检查，与 CI 相同：格式、lint、类型检查、引擎（覆盖率 100%）、legacy 对拍、AI 流水线（覆盖率 100%）、
# 后端（覆盖率 ≥ 80%）。
# 用法：bash scripts/check.sh   （首次运行前：uv sync；cd tests/parity && pnpm install）
set -euo pipefail
cd "$(dirname "$0")/.."

uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen mypy --strict
uv run --frozen pytest engine/tests tests -q --cov=zongce_engine --cov-branch --cov-fail-under=100
uv run --frozen pytest ai/pipeline/tests -q --cov=zongce_ai --cov-branch --cov-fail-under=100
uv run --frozen pytest backend/tests -q --cov=zongce_backend --cov-branch --cov-fail-under=80
