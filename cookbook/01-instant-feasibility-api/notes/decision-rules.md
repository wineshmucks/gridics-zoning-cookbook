# Decision Rules

This example keeps feasibility deterministic and auditable:

- Source of truth: Gridics `GET /v1/property-record` response.
- Pre-check: Gridics `GET /v1/markets` is used to avoid unsupported state requests.
- Optional fallback/discovery: Gridics `GET /v1/search` (polygon) only for alternatives.

## Result states

- `likely_yes`: no hard conflicts detected and no major warning signals.
- `likely_no`: disallowed use or clear numeric conflicts (for example units/height > observed max).
- `needs_review`: missing or ambiguous zoning fields, warnings, or non-OK calculation status.
- `coverage_unavailable`: market pre-check indicates unsupported market.

## Confidence model

- `likely_yes` -> `0.84`
- `needs_review` -> `0.58`
- `likely_no` -> `0.30`
- `coverage_unavailable` -> `0.99`

These values are conservative placeholders for cookbook purposes.
