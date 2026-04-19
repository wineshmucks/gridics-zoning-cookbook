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
TERRAFORM_WORKSPACE_OVERRIDE="${TERRAFORM_WORKSPACE:-}"
APP_ALLOWED_ORIGINS_OVERRIDE="${APP_ALLOWED_ORIGINS_OVERRIDE:-}"
DB_USERNAME_OVERRIDE="${DB_USERNAME_OVERRIDE:-}"
DB_PASSWORD_OVERRIDE="${DB_PASSWORD_OVERRIDE:-}"
DB_NAME_OVERRIDE="${DB_NAME_OVERRIDE:-}"
DB_ENGINE_VERSION="${UZONE_DB_ENGINE_VERSION:-16.13}"
CERTIFICATE_ARN_OVERRIDE="${CERTIFICATE_ARN_OVERRIDE:-}"
SKIP_TERRAFORM_APPLY="${SKIP_TERRAFORM_APPLY:-0}"
SKIP_IMAGE_PUSH="${SKIP_IMAGE_PUSH:-0}"
SMOKE_TEST_TIMEOUT_SECONDS="${SMOKE_TEST_TIMEOUT_SECONDS:-180}"
SMOKE_TEST_BASE_URL="${SMOKE_TEST_BASE_URL:-}"
UZONE_PUBLIC_BASE_URL="${UZONE_PUBLIC_BASE_URL:-}"
AGENTIC_PUBLIC_BASE_URL="${AGENTIC_PUBLIC_BASE_URL:-${UZONE_PUBLIC_BASE_URL:-}}"
LETTERS_PUBLIC_BASE_URL="${LETTERS_PUBLIC_BASE_URL:-}"

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

