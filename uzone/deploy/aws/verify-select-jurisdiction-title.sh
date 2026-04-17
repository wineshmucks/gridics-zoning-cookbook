#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <base-url>" >&2
  exit 1
fi

BASE_URL="${1%/}"
for PATH_SUFFIX in "/" "/select-jurisdiction?returnTo=%2F"; do
  HTML="$(curl -fsSL "${BASE_URL}${PATH_SUFFIX}")"

  if [[ "${HTML}" != *"<title>Gridics AI Assistant</title>"* ]]; then
    echo "error: expected ${PATH_SUFFIX} title to be Gridics AI Assistant" >&2
    exit 1
  fi

  if [[ "${HTML}" == *"City of Miami"* ]]; then
    echo "error: ${PATH_SUFFIX} title leaked a jurisdiction name" >&2
    exit 1
  fi
done

echo "agentic home and select-jurisdiction title smoke test passed."
