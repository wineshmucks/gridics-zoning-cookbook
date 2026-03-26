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

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${BACKEND_REPO_URL%/*}"

docker build \
  --no-cache \
  -f "${UZONE_DIR}/backend/Dockerfile.prod" \
  -t "${BACKEND_REPO_URL}:${IMAGE_TAG}" \
  "${UZONE_DIR}/backend"

docker push "${BACKEND_REPO_URL}:${IMAGE_TAG}"

docker build \
  --no-cache \
  -f "${UZONE_DIR}/frontend/Dockerfile.prod" \
  --build-arg NEXT_PUBLIC_UZONE_API_BASE=/api \
  --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY:-}" \
  -t "${FRONTEND_REPO_URL}:${IMAGE_TAG}" \
  "${UZONE_DIR}/frontend"

docker push "${FRONTEND_REPO_URL}:${IMAGE_TAG}"