emit_list_if_set() {
  local key="$1"
  local value="${2:-}"
  if [[ -z "${value}" ]]; then
    return
  fi

  IFS=',' read -r -a parts <<< "${value}"
  printf '  %s = [\n' "${key}"
  for part in "${parts[@]}"; do
    local trimmed="${part#"${part%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    if [[ -n "${trimmed}" ]]; then
      printf '    %s,\n' "$(escape_hcl_string "${trimmed}")"
    fi
  done
  printf '  ]\n'
}

emit_bool() {
  local key="$1"
  local value="${2:-false}"
  printf '  %s = %s\n' "${key}" "${value}"
}

emit_secret_arn_if_set() {
  local key="$1"
  local secret_name="$2"
  local value="${3:-}"
  if [[ -n "${value}" ]]; then
    printf '  %s = %s\n' "${key}" "$(escape_hcl_string "$(resolve_secret_arn "${secret_name}")")"
  fi
}

read_existing_tfvars_string() {
  local key="$1"

  if [[ ! -f "${TFVARS_PATH}" ]]; then
    return
  fi

  sed -nE "s/^${key}[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$/\\1/p" "${TFVARS_PATH}" | head -n 1
}

validate_elb_arn() {
  local label="$1"
  local arn="$2"

  if [[ -z "${arn}" ]]; then
    return 0
  fi

  if [[ "${arn}" =~ ^arn:aws:elasticloadbalancing:([^:]+):([0-9]{12}): ]]; then
    local arn_region="${BASH_REMATCH[1]}"
    local arn_account="${BASH_REMATCH[2]}"

    if [[ "${arn_region}" != "${AWS_REGION}" ]]; then
      echo "error: ${label} region ${arn_region} does not match AWS_REGION=${AWS_REGION}" >&2
      exit 1
    fi

    if [[ "${arn_account}" != "${ACCOUNT_ID}" ]]; then
      echo "error: ${label} account ${arn_account} does not match the active AWS account ${ACCOUNT_ID}" >&2
      echo "hint: switch AWS_PROFILE or update ${label} to an ARN that exists in the current account" >&2
      exit 1
    fi

    return 0
  fi

  echo "error: ${label} must be a valid ELB ARN" >&2
  exit 1
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
require_command curl

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

TAG_ENV="${UZONE_TAG_ENV:-}"
TAG_NAME="${UZONE_TAG_NAME:-}"

if [[ -z "${AWS_PROFILE:-}" ]]; then
  echo "error: AWS_PROFILE must be set in ${ENV_FILE}; refusing to fall back to the default profile" >&2
  exit 1
fi

if [[ "${AWS_PROFILE}" == "default" ]]; then
  echo "error: AWS_PROFILE=default is not allowed for deploys in this workspace" >&2
  echo "hint: use the staging profile that targets account 460508179634" >&2
  exit 1
fi

if [[ -z "${TAG_ENV}" ]]; then
  echo "error: UZONE_TAG_ENV must be set in ${ENV_FILE}" >&2
  exit 1
fi

if [[ -z "${TAG_NAME}" ]]; then
  echo "error: UZONE_TAG_NAME must be set in ${ENV_FILE}" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text --region "${AWS_REGION}")"
BACKEND_REPOSITORY_NAME="${PROJECT}-${DEPLOY_ENVIRONMENT}-backend"
FRONTEND_REPOSITORY_NAME="${PROJECT}-${DEPLOY_ENVIRONMENT}-frontend"

APP_ALLOWED_ORIGINS="${APP_ALLOWED_ORIGINS_OVERRIDE:-${UZONE_ALLOWED_ORIGINS:-http://localhost:3001,http://127.0.0.1:3001}}"
DB_USERNAME="${DB_USERNAME_OVERRIDE:-${POSTGRES_USER:-uzone}}"
DB_PASSWORD="${DB_PASSWORD_OVERRIDE:-${POSTGRES_PASSWORD:-postgres}}"
DB_NAME="${DB_NAME_OVERRIDE:-${POSTGRES_DB:-uzone}}"
EXISTING_CERTIFICATE_ARN="$(read_existing_tfvars_string "certificate_arn")"
CERTIFICATE_ARN="${CERTIFICATE_ARN_OVERRIDE:-${UZONE_AWS_CERTIFICATE_ARN:-${EXISTING_CERTIFICATE_ARN}}}"
REQUIRE_AGENT_OS="${UZONE_REQUIRE_AGENT_OS:-true}"
USE_EXISTING_VPC="${UZONE_USE_EXISTING_VPC:-false}"
USE_EXISTING_ALB="${UZONE_USE_EXISTING_ALB:-false}"
EXISTING_VPC_ID="${UZONE_EXISTING_VPC_ID:-}"
EXISTING_PUBLIC_SUBNET_IDS="${UZONE_EXISTING_PUBLIC_SUBNET_IDS:-}"
EXISTING_PRIVATE_SUBNET_IDS="${UZONE_EXISTING_PRIVATE_SUBNET_IDS:-}"
EXISTING_ALB_ARN="${UZONE_EXISTING_ALB_ARN:-}"
EXISTING_ALB_HTTP_LISTENER_ARN="${UZONE_EXISTING_ALB_HTTP_LISTENER_ARN:-}"
EXISTING_ALB_HTTPS_LISTENER_ARN="${UZONE_EXISTING_ALB_HTTPS_LISTENER_ARN:-}"
EXISTING_ALB_HOST_HEADER="${UZONE_EXISTING_ALB_HOST_HEADER:-}"
EXISTING_ALB_FRONTEND_RULE_PRIORITY="${UZONE_EXISTING_ALB_FRONTEND_RULE_PRIORITY:-110}"
EXISTING_ALB_API_RULE_PRIORITY="${UZONE_EXISTING_ALB_API_RULE_PRIORITY:-100}"
ASSETS_BUCKET_NAME="${UZONE_ASSETS_BUCKET_NAME:-gridics-uzones}"

if [[ "${USE_EXISTING_ALB}" == "true" ]]; then
  validate_elb_arn "existing_alb_arn" "${EXISTING_ALB_ARN}"
  validate_elb_arn "existing_alb_http_listener_arn" "${EXISTING_ALB_HTTP_LISTENER_ARN}"
  validate_elb_arn "existing_alb_https_listener_arn" "${EXISTING_ALB_HTTPS_LISTENER_ARN}"
fi

wait_for_expected_status() {
  local url="$1"
  local expected_status="$2"
  local timeout_seconds="$3"
  local host_header="${4:-}"
  local start_time
  start_time="$(date +%s)"

  while true; do
    local status
    if [[ -n "${host_header}" ]]; then
      status="$(curl -s -o /tmp/uzone_smoke_response.txt -w '%{http_code}' -H "Host: ${host_header}" "${url}" || true)"
    else
      status="$(curl -s -o /tmp/uzone_smoke_response.txt -w '%{http_code}' "${url}" || true)"
    fi
    if [[ "${status}" == "${expected_status}" ]]; then
      return 0
    fi
    if (( $(date +%s) - start_time >= timeout_seconds )); then
      echo "smoke check failed for ${url}: expected ${expected_status}, got ${status}" >&2
      cat /tmp/uzone_smoke_response.txt >&2 || true
      return 1
    fi
    sleep 5
  done
}

resolve_smoke_test_base_url() {
  local alb_dns_name="$1"

  if [[ -n "${SMOKE_TEST_BASE_URL}" ]]; then
    printf '%s' "${SMOKE_TEST_BASE_URL%/}"
    return
  fi

  if [[ -n "${AGENTIC_PUBLIC_BASE_URL}" ]]; then
    printf '%s' "${AGENTIC_PUBLIC_BASE_URL%/}"
    return
  fi

  if [[ -n "${UZONE_PUBLIC_BASE_URL}" ]]; then
    printf '%s' "${UZONE_PUBLIC_BASE_URL%/}"
    return
  fi

  if [[ -n "${CERTIFICATE_ARN}" ]]; then
    if [[ "${DEPLOY_ENVIRONMENT}" == "prod" ]]; then
      printf 'https://uzones.dev'
    else
      printf 'https://%s' "${alb_dns_name}"
    fi
    return
  fi

  printf 'http://%s' "${alb_dns_name}"
}

warn_if_prod_without_certificate() {
  if [[ "${DEPLOY_ENVIRONMENT}" == "prod" && -z "${CERTIFICATE_ARN}" ]]; then
    cat >&2 <<'EOF'
warning: deploying prod without certificate_arn
- HTTPS listener will not be created
- smoke tests will use the ALB HTTP URL
- Clerk and custom-domain production flows may not work correctly until ACM is configured
EOF
  fi
}

mkdir -p "${TF_DIR}"

export AWS_REGION
"${SCRIPT_DIR}/create-or-update-secrets.sh"
warn_if_prod_without_certificate

cat > "${TFVARS_PATH}" <<EOF
aws_region          = $(escape_hcl_string "${AWS_REGION}")
project             = $(escape_hcl_string "${PROJECT}")
environment         = $(escape_hcl_string "${DEPLOY_ENVIRONMENT}")
tag_env             = $(escape_hcl_string "${TAG_ENV}")
tag_name            = $(escape_hcl_string "${TAG_NAME}")
app_allowed_origins = $(escape_hcl_string "${APP_ALLOWED_ORIGINS}")
$(emit_bool "use_existing_vpc" "${USE_EXISTING_VPC}")
$(emit_bool "use_existing_alb" "${USE_EXISTING_ALB}")
existing_vpc_id     = $(escape_hcl_string "${EXISTING_VPC_ID}")
$(emit_list_if_set "existing_public_subnet_ids" "${EXISTING_PUBLIC_SUBNET_IDS}")
$(emit_list_if_set "existing_private_subnet_ids" "${EXISTING_PRIVATE_SUBNET_IDS}")
existing_alb_arn                = $(escape_hcl_string "${EXISTING_ALB_ARN}")
existing_alb_http_listener_arn  = $(escape_hcl_string "${EXISTING_ALB_HTTP_LISTENER_ARN}")
existing_alb_https_listener_arn = $(escape_hcl_string "${EXISTING_ALB_HTTPS_LISTENER_ARN}")
existing_alb_host_header        = $(escape_hcl_string "${EXISTING_ALB_HOST_HEADER}")
existing_alb_frontend_rule_priority = ${EXISTING_ALB_FRONTEND_RULE_PRIORITY}
existing_alb_api_rule_priority      = ${EXISTING_ALB_API_RULE_PRIORITY}
assets_bucket_name  = $(escape_hcl_string "${ASSETS_BUCKET_NAME}")
public_base_url     = $(escape_hcl_string "${UZONE_PUBLIC_BASE_URL}")

db_username = $(escape_hcl_string "${DB_USERNAME}")
db_password = $(escape_hcl_string "${DB_PASSWORD}")
db_name     = $(escape_hcl_string "${DB_NAME}")
db_engine_version = $(escape_hcl_string "${DB_ENGINE_VERSION}")

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
$(emit_kv_if_set "UZONE_REQUIRE_AGENT_OS" "${REQUIRE_AGENT_OS}")
$(emit_kv_if_set "UZONE_ZONING_AGENT_LLM_PROVIDER" "${UZONE_ZONING_AGENT_LLM_PROVIDER:-}")
$(emit_kv_if_set "UZONE_ZONING_AGENT_LLM_MODEL_ID" "${UZONE_ZONING_AGENT_LLM_MODEL_ID:-}")
$(emit_kv_if_set "GRIDICS_CLERK_ORGANIZATION_SLUG" "${GRIDICS_CLERK_ORGANIZATION_SLUG:-}")
}

