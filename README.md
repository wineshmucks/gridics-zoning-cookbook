# UZone

UZone is a self-contained zoning verification workflow app with `backend/` and `frontend/` at the repo root.

## Stack

- `backend/`: FastAPI + SQLAlchemy + Alembic
- `frontend/`: Next.js
- `docker-compose.yml`: local full-stack runtime with PostgreSQL

## Run Locally With Docker

From the repo root:

```bash
cp .env.example .env
```

Then:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3001`
- Backend API: `http://localhost:8000`
- Backend health: `http://localhost:8000/health`
- Backend routes: `http://localhost:8000/routes`

The backend container automatically:

1. runs Alembic migrations
2. seeds demo data
3. starts the API server

## AWS Deployment

Production AWS deployment scaffolding is available under:

- [deploy/aws/README.md](/workspaces/gridics-zoning-cookbook/deploy/aws/README.md)

It includes:

- production Dockerfiles for backend and frontend
- Terraform for ECR, ECS Fargate, ALB, and RDS PostgreSQL
- a build-and-push script for publishing images to ECR

The shared deploy baseline lives in `.env-deploy`. If you need a production deploy file, create `.env-deploy.prod` locally and keep it untracked.

## Seeded Demo Users

- `admin@uzone.local` / `password123`
- `staff@uzone.local` / `password123`
- `customer@uzone.local` / `password123`

## Local Backend Without Docker

```bash
cd backend
pip install -e .
alembic upgrade heads
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

## Agno Session Persistence

Agno session persistence is wired in through the backend AgentOS and customer zoning agent setup:

- [`backend/app/agents/storage.py`](/workspaces/gridics-zoning-cookbook/backend/app/agents/storage.py) builds the shared Agno Postgres session DB, run-metrics helpers, and session-usage rollups
- [`backend/app/agents/zoning_agent.py`](/workspaces/gridics-zoning-cookbook/backend/app/agents/zoning_agent.py) attaches the DB and bounded history settings to the public team and agent
- [`backend/app/agent_os.py`](/workspaces/gridics-zoning-cookbook/backend/app/agent_os.py) reuses the same PostgreSQL connection for AgentOS

Session identity:

- The browser already keeps a stable `session_id` per chat thread and sends it with each run
- Tenant scope is stored in `metadata.tenant_client_id` so `user_id` stays available for a future real user id
- Agno prefers `conversation_id`, `session_id`, `thread_id`, or `chat_id` if those are available in metadata or session state
- If none are present, Agno generates a fresh session id

Storage controls:

- `AGNO_SESSION_TABLE=...`
- `AGNO_STORE_HISTORY_MESSAGES=true|false`
- `AGNO_NUM_HISTORY_RUNS=...`
- `NEXT_PUBLIC_ASSISTANT_TARGET_ID=...`

The implementation keeps history conservative by default:

- `add_history_to_context` is enabled for the customer zoning assistant because it already depends on multi-turn follow-ups
- `num_history_runs` is capped at 5
- `store_history_messages` defaults to `false`
- If you turn `AGNO_STORE_HISTORY_MESSAGES=true` on, expect materially higher PostgreSQL usage because Agno persists expanded history per run

Inspecting stored conversations:

- Use `customer_zoning_team.get_session(session_id="...")` or `customer_zoning_agent.get_session(session_id="...")`
- Use `GET /api/admin/agno/sessions/{session_id}/usage` to inspect per-session totals from the browser or API client
- Use the super-admin conversations screen at `/super-admin/{organizationId}/conversations` to review tenant-scoped chat threads
- Use [`backend/app/agents/storage.py`](/workspaces/gridics-zoning-cookbook/backend/app/agents/storage.py) `get_session_usage_totals(session_id)` to inspect per-session totals

Example:

```python
from app.agents.storage import get_session_usage_totals

