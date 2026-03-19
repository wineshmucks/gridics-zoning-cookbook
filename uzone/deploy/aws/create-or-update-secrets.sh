#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")}"

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

if [[ -n "${UZONE_STRIPE_SECRET_KEY:-}" ]]; then
  put_secret "uzone/stripe-secret" "${UZONE_STRIPE_SECRET_KEY}"
fi

if [[ -n "${UZONE_STRIPE_WEBHOOK_SECRET:-}" ]]; then
  put_secret "uzone/stripe-webhook" "${UZONE_STRIPE_WEBHOOK_SECRET}"
fi

if [[ -n "${UZONE_RESEND_API_KEY:-}" ]]; then
  put_secret "uzone/resend-api-key" "${UZONE_RESEND_API_KEY}"
fi

if [[ -n "${UZONE_ZONING_EMBEDDER_API_KEY:-}" ]]; then
  put_secret "uzone/zoning-embedder-api-key" "${UZONE_ZONING_EMBEDDER_API_KEY}"
fi

if [[ -n "${UZONE_ZONING_AGENT_LLM_API_KEY:-}" ]]; then
  put_secret "uzone/zoning-agent-llm-api-key" "${UZONE_ZONING_AGENT_LLM_API_KEY}"
fi

if [[ -n "${GOOGLE_API_KEY:-}" ]]; then
  put_secret "uzone/google-api-key" "${GOOGLE_API_KEY}"
fi

if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
  put_secret "uzone/openrouter-api-key" "${OPENROUTER_API_KEY}"
fi

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  put_secret "uzone/openai-api-key" "${OPENAI_API_KEY}"
fi

if [[ -n "${GROQ_API_KEY:-}" ]]; then
  put_secret "uzone/groq-api-key" "${GROQ_API_KEY}"
fi

if [[ -n "${GRIDICS_API_KEY:-}" ]]; then
  put_secret "uzone/gridics-api-key" "${GRIDICS_API_KEY}"
fi

if [[ -n "${GRIDICS_CONSUMER_KEY:-}" ]]; then
  put_secret "uzone/gridics-consumer-key" "${GRIDICS_CONSUMER_KEY}"
fi

if [[ -n "${GRIDICS_CONSUMER_SECRET:-}" ]]; then
  put_secret "uzone/gridics-consumer-secret" "${GRIDICS_CONSUMER_SECRET}"
fi

cat <<EOF
secret arns:
arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/clerk-publishable
arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/clerk-secret
$(if [[ -n "${UZONE_STRIPE_SECRET_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/stripe-secret"; fi)
$(if [[ -n "${UZONE_STRIPE_WEBHOOK_SECRET:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/stripe-webhook"; fi)
$(if [[ -n "${UZONE_RESEND_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/resend-api-key"; fi)
$(if [[ -n "${UZONE_ZONING_EMBEDDER_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/zoning-embedder-api-key"; fi)
$(if [[ -n "${UZONE_ZONING_AGENT_LLM_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/zoning-agent-llm-api-key"; fi)
$(if [[ -n "${GOOGLE_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/google-api-key"; fi)
$(if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/openrouter-api-key"; fi)
$(if [[ -n "${OPENAI_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/openai-api-key"; fi)
$(if [[ -n "${GROQ_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/groq-api-key"; fi)
$(if [[ -n "${GRIDICS_API_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/gridics-api-key"; fi)
$(if [[ -n "${GRIDICS_CONSUMER_KEY:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/gridics-consumer-key"; fi)
$(if [[ -n "${GRIDICS_CONSUMER_SECRET:-}" ]]; then echo "arn:aws:secretsmanager:${AWS_REGION}:${ACCOUNT_ID}:secret:uzone/gridics-consumer-secret"; fi)
EOF