frontend_environment = {
$(emit_kv_if_set "GRIDICS_CLERK_ORGANIZATION_SLUG" "${GRIDICS_CLERK_ORGANIZATION_SLUG:-}")
$(emit_kv_if_set "AGENTIC_PUBLIC_BASE_URL" "${AGENTIC_PUBLIC_BASE_URL:-}")
$(emit_kv_if_set "LETTERS_PUBLIC_BASE_URL" "${LETTERS_PUBLIC_BASE_URL:-}")
$(emit_kv_if_set "NEXT_PUBLIC_AGENTIC_PUBLIC_BASE_URL" "${AGENTIC_PUBLIC_BASE_URL:-}")
$(emit_kv_if_set "NEXT_PUBLIC_LETTERS_PUBLIC_BASE_URL" "${LETTERS_PUBLIC_BASE_URL:-}")
}

backend_secret_arns = {
$(emit_secret_arn_if_set "CLERK_SECRET_KEY" "uzone/clerk-secret" "${CLERK_SECRET_KEY:-}")
$(emit_secret_arn_if_set "UZONE_STRIPE_SECRET_KEY" "uzone/stripe-secret" "${UZONE_STRIPE_SECRET_KEY:-}")
$(emit_secret_arn_if_set "UZONE_STRIPE_WEBHOOK_SECRET" "uzone/stripe-webhook" "${UZONE_STRIPE_WEBHOOK_SECRET:-}")
$(emit_secret_arn_if_set "UZONE_RESEND_API_KEY" "uzone/resend-api-key" "${UZONE_RESEND_API_KEY:-}")
$(emit_secret_arn_if_set "UZONE_MANDRILL_API_KEY" "uzone/mandrill-api-key" "${UZONE_MANDRILL_API_KEY:-}")
$(emit_secret_arn_if_set "UZONE_ZONING_EMBEDDER_API_KEY" "uzone/zoning-embedder-api-key" "${UZONE_ZONING_EMBEDDER_API_KEY:-}")
$(emit_secret_arn_if_set "UZONE_ZONING_AGENT_LLM_API_KEY" "uzone/zoning-agent-llm-api-key" "${UZONE_ZONING_AGENT_LLM_API_KEY:-}")
$(emit_secret_arn_if_set "GOOGLE_API_KEY" "uzone/google-api-key" "${GOOGLE_API_KEY:-}")
$(emit_secret_arn_if_set "OPENROUTER_API_KEY" "uzone/openrouter-api-key" "${OPENROUTER_API_KEY:-}")
$(emit_secret_arn_if_set "OPENAI_API_KEY" "uzone/openai-api-key" "${OPENAI_API_KEY:-}")
$(emit_secret_arn_if_set "GROQ_API_KEY" "uzone/groq-api-key" "${GROQ_API_KEY:-}")
$(emit_secret_arn_if_set "GRIDICS_API_KEY" "uzone/gridics-api-key" "${GRIDICS_API_KEY:-}")
$(emit_secret_arn_if_set "GRIDICS_CONSUMER_KEY" "uzone/gridics-consumer-key" "${GRIDICS_CONSUMER_KEY:-}")
$(emit_secret_arn_if_set "GRIDICS_CONSUMER_SECRET" "uzone/gridics-consumer-secret" "${GRIDICS_CONSUMER_SECRET:-}")
$(emit_secret_arn_if_set "UZONE_EMBED_SESSION_SIGNING_SECRET" "uzone/embed-session-signing-secret" "${UZONE_EMBED_SESSION_SIGNING_SECRET:-}")
}

