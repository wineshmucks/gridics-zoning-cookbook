#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <aws-region>" >&2
  exit 1
fi

AWS_REGION="$1"

aws secretsmanager create-secret \
  --region "${AWS_REGION}" \
  --name "uzone/clerk-publishable" \
  --secret-string "pk_live_or_pk_test_replace_me"

aws secretsmanager create-secret \
  --region "${AWS_REGION}" \
  --name "uzone/clerk-secret" \
  --secret-string "sk_live_or_sk_test_replace_me"

aws ssm put-parameter \
  --region "${AWS_REGION}" \
  --name "/uzone/gridics-org-id" \
  --type String \
  --value "org_replace_me" \
  --overwrite

# Optional integrations:
aws secretsmanager create-secret \
  --region "${AWS_REGION}" \
  --name "uzone/stripe-secret" \
  --secret-string "sk_live_replace_me"

aws secretsmanager create-secret \
  --region "${AWS_REGION}" \
  --name "uzone/stripe-webhook" \
  --secret-string "whsec_replace_me"

aws secretsmanager create-secret \
  --region "${AWS_REGION}" \
  --name "uzone/resend" \
  --secret-string "re_replace_me"
