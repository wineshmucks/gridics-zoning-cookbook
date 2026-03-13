#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "usage: $0 <base-url> <client-id> <customer-name> <message>" >&2
  exit 1
fi

BASE_URL="${1%/}"
CLIENT_ID="$2"
CUSTOMER_NAME="$3"
MESSAGE="$4"
ATTEMPTS="${VERIFY_ATTEMPTS:-3}"

TMP_OUTPUT="$(mktemp)"
cleanup() {
  rm -f "$TMP_OUTPUT"
}
trap cleanup EXIT

run_once() {
  curl -sS "${BASE_URL}/api/agents/customer-zoning-agent/runs" \
    -H 'Accept: text/event-stream' \
    -F "message=${MESSAGE}" \
    -F 'stream=true' \
    -F "dependencies={\"client_id\":\"${CLIENT_ID}\",\"customer_name\":\"${CUSTOMER_NAME}\"}" \
    -F "metadata={\"surface\":\"aws-smoke-test\",\"client_id\":\"${CLIENT_ID}\"}" \
    > "$TMP_OUTPUT"

  python - "$TMP_OUTPUT" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    raw = handle.read().replace("\r\n", "\n")

blocks = [block for block in raw.split("\n\n") if block.strip()]
events = []
for block in blocks:
    event_name = "message"
    data_lines = []
    for line in block.split("\n"):
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        continue
    events.append((event_name, json.loads("\n".join(data_lines))))

run_completed = next((payload for name, payload in reversed(events) if name == "RunCompleted"), None)
if run_completed is None:
    raise SystemExit("No RunCompleted event found in assistant stream.")

content = (run_completed.get("content") or "").strip()
if not content:
    content = "".join(
        payload.get("content", "")
        for name, payload in events
        if name == "RunContent" and isinstance(payload.get("content"), str)
    ).strip()

if not content:
    raise SystemExit("RunCompleted content was empty.")

print("Run succeeded with non-empty content.")
print()
print(content[:1200])
PY
}

attempt=1
while (( attempt <= ATTEMPTS )); do
  if run_once; then
    exit 0
  fi

  if (( attempt == ATTEMPTS )); then
    exit 1
  fi

  attempt=$((attempt + 1))
  sleep 2
done