frontend_secret_arns = {
$(emit_secret_arn_if_set "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" "uzone/clerk-publishable" "${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}")
$(emit_secret_arn_if_set "CLERK_SECRET_KEY" "uzone/clerk-secret" "${CLERK_SECRET_KEY:-}")
}
EOF

echo "generated ${TFVARS_PATH}"

cd "${TF_DIR}"
terraform init

EXPECTED_TERRAFORM_WORKSPACE="${DEPLOY_ENVIRONMENT}-${ACCOUNT_ID}"
if [[ -n "${TERRAFORM_WORKSPACE_OVERRIDE}" && "${TERRAFORM_WORKSPACE_OVERRIDE}" != "${EXPECTED_TERRAFORM_WORKSPACE}" ]]; then
  echo "error: TERRAFORM_WORKSPACE=${TERRAFORM_WORKSPACE_OVERRIDE} does not match the expected workspace ${EXPECTED_TERRAFORM_WORKSPACE}" >&2
  echo "hint: unset TERRAFORM_WORKSPACE or set it to the expected workspace before rerunning" >&2
  exit 1
fi

TERRAFORM_WORKSPACE="${EXPECTED_TERRAFORM_WORKSPACE}"

if terraform workspace select "${TERRAFORM_WORKSPACE}" >/dev/null 2>&1; then
  echo "selected terraform workspace: ${TERRAFORM_WORKSPACE}"
