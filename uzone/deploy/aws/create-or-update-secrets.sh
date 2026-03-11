#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="${ACCOUNT_ID:-012135905973}"

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "missing required environment variable: ${name}" >&2
    exit 1
  fi
}

put_secret() {
  local name="$1"
  local value="$2"

  if aws secretsmanager describe-secret --region "${AWS_REGION}" --secret-id "${name}" >/dev/null 2>&1; then
    aws secretsmanager put-secret-value \
      --region "${AWS_REGION}" \
      --secret-id "${name}" \
      --secret-string "${value}" >/dev/null
    echo "updated ${name}"
  else
    aws secretsmanager create-secret \
      --region "${AWS_REGION}" \
      --name "${name}" \
      --secret-string "${value}" >/dev/null
    echo "created ${name}"
  fi
}

require_var NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
require_var CLERK_SECRET_KEY

put_secret "uzone/clerk-publishable" "${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}"
put_secret "uzone/clerk-secret" "${CLERK_SECRET_KEY}"

cat <<EOF
secret arns:
arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/clerk-publishable
arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/clerk-secret
EOF
