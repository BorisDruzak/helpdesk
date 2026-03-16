#!/usr/bin/env bash
# Запуск агента для E2E против локального сервера (localhost:8666).
# Требует: сервер уже запущен (scripts/run_server.py), в identity агента — валидный токен.
# Использование:
#   ./scripts/run_agent_e2e.sh
#   или: PC_AGENT_DATA_DIR=.run/agent_e2e ./scripts/run_agent_e2e.sh
set -e
WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE"
export PC_AGENT_WS_URL="${PC_AGENT_WS_URL:-ws://127.0.0.1:8666/ws}"
export PC_AGENT_API_URL="${PC_AGENT_API_URL:-http://127.0.0.1:8666/api}"
AGENT_ARGS=()
if [ -n "$PC_AGENT_DATA_DIR" ]; then
  AGENT_ARGS+=(--data-dir "$PC_AGENT_DATA_DIR")
fi
exec python3 scripts/run_agent.py "${AGENT_ARGS[@]}"