else
  terraform workspace new "${TERRAFORM_WORKSPACE}" >/dev/null
  echo "created terraform workspace: ${TERRAFORM_WORKSPACE}"
fi

ensure_ecr_repository_in_state() {
  local address="$1"
  local repository_name="$2"

  if terraform state show "${address}" >/dev/null 2>&1; then
    if aws ecr describe-repositories --region "${AWS_REGION}" --repository-names "${repository_name}" >/dev/null 2>&1; then
      return
    fi

    echo "stale Terraform state detected for ${repository_name}; removing and recreating it"
    terraform state rm "${address}" >/dev/null
  fi

  if aws ecr describe-repositories --region "${AWS_REGION}" --repository-names "${repository_name}" >/dev/null 2>&1; then
    echo "importing existing ECR repository ${repository_name} into Terraform state"
    terraform import "${address}" "${repository_name}"
  fi
}

ensure_ecr_repository_in_state "aws_ecr_repository.backend" "${BACKEND_REPOSITORY_NAME}"
ensure_ecr_repository_in_state "aws_ecr_repository.frontend" "${FRONTEND_REPOSITORY_NAME}"

TARGET_VPC_ID="${EXISTING_VPC_ID:-}"
if [[ -z "${TARGET_VPC_ID}" && "${USE_EXISTING_VPC}" == "true" && -n "${EXISTING_ALB_ARN}" ]]; then
  TARGET_VPC_ID="$(aws elbv2 describe-load-balancers \
    --region "${AWS_REGION}" \
    --load-balancer-arns "${EXISTING_ALB_ARN}" \
    --query 'LoadBalancers[0].VpcId' \
    --output text)"
fi

import_if_missing() {
  local address="$1"
  local import_id="$2"
  shift 2

  if terraform state show "${address}" >/dev/null 2>&1; then
    return
  fi

  local probe
  probe="$("$@" 2>/dev/null || true)"
  if [[ -n "${probe}" && "${probe}" != "None" && "${probe}" != "[]" ]]; then
    echo "importing existing ${address}"
    terraform import "${address}" "${import_id}"
  fi
}

state_attr_value() {
  local address="$1"
  local attr="$2"

  terraform state show "${address}" 2>/dev/null | sed -nE "s/^${attr}[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$/\\1/p" | head -n 1
}