print(get_session_usage_totals("session_123"))
```

## Local Frontend Without Docker

```bash
cd frontend
npm install
UZONE_API_BASE=http://localhost:8000 NEXT_PUBLIC_UZONE_API_BASE=http://localhost:8000 npm run dev
```

For local testing of the split host routing model (`agentic` vs `zvl`) with Windows or Linux hosts files, see:

- [docs/routing-matrix.md](/workspaces/gridics-zoning-cookbook/docs/routing-matrix.md)

The canonical public URLs for the split app surfaces are set with:

- `AGENTIC_PUBLIC_BASE_URL`
- `LETTERS_PUBLIC_BASE_URL`

`deploy-from-env.sh` mirrors those into `NEXT_PUBLIC_AGENTIC_PUBLIC_BASE_URL` and
`NEXT_PUBLIC_LETTERS_PUBLIC_BASE_URL` for the frontend build/runtime. Example:

```bash
AGENTIC_PUBLIC_BASE_URL=https://st1-agentic.gridics.com
LETTERS_PUBLIC_BASE_URL=https://st1-zvl.gridics.com
```

For local development, the frontend still supports the older
`NEXT_PUBLIC_UZONE_PRODUCT_HOST_MAP` fallback, but the base URL variables are the preferred source
of truth for staging and production.

For AWS deploys, keep `.env-deploy` in git as the baseline and create `.env-deploy.prod`
locally when you need a production-specific env file. Do not commit the prod file.

Frontend host routing:

- `AGENTIC_PUBLIC_BASE_URL=...`
- `LETTERS_PUBLIC_BASE_URL=...`
- optional fallback: `NEXT_PUBLIC_UZONE_PRODUCT_HOST_MAP=...`

## Current Scope

Implemented:

- auth registration/login
- optional Clerk-ready backend auth verification path
- jurisdictions
- properties and property snapshots
- request creation, submission, quoting, checkout, payment confirmation
- staff queue, assignment, start review, notes
- draft generation, approval, delivery
- PDF file generation and document download route
- fee schedules and fee items
- letter templates
- report summary

Still simplified:

- payment provider defaults to `manual`; Stripe is adapter-ready but not fully wired through a frontend checkout flow
- email provider defaults to `console`; Resend and Postmark adapters are included
- digital signatures are represented as approval/version records rather than an external signature platform

## Important Environment Variables

Docker Compose loads `.env` via `env_file`, so the usual local flow is:

```bash
cp .env.example .env
```

Backend:

- `UZONE_AUTH_PROVIDER=local|clerk`
- `CLERK_PEM_PUBLIC_KEY=...`
- `CLERK_JWKS_URL=...`
- `CLERK_AUTHORIZED_PARTIES=http://localhost:3001,http://st1-agentic.gridics.local:3001,http://st1-zvl.gridics.local:3001,...`

For host-based local testing, the backend also allows branded local origins such as:
- `http://st1-agentic.gridics.local:3001`
- `http://st1-zvl.gridics.local:3001`
- `http://st1-agentic.gridics.test:3001`
- `http://st1-zvl.gridics.test:3001`
- `UZONE_EMBED_SESSION_SIGNING_SECRET=...`
- `UZONE_EMBED_SESSION_ISSUER=uzone`
- `UZONE_EMBED_SESSION_AUDIENCE=uzone-embed-widget`
- `UZONE_EMBED_SESSION_TTL_SECONDS=3600`

The embed signing secret is required for the live Super Admin embed preview and for minting widget tokens.
- `UZONE_PAYMENT_PROVIDERS=manual,stripe`
- `UZONE_DEFAULT_PAYMENT_PROVIDER=manual`
- `UZONE_STRIPE_SECRET_KEY=...`
- `UZONE_EMAIL_PROVIDER=console|resend|postmark|mandrill`
- `UZONE_EMAIL_FROM=noreply@yourdomain.com`
- `UZONE_RESEND_API_KEY=...`
- `UZONE_POSTMARK_SERVER_TOKEN=...`
- `UZONE_MANDRILL_API_KEY=...`
- `UZONE_ARTIFACTS_DIR=/app/artifacts`

## Clerk

When `UZONE_AUTH_PROVIDER=clerk`:

