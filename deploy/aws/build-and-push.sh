#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "usage: $0 <aws-region> <backend-repo-url> <frontend-repo-url> [image-tag]" >&2
  exit 1
fi

AWS_REGION="$1"
BACKEND_REPO_URL="$2"
FRONTEND_REPO_URL="$3"
IMAGE_TAG="${4:-latest}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UZONE_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -z "${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}" ]]; then
  echo "missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY for frontend build" >&2
  exit 1
fi

NEXT_PUBLIC_APP_VERSION="${NEXT_PUBLIC_APP_VERSION:-${IMAGE_TAG}}"
FORCE_NO_CACHE="${FORCE_NO_CACHE:-0}"

require_ecr_push_access() {
  local repo_url="$1"
  local repo_name="${repo_url##*/}"
  local registry="${repo_url%/*}"
  local account_id="${registry%%.dkr.ecr.*}"

  if ! aws ecr get-login-password --region "${AWS_REGION}" >/dev/null 2>&1; then
    echo "error: unable to get an ECR login token for ${registry}" >&2
    echo "hint: check AWS_PROFILE, AWS_REGION, and your AWS credentials" >&2
    exit 1
  fi

  if ! aws ecr describe-repositories \
    --region "${AWS_REGION}" \
    --registry-id "${account_id}" \
    --repository-names "${repo_name}" \
    >/dev/null 2>&1; then
    echo "error: repository ${repo_name} does not exist in ${registry}" >&2
    echo "hint: rerun deploy-from-env.sh so Terraform can recreate the missing ECR repository" >&2
    exit 1
  fi

  if ! aws ecr batch-check-layer-availability \
    --region "${AWS_REGION}" \
    --registry-id "${account_id}" \
    --repository-name "${repo_name}" \
    --layer-digests sha256:0000000000000000000000000000000000000000000000000000000000000000 \
    >/dev/null 2>&1; then
    echo "error: the current AWS identity does not appear to have ECR push access for ${repo_name}" >&2
    echo "hint: the principal needs ECR upload permissions such as BatchCheckLayerAvailability, InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, and PutImage" >&2
    exit 1
  fi
}

DEPLOY_DOCKER_CONFIG_CREATED=0
if [[ -z "${DOCKER_CONFIG:-}" ]]; then
  export DOCKER_CONFIG
  DOCKER_CONFIG="$(mktemp -d)"
  DEPLOY_DOCKER_CONFIG_CREATED=1
  printf '{ "auths": {} }\n' > "${DOCKER_CONFIG}/config.json"
fi

cleanup() {
  if [[ "${DEPLOY_DOCKER_CONFIG_CREATED}" == "1" && -n "${DOCKER_CONFIG:-}" && -d "${DOCKER_CONFIG}" ]]; then
    rm -rf "${DOCKER_CONFIG}"
  fi
}
trap cleanup EXIT

require_ecr_push_access "${BACKEND_REPO_URL}"
require_ecr_push_access "${FRONTEND_REPO_URL}"

echo "logging in to ECR for ${BACKEND_REPO_URL%/*}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${BACKEND_REPO_URL%/*}"

echo "building backend image ${BACKEND_REPO_URL}:${IMAGE_TAG}"
backend_build_args=(
  -f "${UZONE_DIR}/backend/Dockerfile.prod" \
  -t "${BACKEND_REPO_URL}:${IMAGE_TAG}" \
  "${UZONE_DIR}/backend"
)
if [[ "${FORCE_NO_CACHE}" == "1" ]]; then
  backend_build_args=(--no-cache "${backend_build_args[@]}")
fi
docker build "${backend_build_args[@]}"

echo "pushing backend image ${BACKEND_REPO_URL}:${IMAGE_TAG}"
docker push "${BACKEND_REPO_URL}:${IMAGE_TAG}"

echo "building frontend image ${FRONTEND_REPO_URL}:${IMAGE_TAG}"
frontend_build_args=(
  -f "${UZONE_DIR}/frontend/Dockerfile.prod" \
  --build-arg NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://localhost:8000}" \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}" \
  --build-arg NEXT_PUBLIC_CLERK_JWKS_URL="${NEXT_PUBLIC_CLERK_JWKS_URL:-}" \
  --build-arg NEXT_PUBLIC_APP_VERSION="${NEXT_PUBLIC_APP_VERSION}" \
  -t "${FRONTEND_REPO_URL}:${IMAGE_TAG}" \
  "${UZONE_DIR}/frontend"
)
if [[ "${FORCE_NO_CACHE}" == "1" ]]; then
  frontend_build_args=(--no-cache "${frontend_build_args[@]}")
fi
docker build "${frontend_build_args[@]}"

echo "pushing frontend image ${FRONTEND_REPO_URL}:${IMAGE_TAG}"
docker push "${FRONTEND_REPO_URL}:${IMAGE_TAG}"