remove_state_if_present() {
  local address="$1"

  if terraform state show "${address}" >/dev/null 2>&1; then
    terraform state rm "${address}" >/dev/null
  fi
}

remove_stale_named_state_if_needed() {
  local address="$1"
  local attr="$2"
  local expected_name="$3"

  if ! terraform state show "${address}" >/dev/null 2>&1; then
    return
  fi

  local current_name
  current_name="$(state_attr_value "${address}" "${attr}")"
  if [[ -n "${current_name}" && "${current_name}" != "${expected_name}" ]]; then
    echo "stale Terraform state detected for ${address}: ${attr}=${current_name}; expected ${expected_name}. removing from state"
    terraform state rm "${address}" >/dev/null
  fi
}

import_named_log_group() {
  local address="$1"
  local log_group_name="$2"

  import_if_missing "${address}" "${log_group_name}" aws logs describe-log-groups \
    --region "${AWS_REGION}" \
    --log-group-name-prefix "${log_group_name}" \
    --query "logGroups[?logGroupName=='${log_group_name}'].logGroupName | [0]" \
    --output text
}

import_security_group() {
  local address="$1"
  local group_name="$2"

  if [[ -z "${TARGET_VPC_ID}" ]]; then
    return
  fi

  local group_id
  group_id="$(aws ec2 describe-security-groups \
    --region "${AWS_REGION}" \
    --filters "Name=vpc-id,Values=${TARGET_VPC_ID}" "Name=group-name,Values=${group_name}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || true)"

  if [[ -n "${group_id}" && "${group_id}" != "None" ]]; then
    import_if_missing "${address}" "${group_id}" aws ec2 describe-security-groups \
      --region "${AWS_REGION}" \
      --filters "Name=vpc-id,Values=${TARGET_VPC_ID}" "Name=group-name,Values=${group_name}" \
      --query 'SecurityGroups[0].GroupId' \
      --output text
  fi
}

import_target_group() {
  local address="$1"
  local target_group_name="$2"

  local target_group_arn
  target_group_arn="$(aws elbv2 describe-target-groups \
    --region "${AWS_REGION}" \
    --names "${target_group_name}" \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text 2>/dev/null || true)"

  if [[ -n "${target_group_arn}" && "${target_group_arn}" != "None" ]]; then
    import_if_missing "${address}" "${target_group_arn}" aws elbv2 describe-target-groups \
      --region "${AWS_REGION}" \
      --names "${target_group_name}" \
      --query 'TargetGroups[0].TargetGroupArn' \
      --output text
  fi
}

import_listener_rule() {
  local address="$1"
  local listener_arn="$2"
  local priority="$3"

  if [[ -z "${listener_arn}" ]]; then
    return
  fi

  local rule_arn
  rule_arn="$(aws elbv2 describe-rules \
    --region "${AWS_REGION}" \
    --listener-arn "${listener_arn}" \
    --query "Rules[?Priority=='${priority}'].RuleArn | [0]" \
    --output text 2>/dev/null || true)"

  if [[ -n "${rule_arn}" && "${rule_arn}" != "None" ]]; then
    import_if_missing "${address}" "${rule_arn}" aws elbv2 describe-rules \
      --region "${AWS_REGION}" \
      --listener-arn "${listener_arn}" \
      --query "Rules[?Priority=='${priority}'].RuleArn | [0]" \
      --output text
  fi
}

import_db_subnet_group() {
  local address="$1"
  local name="$2"

  import_if_missing "${address}" "${name}" aws rds describe-db-subnet-groups \
    --region "${AWS_REGION}" \
    --db-subnet-group-name "${name}" \
    --query 'DBSubnetGroups[0].DBSubnetGroupName' \
    --output text
}

import_db_instance() {
  local address="$1"
  local identifier="$2"

  import_if_missing "${address}" "${identifier}" aws rds describe-db-instances \
    --region "${AWS_REGION}" \
    --db-instance-identifier "${identifier}" \
    --query 'DBInstances[0].DBInstanceIdentifier' \
    --output text
}

