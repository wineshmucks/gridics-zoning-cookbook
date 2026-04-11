# 01. Instant Feasibility API

## Audience
- Proptech companies
- Architects and planners
- Brokers and investors
- Builders and developers

## Problem
Given one property input, return an immediate and structured answer to: "Can I build this here?"

## Example Scope
This track is now served from the unified FastAPI server route:

- `POST /api/instant-feasibility`

Composed services:

- `GET /api/gridics/markets`
- `GET /api/gridics/property-record`
- `GET /api/gridics/search` (optional alternatives)

Result classes:

- `likely_yes`
- `likely_no`
- `needs_review`
- `coverage_unavailable`

## Inputs
Request body shape:

```json
{
  "address": "444 Brickell Ave, Miami, FL 33131",
  "state_env": "fl",
  "zip_code": "33131",
  "project": {
    "use": "multifamily",
    "units": 12,
    "height_ft": 65,
    "stories": 6,
    "gross_sqft": 12000
  },
  "enable_search_alternatives": true,
  "search_polygon": "[[[-80.1925,25.7730],[-80.1925,25.7715],[-80.1905,25.7715],[-80.1905,25.7730],[-80.1925,25.7730]]]"
}
```

## Outputs
Response includes:

- `result`
- `confidence`
- `reasons`
- `key_constraints`
- `source.gridics`
- `next_steps`
- `alternatives` (optional)

## API/Workflow Sketch
1. Normalize input address.
2. Check market availability.
3. Fetch property zoning record.
4. Run deterministic feasibility rules.
5. Optionally fetch search alternatives.

## Files In This Track
- `server/app/routers/cookbook.py`
- `agent_os/common/feasibility_engine.py`
- `agent_os/common/gridics_client.py`
- `cookbook/01-instant-feasibility-api/fixtures/request.json`
- `cookbook/01-instant-feasibility-api/fixtures/response.example.json`
- `cookbook/01-instant-feasibility-api/notes/decision-rules.md`

Compatibility wrapper (legacy):

- `cookbook/01-instant-feasibility-api/examples/python/feasibility_server.py`

## Run Locally

Start unified server:

```bash
export GRIDICS_CONSUMER_KEY="YOUR_CONSUMER_KEY"
python3 -m uvicorn server.app.main:app --host 0.0.0.0 --port 8080 --reload
```

Test route:

```bash
curl -sS -X POST "http://localhost:8080/api/instant-feasibility" \
  -H "Content-Type: application/json" \
  --data @cookbook/01-instant-feasibility-api/fixtures/request.json
```
