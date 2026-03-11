# UZone

UZone is a self-contained zoning verification workflow app under `uzone/`.

## Stack

- `backend/`: FastAPI + SQLAlchemy + Alembic
- `frontend/`: Next.js
- `docker-compose.yml`: local full-stack runtime with PostgreSQL

## Run Locally With Docker

From the `uzone/` directory:

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

- [uzone/deploy/aws/README.md](/workspaces/gridics-zoning-cookbook/uzone/deploy/aws/README.md)

It includes:

- production Dockerfiles for backend and frontend
- Terraform for ECR, ECS Fargate, ALB, and RDS PostgreSQL
- a build-and-push script for publishing images to ECR

## Seeded Demo Users

- `admin@uzone.local` / `password123`
- `staff@uzone.local` / `password123`
- `customer@uzone.local` / `password123`

## Local Backend Without Docker

```bash
cd backend
pip install -e .
alembic upgrade head
python -m app.scripts.seed_data
uvicorn app.main:app --reload
```

## Local Frontend Without Docker

```bash
cd frontend
npm install
UZONE_API_BASE=http://localhost:8000 NEXT_PUBLIC_UZONE_API_BASE=http://localhost:8000 npm run dev
```

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

Docker Compose loads `uzone/.env` via `env_file`, so the usual local flow is:

```bash
cd uzone
cp .env.example .env
```

Backend:

- `UZONE_AUTH_PROVIDER=local|clerk`
- `UZONE_CLERK_PEM_PUBLIC_KEY=...`
- `UZONE_CLERK_JWKS_URL=...`
- `UZONE_CLERK_AUTHORIZED_PARTIES=http://localhost:3001,...`
- `UZONE_PAYMENT_PROVIDERS=manual,stripe`
- `UZONE_DEFAULT_PAYMENT_PROVIDER=manual`
- `UZONE_STRIPE_SECRET_KEY=...`
- `UZONE_EMAIL_PROVIDER=console|resend|postmark`
- `UZONE_EMAIL_FROM=noreply@yourdomain.com`
- `UZONE_RESEND_API_KEY=...`
- `UZONE_POSTMARK_SERVER_TOKEN=...`
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

- [payment_service.py](/workspaces/gridics-zoning-cookbook/uzone/backend/app/services/payment_service.py)

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

- [email_service.py](/workspaces/gridics-zoning-cookbook/uzone/backend/app/services/email_service.py)

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