import_bucket() {
  local address="$1"
  local bucket_name="$2"

  local current_bucket_name
  current_bucket_name="$(state_attr_value "${address}" "bucket")"
  if [[ -n "${current_bucket_name}" && "${current_bucket_name}" != "${bucket_name}" ]]; then
    echo "stale Terraform state detected for ${address}: bucket=${current_bucket_name}; expected ${bucket_name}. removing S3 resources from state"
    remove_state_if_present "aws_s3_bucket_public_access_block.logo_assets"
    remove_state_if_present "aws_s3_bucket_versioning.logo_assets"
    remove_state_if_present "aws_s3_bucket_server_side_encryption_configuration.logo_assets"
    remove_state_if_present "${address}"
  fi

  if aws s3api head-bucket --bucket "${bucket_name}" >/dev/null 2>&1; then
    if ! terraform state show "${address}" >/dev/null 2>&1; then
      echo "importing existing ${address}"
      terraform import "${address}" "${bucket_name}"
    fi
  fi
}

import_iam_role() {
  local address="$1"
  local role_name="$2"

  import_if_missing "${address}" "${role_name}" aws iam get-role \
    --role-name "${role_name}" \
    --query 'Role.RoleName' \
    --output text
}

import_ecs_cluster() {
  local address="$1"
  local cluster_name="$2"

  remove_stale_named_state_if_needed "${address}" "name" "${cluster_name}"

  import_if_missing "${address}" "${cluster_name}" aws ecs describe-clusters \
    --region "${AWS_REGION}" \
    --clusters "${cluster_name}" \
    --query 'clusters[0].clusterArn' \
    --output text
}

import_ecs_service() {
  local address="$1"
  local cluster_name="$2"
  local service_name="$3"

  local service_status
  service_status="$(aws ecs describe-services \
    --region "${AWS_REGION}" \
    --cluster "${cluster_name}" \
    --services "${service_name}" \
    --query 'services[0].status' \
    --output text 2>/dev/null || true)"

  if [[ "${service_status}" == "ACTIVE" ]]; then
    import_if_missing "${address}" "${cluster_name}/${service_name}" aws ecs describe-services \
      --region "${AWS_REGION}" \
      --cluster "${cluster_name}" \
      --services "${service_name}" \
      --query 'services[0].serviceArn' \
      --output text
  elif [[ "${service_status}" == "INACTIVE" ]]; then
    echo "skipping import for inactive ECS service ${cluster_name}/${service_name}; Terraform will recreate it if needed"
  fi
}

bootstrap_existing_resources() {
  import_db_subnet_group "aws_db_subnet_group.postgres" "${PROJECT}-${DEPLOY_ENVIRONMENT}-db-subnets"
  import_db_instance "aws_db_instance.postgres" "${PROJECT}-${DEPLOY_ENVIRONMENT}-postgres"

  if [[ "${USE_EXISTING_ALB}" != "true" ]]; then
    import_security_group "aws_security_group.alb[0]" "${PROJECT}-${DEPLOY_ENVIRONMENT}-alb"
  fi
  import_security_group "aws_security_group.frontend" "${PROJECT}-${DEPLOY_ENVIRONMENT}-frontend"
  import_security_group "aws_security_group.backend" "${PROJECT}-${DEPLOY_ENVIRONMENT}-backend"
  import_security_group "aws_security_group.postgres" "${PROJECT}-${DEPLOY_ENVIRONMENT}-postgres"

  import_named_log_group "aws_cloudwatch_log_group.backend" "/ecs/${PROJECT}-${DEPLOY_ENVIRONMENT}-backend"
  import_named_log_group "aws_cloudwatch_log_group.frontend" "/ecs/${PROJECT}-${DEPLOY_ENVIRONMENT}-frontend"

  import_bucket "aws_s3_bucket.logo_assets" "${ASSETS_BUCKET_NAME}"

  import_iam_role "aws_iam_role.ecs_task_execution" "${PROJECT}-${DEPLOY_ENVIRONMENT}-ecs-execution"
  import_iam_role "aws_iam_role.ecs_task" "${PROJECT}-${DEPLOY_ENVIRONMENT}-ecs-task"

  import_ecs_cluster "aws_ecs_cluster.main" "${PROJECT}-${DEPLOY_ENVIRONMENT}-cluster"

  import_target_group "aws_lb_target_group.frontend" "${PROJECT}-${DEPLOY_ENVIRONMENT}-fe"
  import_target_group "aws_lb_target_group.backend" "${PROJECT}-${DEPLOY_ENVIRONMENT}-be"

  import_ecs_service "aws_ecs_service.backend" "${PROJECT}-${DEPLOY_ENVIRONMENT}-cluster" "${PROJECT}-${DEPLOY_ENVIRONMENT}-backend"
  import_ecs_service "aws_ecs_service.frontend" "${PROJECT}-${DEPLOY_ENVIRONMENT}-cluster" "${PROJECT}-${DEPLOY_ENVIRONMENT}-frontend"

  import_listener_rule "aws_lb_listener_rule.api_http_existing[0]" "${EXISTING_ALB_HTTP_LISTENER_ARN}" "${EXISTING_ALB_API_RULE_PRIORITY}"
  import_listener_rule "aws_lb_listener_rule.frontend_http_existing[0]" "${EXISTING_ALB_HTTP_LISTENER_ARN}" "${EXISTING_ALB_FRONTEND_RULE_PRIORITY}"
  import_listener_rule "aws_lb_listener_rule.api_https_existing[0]" "${EXISTING_ALB_HTTPS_LISTENER_ARN}" "${EXISTING_ALB_API_RULE_PRIORITY}"
  import_listener_rule "aws_lb_listener_rule.frontend_https_existing[0]" "${EXISTING_ALB_HTTPS_LISTENER_ARN}" "${EXISTING_ALB_FRONTEND_RULE_PRIORITY}"
}