- backend local register/login endpoints are disabled
- `GET /api/auth/me` expects a Clerk session token in `Authorization: Bearer ...`
- backend validates the token against Clerk JWKS or a configured Clerk PEM public key

This matches Clerk’s guidance for validating session tokens and checking `azp` against allowed origins:

- https://clerk.com/docs/request-authentication/validate-session-tokens

## Payment Providers

The payment layer now uses provider adapters under:

- [payment_service.py](/workspaces/gridics-zoning-cookbook/backend/app/services/payment_service.py)

Current providers:

- `manual`
- `stripe`

The manual provider is the local default.

Stripe is the first production-oriented adapter because it has broad payment-method coverage and a stable Payment Intents API:

- https://stripe.com/docs/payments/payment-intents

Webhook route:

- `POST /api/payments/webhook/stripe`

Related env var:

- `UZONE_STRIPE_WEBHOOK_SECRET=...`

## Email Providers

The email layer now uses provider adapters under:

- [email_service.py](/workspaces/gridics-zoning-cookbook/backend/app/services/email_service.py)

Current providers:

- `console`
- `resend`
- `postmark`

Email templates are stored in the database and rendered by template code first, with provider send fallback still available when no matching template exists.

Recommended choices:

- `Resend` for the fastest developer setup and a clean API: https://resend.com/docs
- `Postmark` for high-confidence transactional delivery and message streams separation: https://postmarkapp.com/developer/api/overview
- `Amazon SES` if cost and AWS integration matter more than developer ergonomics: https://docs.aws.amazon.com/ses/latest/dg/Welcome.html

## Signatures Recommendation

For external signature support, the best fit depends on the legal/compliance bar:

- `DocuSign` if you need the most established enterprise eSignature platform and broad workflow coverage: https://www.docusign.com/products/apis
- `Dropbox Sign` if you want a faster embedded signing implementation and simpler developer UX: https://developers.hellosign.com/docs/api/embedded

For UZone specifically:

- use internal approval + generated PDF for ordinary zoning letters that do not require external signer identity proofing
- use DocuSign when you need formal external signature workflows, signer audit artifacts, or broader municipal/legal scrutiny
- use Dropbox Sign if embedded in-app signing speed matters more than enterprise breadth

## Embeddable Assistant Widget

UZone now supports a secure third-party widget flow similar to the Placer County / Polimorphic pattern.

How it works:

1. A host site administrator provisions an embed secret for a tenant.
2. The host backend exchanges that secret for a short-lived widget token from `POST /api/public/embed/sessions`.
3. The host embeds `https://your-uzone-domain/embed#token=...` in an iframe.
4. The widget validates the token with `GET /api/public/embed/session` and uses the token on chat run requests.

The signed token is what protects the assistant. The host never gets direct access to the chat backend credentials.

Provisioning example:

```bash
curl -X POST "https://your-uzone-domain/api/admin/clients/dream-town/assistant-embed" \
  -H "Content-Type: application/json" \
  -d '{
    "allowed_origins": ["https://partner.example.com"],
    "widget_title": "Ask Dream Town",
    "launcher_label": "Have a question?",
    "accent_color": "#0b67c2",
    "is_active": true
  }'
```

That response returns the one-time secret. The host backend can then mint a widget token with:

```bash
curl -X POST "https://your-uzone-domain/api/public/embed/sessions" \
  -H "Content-Type: application/json" \
  -H "X-UZone-Embed-Secret: <one-time-secret>" \
  -d '{
    "client_id": "dream-town",
    "origin": "https://partner.example.com"
  }'
```

Use the returned `token` in the iframe fragment:

```html
<iframe
  src="https://your-uzone-domain/embed#token=eyJ..."
  style="position:fixed;right:20px;bottom:20px;width:420px;height:700px;border:0;z-index:2147483647;"
></iframe>
```

For a live test page inside UZone, open:

- `/super-admin/:organizationId/assistant-embed`
- add `?secret=<one-time-secret>` after saving the embed settings
- optionally add `?origin=https://partner.example.com` to preview a specific allowed origin

That page mints a fresh token and renders the same iframe-backed widget the host site will use.
