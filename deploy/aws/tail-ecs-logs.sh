#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <staging|prod> [frontend|backend|both]" >&2
  exit 1
fi

ENVIRONMENT="$1"
TARGET="${2:-both}"
REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-default}"
PROJECT="${PROJECT:-gridics-uzone}"

case "${ENVIRONMENT}" in
  staging)
    ;;
  prod)
    ;;
  *)
    echo "error: environment must be staging or prod" >&2
    exit 1
    ;;
esac

case "${TARGET}" in
  frontend|backend|both)
    ;;
  *)
    echo "error: target must be frontend, backend, or both" >&2
    exit 1
    ;;
esac

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "missing required command: ${name}" >&2
    exit 1
  fi
}

require_command aws

LOG_GROUP_FRONTEND="/ecs/${PROJECT}-${ENVIRONMENT}-frontend"
LOG_GROUP_BACKEND="/ecs/${PROJECT}-${ENVIRONMENT}-backend"

tail_one() {
  local label="$1"
  local log_group="$2"
  echo "tailing ${label}: ${log_group}"
  AWS_PROFILE="${PROFILE}" aws logs tail "${log_group}" --follow --since 30m --region "${REGION}"
}

if [[ "${TARGET}" == "frontend" ]]; then
  tail_one "frontend" "${LOG_GROUP_FRONTEND}"
  exit 0
fi

if [[ "${TARGET}" == "backend" ]]; then
  tail_one "backend" "${LOG_GROUP_BACKEND}"
  exit 0
fi

frontend_pid=""
backend_pid=""

cleanup() {
  if [[ -n "${frontend_pid}" ]]; then
    kill "${frontend_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${backend_pid}" ]]; then
    kill "${backend_pid}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

tail_one "frontend" "${LOG_GROUP_FRONTEND}" &
frontend_pid="$!"
tail_one "backend" "${LOG_GROUP_BACKEND}" &
backend_pid="$!"

wait