bootstrap_existing_resources

backend_ecr_in_state=0
frontend_ecr_in_state=0
if terraform state show "aws_ecr_repository.backend" >/dev/null 2>&1; then
  backend_ecr_in_state=1
fi
if terraform state show "aws_ecr_repository.frontend" >/dev/null 2>&1; then
  frontend_ecr_in_state=1
fi

if [[ "${SKIP_TERRAFORM_APPLY}" != "1" ]]; then
  if [[ "${backend_ecr_in_state}" == "1" && "${frontend_ecr_in_state}" == "1" ]]; then
    echo "skipping targeted ECR apply because both repositories already exist in Terraform state"
  else
    terraform apply \
      -auto-approve \
      -target=aws_ecr_repository.backend \
      -target=aws_ecr_repository.frontend \
      -target=aws_internet_gateway.main \
      -target=aws_lb.app \
      -target=aws_lb_listener.http \
      -target=aws_lb_listener_rule.api_http \
      -target=aws_route_table.public \
      -target=aws_security_group.alb \
      -target=aws_vpc.main
  fi
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
  ALB_DNS_NAME="$(terraform output -raw alb_dns_name)"
  echo "alb_dns_name: ${ALB_DNS_NAME}"
  EFFECTIVE_SMOKE_TEST_BASE_URL="$(resolve_smoke_test_base_url "${ALB_DNS_NAME}")"
  echo "smoke_test_base_url: ${EFFECTIVE_SMOKE_TEST_BASE_URL}"
  SMOKE_TEST_HOST_HEADER=""
  if [[ "${USE_EXISTING_ALB}" == "true" && -z "${SMOKE_TEST_BASE_URL}" && -z "${UZONE_PUBLIC_BASE_URL}" ]]; then
    SMOKE_TEST_HOST_HEADER="${EXISTING_ALB_HOST_HEADER}"
  fi
  wait_for_expected_status "${EFFECTIVE_SMOKE_TEST_BASE_URL}/api/health" "200" "${SMOKE_TEST_TIMEOUT_SECONDS}" "${SMOKE_TEST_HOST_HEADER}"
  wait_for_expected_status "${EFFECTIVE_SMOKE_TEST_BASE_URL}/api/health/agent-os" "200" "${SMOKE_TEST_TIMEOUT_SECONDS}" "${SMOKE_TEST_HOST_HEADER}"
  wait_for_expected_status "${EFFECTIVE_SMOKE_TEST_BASE_URL}/api/agents/customer-zoning-agent/runs" "422" "${SMOKE_TEST_TIMEOUT_SECONDS}" "${SMOKE_TEST_HOST_HEADER}"
fi
