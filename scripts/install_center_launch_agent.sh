#!/usr/bin/env bash

set -euo pipefail

APP_SUPPORT_DIR="${HOME}/Library/Application Support/KnowledgeBase"
LOG_DIR="${HOME}/Library/Logs/KnowledgeBase"
PLIST_PATH="${HOME}/Library/LaunchAgents/com.bee.knowledgebase-center.plist"
RUN_SCRIPT="${APP_SUPPORT_DIR}/run_center_server.sh"
ENV_FILE="${APP_SUPPORT_DIR}/center.env"
LABEL="com.bee.knowledgebase-center"

mkdir -p "${APP_SUPPORT_DIR}" "${LOG_DIR}" "${HOME}/Library/LaunchAgents"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run scripts/setup_center_machine.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

if [[ ! -x "${RUN_SCRIPT}" ]]; then
  echo "Missing ${RUN_SCRIPT}. Run scripts/setup_center_machine.sh first." >&2
  exit 1
fi

existing_pid="$(lsof -nP -t -iTCP:"${KNOWLEDGE_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
if [[ -n "${existing_pid}" ]]; then
  existing_command="$(ps -p "${existing_pid}" -o command= 2>/dev/null || true)"
  if [[ "${existing_command}" != *"${APP_SUPPORT_DIR}/runtime/.venv/bin/python"* ]]; then
    printf 'Port %s is already in use by PID %s: %s\n' "${KNOWLEDGE_PORT}" "${existing_pid}" "${existing_command}" >&2
    printf 'Set KNOWLEDGE_PORT to another port and rerun scripts/setup_center_machine.sh.\n' >&2
    exit 1
  fi
fi

cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${RUN_SCRIPT}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>${KNOWLEDGE_RUNTIME_ROOT}</string>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/center.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/center.stderr.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/${UID}" "${PLIST_PATH}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID}" "${PLIST_PATH}"
launchctl kickstart -k "gui/${UID}/${LABEL}"

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:${KNOWLEDGE_PORT}/health" >/dev/null 2>&1; then
    printf 'LaunchAgent installed: %s\n' "${PLIST_PATH}"
    printf 'Health check: http://127.0.0.1:%s/health\n' "${KNOWLEDGE_PORT}"
    printf 'Logs: %s\n' "${LOG_DIR}"
    exit 0
  fi
  sleep 1
done

printf 'Center machine failed health check on port %s.\n' "${KNOWLEDGE_PORT}" >&2
launchctl print "gui/${UID}/${LABEL}" >&2 || true
tail -n 40 "${LOG_DIR}/center.stderr.log" >&2 || true
exit 1
