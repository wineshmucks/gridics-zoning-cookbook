#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UZONE_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TF_DIR="${SCRIPT_DIR}/terraform"
ENV_FILE="${ENV_FILE:-${UZONE_DIR}/.env-deploy}"

AWS_REGION="${AWS_REGION:-${UZONE_AWS_REGION:-us-east-1}}"
PROJECT="${PROJECT:-uzone}"
DEPLOY_ENVIRONMENT="${DEPLOY_ENVIRONMENT:-prod}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
TFVARS_PATH="${TFVARS_PATH:-${TF_DIR}/terraform.tfvars}"
APP_ALLOWED_ORIGINS_OVERRIDE="${APP_ALLOWED_ORIGINS_OVERRIDE:-}"
DB_USERNAME_OVERRIDE="${DB_USERNAME_OVERRIDE:-}"
DB_PASSWORD_OVERRIDE="${DB_PASSWORD_OVERRIDE:-}"
CERTIFICATE_ARN_OVERRIDE="${CERTIFICATE_ARN_OVERRIDE:-}"
SKIP_TERRAFORM_APPLY="${SKIP_TERRAFORM_APPLY:-0}"
SKIP_IMAGE_PUSH="${SKIP_IMAGE_PUSH:-0}"

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "missing required command: ${name}" >&2
    exit 1
  fi
}

escape_hcl_string() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '"%s"' "${value}"
}

emit_kv_if_set() {
  local key="$1"
  local value="${2:-}"
  if [[ -n "${value}" ]]; then
    printf '  %s = %s\n' "${key}" "$(escape_hcl_string "${value}")"
  fi
}

emit_secret_arn_if_set() {
  local key="$1"
  local secret_name="$2"
  local value="${3:-}"
  if [[ -n "${value}" ]]; then
    printf '  %s = %s\n' "${key}" "$(escape_hcl_string "$(resolve_secret_arn "${secret_name}")")"
  fi
}

resolve_secret_arn() {
  local secret_name="$1"
  aws secretsmanager describe-secret \
    --region "${AWS_REGION}" \
    --secret-id "${secret_name}" \
    --query 'ARN' \
    --output text
}

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "env file not found: ${ENV_FILE}" >&2
  exit 1
fi

require_command aws
require_command terraform
require_command docker

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")"
BACKEND_REPOSITORY_NAME="${PROJECT}-${DEPLOY_ENVIRONMENT}-backend"
FRONTEND_REPOSITORY_NAME="${PROJECT}-${DEPLOY_ENVIRONMENT}-frontend"

APP_ALLOWED_ORIGINS="${APP_ALLOWED_ORIGINS_OVERRIDE:-${UZONE_ALLOWED_ORIGINS:-http://localhost:3001,http://127.0.0.1:3001}}"
DB_USERNAME="${DB_USERNAME_OVERRIDE:-${POSTGRES_USER:-uzone}}"
DB_PASSWORD="${DB_PASSWORD_OVERRIDE:-${POSTGRES_PASSWORD:-postgres}}"
CERTIFICATE_ARN="${CERTIFICATE_ARN_OVERRIDE:-}"

mkdir -p "${TF_DIR}"

export AWS_REGION
"${SCRIPT_DIR}/create-or-update-secrets.sh"

cat > "${TFVARS_PATH}" <<EOF
aws_region          = $(escape_hcl_string "${AWS_REGION}")
project             = $(escape_hcl_string "${PROJECT}")
environment         = $(escape_hcl_string "${DEPLOY_ENVIRONMENT}")
app_allowed_origins = $(escape_hcl_string "${APP_ALLOWED_ORIGINS}")

db_username = $(escape_hcl_string "${DB_USERNAME}")
db_password = $(escape_hcl_string "${DB_PASSWORD}")

backend_image_tag  = $(escape_hcl_string "${IMAGE_TAG}")
frontend_image_tag = $(escape_hcl_string "${IMAGE_TAG}")
certificate_arn    = $(escape_hcl_string "${CERTIFICATE_ARN}")

