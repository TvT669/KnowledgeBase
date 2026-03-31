#!/usr/bin/env bash

set -euo pipefail

APP_SUPPORT_DIR="${HOME}/Library/Application Support/KnowledgeBase"
LAUNCH_SCRIPT="${APP_SUPPORT_DIR}/run_center_server.sh"

if [[ ! -x "${LAUNCH_SCRIPT}" ]]; then
  echo "Missing ${LAUNCH_SCRIPT}. Run scripts/setup_center_machine.sh first." >&2
  exit 1
fi

exec "${LAUNCH_SCRIPT}"
