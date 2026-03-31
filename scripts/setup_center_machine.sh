#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_SUPPORT_DIR="${HOME}/Library/Application Support/KnowledgeBase"
RUNTIME_ROOT="${APP_SUPPORT_DIR}/runtime"
DATA_DIR="${APP_SUPPORT_DIR}/data"
LOG_DIR="${HOME}/Library/Logs/KnowledgeBase"
ENV_FILE="${APP_SUPPORT_DIR}/center.env"
TOKEN_FILE="${APP_SUPPORT_DIR}/api_token"
LAUNCH_SCRIPT="${APP_SUPPORT_DIR}/run_center_server.sh"
SOURCE_DB="${PROJECT_ROOT}/data/knowledge.db"

PORT="${KNOWLEDGE_PORT:-8787}"
HOST="${KNOWLEDGE_HOST:-0.0.0.0}"
DB_PATH="${KNOWLEDGE_DB_PATH:-${DATA_DIR}/knowledge.db}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"

mkdir -p "${APP_SUPPORT_DIR}" "${DATA_DIR}" "${LOG_DIR}" "${RUNTIME_ROOT}"

if [[ ! -s "${TOKEN_FILE}" ]]; then
  openssl rand -hex 32 > "${TOKEN_FILE}"
fi

TOKEN="$(tr -d '\n' < "${TOKEN_FILE}")"

# Keep the launchd runtime out of Desktop/Documents to avoid macOS privacy denials.
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '.pytest_cache/' \
  --exclude '__pycache__/' \
  --exclude '.DS_Store' \
  --exclude 'data/' \
  --exclude 'tests/' \
  --exclude 'image/' \
  "${PROJECT_ROOT}/" "${RUNTIME_ROOT}/"

if [[ ! -f "${DB_PATH}" && -f "${SOURCE_DB}" ]]; then
  cp "${SOURCE_DB}" "${DB_PATH}"
fi

if [[ ! -d "${RUNTIME_ROOT}/.venv" ]]; then
  python3 -m venv "${RUNTIME_ROOT}/.venv"
fi

"${RUNTIME_ROOT}/.venv/bin/pip" install -r "${RUNTIME_ROOT}/requirements.txt"

cat > "${ENV_FILE}" <<EOF
export KNOWLEDGE_PROJECT_ROOT="${PROJECT_ROOT}"
export KNOWLEDGE_RUNTIME_ROOT="${RUNTIME_ROOT}"
export KNOWLEDGE_DB_PATH="${DB_PATH}"
export KNOWLEDGE_HOST="${HOST}"
export KNOWLEDGE_PORT="${PORT}"
export KNOWLEDGE_API_TOKEN="${TOKEN}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL}"
export OLLAMA_MODEL="${OLLAMA_MODEL}"
EOF

cat > "${LAUNCH_SCRIPT}" <<EOF
#!/usr/bin/env bash

set -euo pipefail

ENV_FILE="${ENV_FILE}"

if [[ ! -f "\${ENV_FILE}" ]]; then
  echo "Missing \${ENV_FILE}. Run scripts/setup_center_machine.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "\${ENV_FILE}"

cd "\${KNOWLEDGE_RUNTIME_ROOT}"
exec "\${KNOWLEDGE_RUNTIME_ROOT}/.venv/bin/python" -m uvicorn app.main:app --host "\${KNOWLEDGE_HOST}" --port "\${KNOWLEDGE_PORT}"
EOF

chmod 700 "${LAUNCH_SCRIPT}"
chmod 600 "${ENV_FILE}" "${TOKEN_FILE}"

printf 'Center machine env is ready.\n'
printf 'Project root: %s\n' "${PROJECT_ROOT}"
printf 'Runtime root: %s\n' "${RUNTIME_ROOT}"
printf 'Database path: %s\n' "${DB_PATH}"
printf 'Port: %s\n' "${PORT}"
printf 'Env file: %s\n' "${ENV_FILE}"
printf 'API token file: %s\n' "${TOKEN_FILE}"
printf 'Launch script: %s\n' "${LAUNCH_SCRIPT}"
printf 'Run the server: %s\n' "${PROJECT_ROOT}/scripts/run_center_server.sh"