backend_environment = {
  UZONE_AUTH_PROVIDER = $(escape_hcl_string "${UZONE_AUTH_PROVIDER:-local}")
  UZONE_PAYMENT_PROVIDERS = $(escape_hcl_string "${UZONE_PAYMENT_PROVIDERS:-manual}")
  UZONE_DEFAULT_PAYMENT_PROVIDER = $(escape_hcl_string "${UZONE_DEFAULT_PAYMENT_PROVIDER:-manual}")
  UZONE_EMAIL_PROVIDER = $(escape_hcl_string "${UZONE_EMAIL_PROVIDER:-console}")
  UZONE_EMAIL_FROM = $(escape_hcl_string "${UZONE_EMAIL_FROM:-noreply@example.com}")
  UZONE_CLERK_JWKS_URL = $(escape_hcl_string "${UZONE_CLERK_JWKS_URL:-}")
  UZONE_CLERK_AUTHORIZED_PARTIES = $(escape_hcl_string "${UZONE_CLERK_AUTHORIZED_PARTIES:-${APP_ALLOWED_ORIGINS}}")
  UZONE_ARTIFACTS_DIR = $(escape_hcl_string "${UZONE_ARTIFACTS_DIR:-/app/artifacts}")
$(emit_kv_if_set "UZONE_ZONING_EMBEDDER_PROVIDER" "${UZONE_ZONING_EMBEDDER_PROVIDER:-}")
$(emit_kv_if_set "UZONE_ZONING_EMBEDDER_MODEL_ID" "${UZONE_ZONING_EMBEDDER_MODEL_ID:-}")
$(emit_kv_if_set "UZONE_ZONING_EMBEDDER_DIMENSIONS" "${UZONE_ZONING_EMBEDDER_DIMENSIONS:-}")
$(emit_kv_if_set "UZONE_ZONING_EMBEDDER_REQUESTS_PER_MINUTE" "${UZONE_ZONING_EMBEDDER_REQUESTS_PER_MINUTE:-}")
$(emit_kv_if_set "UZONE_ZONING_AGENT_LLM_PROVIDER" "${UZONE_ZONING_AGENT_LLM_PROVIDER:-}")
$(emit_kv_if_set "UZONE_ZONING_AGENT_LLM_MODEL_ID" "${UZONE_ZONING_AGENT_LLM_MODEL_ID:-}")
$(emit_kv_if_set "GRIDICS_CLERK_ORGANIZATION_SLUG" "${GRIDICS_CLERK_ORGANIZATION_SLUG:-}")
}

frontend_environment = {
$(emit_kv_if_set "GRIDICS_CLERK_ORGANIZATION_SLUG" "${GRIDICS_CLERK_ORGANIZATION_SLUG:-}")
}

backend_secret_arns = {
$(emit_secret_arn_if_set "CLERK_SECRET_KEY" "uzone/clerk-secret" "${CLERK_SECRET_KEY:-}")
$(emit_secret_arn_if_set "UZONE_STRIPE_SECRET_KEY" "uzone/stripe-secret" "${UZONE_STRIPE_SECRET_KEY:-}")
$(emit_secret_arn_if_set "UZONE_STRIPE_WEBHOOK_SECRET" "uzone/stripe-webhook" "${UZONE_STRIPE_WEBHOOK_SECRET:-}")
$(emit_secret_arn_if_set "UZONE_RESEND_API_KEY" "uzone/resend-api-key" "${UZONE_RESEND_API_KEY:-}")
$(emit_secret_arn_if_set "UZONE_ZONING_EMBEDDER_API_KEY" "uzone/zoning-embedder-api-key" "${UZONE_ZONING_EMBEDDER_API_KEY:-}")
$(emit_secret_arn_if_set "UZONE_ZONING_AGENT_LLM_API_KEY" "uzone/zoning-agent-llm-api-key" "${UZONE_ZONING_AGENT_LLM_API_KEY:-}")
$(emit_secret_arn_if_set "GRIDICS_API_KEY" "uzone/gridics-api-key" "${GRIDICS_API_KEY:-}")
$(emit_secret_arn_if_set "GRIDICS_CONSUMER_KEY" "uzone/gridics-consumer-key" "${GRIDICS_CONSUMER_KEY:-}")
$(emit_secret_arn_if_set "GRIDICS_CONSUMER_SECRET" "uzone/gridics-consumer-secret" "${GRIDICS_CONSUMER_SECRET:-}")
}

frontend_secret_arns = {
$(emit_secret_arn_if_set "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" "uzone/clerk-publishable" "${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}")
$(emit_secret_arn_if_set "CLERK_SECRET_KEY" "uzone/clerk-secret" "${CLERK_SECRET_KEY:-}")
}
EOF

echo "generated ${TFVARS_PATH}"

cd "${TF_DIR}"
terraform init

ensure_ecr_repository_in_state() {
  local address="$1"
  local repository_name="$2"

  if terraform state show "${address}" >/dev/null 2>&1; then
    return
  fi

  if aws ecr describe-repositories --region "${AWS_REGION}" --repository-names "${repository_name}" >/dev/null 2>&1; then
    echo "importing existing ECR repository ${repository_name} into Terraform state"
    terraform import "${address}" "${repository_name}"
  fi
}

ensure_ecr_repository_in_state "aws_ecr_repository.backend" "${BACKEND_REPOSITORY_NAME}"
ensure_ecr_repository_in_state "aws_ecr_repository.frontend" "${FRONTEND_REPOSITORY_NAME}"

if [[ "${SKIP_TERRAFORM_APPLY}" != "1" ]]; then
  terraform apply \
    -auto-approve \
    -target=aws_ecr_repository.backend \
    -target=aws_ecr_repository.frontend
fi

BACKEND_REPO_URL="$(terraform output -raw backend_ecr_repository_url)"
FRONTEND_REPO_URL="$(terraform output -raw frontend_ecr_repository_url)"

if [[ "${SKIP_IMAGE_PUSH}" != "1" ]]; then
  export NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}"
  "${SCRIPT_DIR}/build-and-push.sh" \
    "${AWS_REGION}" \
    "${BACKEND_REPO_URL}" \
    "${FRONTEND_REPO_URL}" \
    "${IMAGE_TAG}"
fi

if [[ "${SKIP_TERRAFORM_APPLY}" != "1" ]]; then
  terraform apply -auto-approve
  echo "alb_dns_name: $(terraform output -raw alb_dns_name)"
fi
