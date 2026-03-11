# UZone Implementation Plan

## Goal

Build a complete zoning verification letter product inside `uzone/` using the mock screens in `uzone/mocks/` as the functional reference.

This plan assumes:

- `uzone/` is self-contained.
- No existing backend or frontend code outside `uzone/` is required.
- The product includes public intake, staff processing, admin configuration, payments, document generation, notifications, and reporting.

## Product Scope

The mocks imply four product areas:

1. Public portal
2. Staff operations portal
3. Admin configuration portal
4. Shared platform services

### Public portal

- Marketing homepage
- Parcel selection/search
- Account creation and sign-in
- Request form
- Fee calculation and payment
- Order history
- Status tracking

### Staff portal

- Request queue
- Filtering and assignment
- Request detail view
- Internal notes and status history
- Letter drafting/editing
- Approval and digital signing
- Delivery controls
- Reports and exports

### Admin portal

- Jurisdiction management
- Form settings
- Email templates
- Fee structure
- Letter templates
- Home page content
- Permissions and roles

### Shared services

- Authentication and RBAC
- Property and parcel retrieval
- Payment processing
- PDF generation
- Email delivery
- Audit logging
- Search and reporting

## Recommended UZone Structure

Create the product under `uzone/` with clear separation between API, app UI, persistence, and services.

```text
uzone/
  IMPLEMENTATION_PLAN.md
  mocks/
  backend/
    app/
      api/
      core/
      db/
      domain/
      schemas/
      services/
      workers/
    tests/
    alembic/
    pyproject.toml
  frontend/
    src/
      app/
      components/
      lib/
      hooks/
      types/
    public/
    package.json
  docs/
    api.md
    data-model.md
    state-machine.md
    template-system.md
```

## Architecture

### Backend

Use:

- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis for background jobs and transient workflow state
- Celery or RQ for async jobs
- S3-compatible object storage for final documents

Responsibilities:

- Serve REST API for public, staff, and admin flows
- Persist all transactional data
- Generate fee quotes
- Manage request lifecycle
- Produce letter drafts and final PDFs
- Send emails
- record audit events for all important actions

### Frontend

Use:

- Next.js
- TypeScript
- Tailwind
- A small internal design system based on the mock patterns

Responsibilities:

- Public request flow
- Staff operational interface
- Admin settings interface
- Authenticated account history and request tracking

### External integrations

Plan for explicit interfaces under `backend/app/services/integrations/`:

- property provider
- payment gateway
- email provider
- storage provider
- PDF renderer
- signature provider

Keep these behind adapters so vendor choices can change later.

## Core Domain Model

The central entity is `zoning_verification_request`.

Related entities:

- user
- role
- jurisdiction
- property
- property_snapshot
- request_assignment
- request_note
- request_status_event
- fee_schedule
- quote
- payment
- payment_event
- letter_template
- letter_draft
- letter_version
- signature_event
- delivery
- email_template
- email_event
- audit_log

## Database Tables

Phase 1 minimum tables:

- `users`
- `roles`
- `user_roles`
- `sessions`
- `jurisdictions`
- `properties`
- `property_snapshots`
- `requests`
- `request_status_events`
- `request_assignments`
- `request_notes`
- `fee_schedules`
- `fee_schedule_items`
- `quotes`
- `payments`
- `payment_events`
- `letter_templates`
- `letter_drafts`
- `letter_versions`
- `deliveries`
- `email_templates`
- `email_events`
- `audit_log`

### Requests table

Suggested fields:

- `id`
- `public_id` such as `ZVL-2026-000001`
- `jurisdiction_id`
- `requester_user_id`
- `property_id`
- `property_snapshot_id`
- `letter_type`
- `processing_type`
- `delivery_method`
- `status`
- `assigned_to_user_id`
- `submitted_at`
- `paid_at`
- `due_at`
- `approved_at`
- `delivered_at`
- `total_amount_cents`
- `currency`
- `payment_status`
- `current_draft_id`
- `final_document_url`

### Property snapshot

This should freeze the exact property and zoning facts used to produce the letter.

Suggested fields:

- `id`
- `property_id`
- `address`
- `apn`
- `group_id`
- `zoning_code`
- `zoning_name`
- `lot_size_sf`
- `permitted_uses_json`
- `overlays_json`
- `raw_source_payload_json`
- `source_payload_hash`
- `captured_at`

## Request State Machine

Do not treat request status as a loose string. Use a state machine plus event log.

Recommended statuses:

- `draft`
- `submitted`
- `payment_pending`
- `paid`
- `pending_review`
- `in_progress`
- `awaiting_additional_info`
- `awaiting_final_signature`
- `approved`
- `rejected`
- `delivered`
- `cancelled`
- `refunded`

Key transitions:

- `draft -> submitted`
- `submitted -> payment_pending`
- `payment_pending -> paid`
- `paid -> pending_review`
- `pending_review -> in_progress`
- `in_progress -> awaiting_additional_info`
- `in_progress -> awaiting_final_signature`
- `awaiting_final_signature -> approved`
- `approved -> delivered`
- `pending_review|in_progress -> rejected`
- `submitted|paid|pending_review -> cancelled`

Every transition should create:

- a `request_status_event`
- an `audit_log` entry
- optional email notifications

## Roles and Permissions

Initial roles:

- `public_user`
- `request_processor`
- `signer`
- `admin`
- `super_admin`
- `viewer`

Permission groups:

- account management
- request submission
- payment management
- queue access
- assignment
- draft editing
- approval
- signing
- admin configuration
- reporting export

Use a permission matrix table rather than hard-coding all role behavior in UI only.

## Backend Modules

Recommended modules under `backend/app/`:

### `api/`

- `auth.py`
- `properties.py`
- `requests.py`
- `payments.py`
- `staff_requests.py`
- `admin_fees.py`
- `admin_templates.py`
- `admin_permissions.py`
- `reports.py`

### `domain/`

- `request_states.py`
- `roles.py`
- `fee_rules.py`
- `delivery.py`

### `services/`

- `auth_service.py`
- `property_service.py`
- `request_service.py`
- `quote_service.py`
- `payment_service.py`
- `document_service.py`
- `signature_service.py`
- `delivery_service.py`
- `email_service.py`
- `report_service.py`
- `audit_service.py`

### `db/`

- models
- session management
- migrations
- repositories

## API Surface

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`
- `GET /api/me`

### Public property flow

- `GET /api/properties/search`
- `GET /api/properties/{property_id}`
- `POST /api/properties/select`

### Public request flow

- `POST /api/requests`
- `GET /api/requests/{request_id}`
- `PATCH /api/requests/{request_id}`
- `POST /api/requests/{request_id}/quote`
- `POST /api/requests/{request_id}/submit`
- `GET /api/my/requests`

### Payments

- `POST /api/requests/{request_id}/checkout`
- `POST /api/payments/webhook`
- `GET /api/requests/{request_id}/receipt`

### Staff

- `GET /api/staff/requests`
- `GET /api/staff/requests/{request_id}`
- `POST /api/staff/requests/{request_id}/assign`
- `POST /api/staff/requests/{request_id}/notes`
- `POST /api/staff/requests/{request_id}/drafts`
- `PATCH /api/staff/drafts/{draft_id}`
- `POST /api/staff/requests/{request_id}/approve`
- `POST /api/staff/requests/{request_id}/sign`
- `POST /api/staff/requests/{request_id}/deliver`

### Admin

- `GET /api/admin/jurisdictions`
- `POST /api/admin/jurisdictions`
- `GET /api/admin/form-settings`
- `PUT /api/admin/form-settings`
- `GET /api/admin/fees`
- `PUT /api/admin/fees`
- `GET /api/admin/email-templates`
- `PUT /api/admin/email-templates/{template_id}`
- `GET /api/admin/letter-templates`
- `PUT /api/admin/letter-templates/{template_id}`
- `GET /api/admin/homepage-content`
- `PUT /api/admin/homepage-content`
- `GET /api/admin/permissions`
- `PUT /api/admin/permissions`

### Reporting

- `GET /api/reports/requests`
- `GET /api/reports/summary`
- `POST /api/reports/export`

## Frontend Route Map

Implement the three app surfaces under `frontend/src/app/`.

### Public

- `/`
- `/select-property`
- `/register`
- `/login`
- `/request/new`
- `/request/[id]/review`
- `/checkout/[id]`
- `/account/requests`
- `/account/requests/[id]`

### Staff

- `/staff/requests`
- `/staff/requests/[id]`
- `/staff/reports`

### Admin

- `/admin/jurisdictions`
- `/admin/form-settings`
- `/admin/email-templates`
- `/admin/fees`
- `/admin/letter-templates`
- `/admin/homepage-content`
- `/admin/permissions`

## Feature Mapping From Mocks

### `1 Public-facing homepage.html`

Implement:

- configurable homepage content
- explanation of letter types
- CTA into property selection

### `2 Parcel Selection Page.html`

Implement:

- parcel search by address or map
- parcel detail preview
- selected property carry-forward into request flow

### `3 Account Creation Page.html` and `4 Login Page.html`

Implement:

- public auth
- session persistence
- password reset

### `5 ZVL Request Form & Review Pa.html`

Implement:

- requester data capture
- selected property summary
- letter type selection
- expedited option
- delivery method
- live quote summary

### `6 Payment Collection.html`

Implement:

- hosted or embedded card checkout
- payment confirmation page
- receipt creation

### `7 User Order History.html`

Implement:

- request list
- statuses
- download links for delivered PDFs

### `8 9 10 11`

Implement:

- staff queue
- request detail page
- note-taking
- letter editing
- approval and signing
- reporting

### `12 13 14 15 16 17 18`

Implement:

- admin configuration modules
- role management
- content and template versioning

## Document Generation Plan

The letter system should not be a loose rich-text editor only.

Use a structured model:

- template definition
- merge variables
- generated HTML
- rendered PDF
- signed PDF
- archived final version

Recommended flow:

1. load request and property snapshot
2. load jurisdiction template
3. fill merge variables
4. produce draft HTML
5. allow staff edits in constrained editable sections
6. render final PDF
7. apply digital signature metadata/stamp
8. store immutable final artifact

Template variables likely include:

- jurisdiction name
- department name
- request id
- request date
- requester name
- property address
- parcel number
- zoning district
- permitted uses
- overlay details
- staff signer name and title

## Payment Plan

Phase 1 recommendation:

- charge before staff processing
- support card payments first
- store only gateway references, never raw card data

Payment statuses:

- `unpaid`
- `checkout_created`
- `authorized`
- `paid`
- `failed`
- `refunded`

## Notification Plan

Email events needed immediately:

- account created
- request submitted
- payment received
- status changed
- additional information requested
- request approved
- letter delivered

Each email should store:

- template id
- recipient
- rendered subject
- rendered body
- provider message id
- send status

## Reporting Plan

Metrics implied by mocks:

- total requests
- approved letters
- average completion time
- revenue collected
- queue counts by status
- staff throughput
- expedited vs standard volume

Exports:

- CSV request export
- monthly finance export
- staff workload export

## Testing Plan

### Backend

- unit tests for fee logic
- unit tests for state transitions
- API tests for public request flow
- API tests for staff workflow
- webhook tests for payments
- permission tests for RBAC

### Frontend

- component tests for key forms
- route tests for auth-protected pages
- end-to-end tests for full request lifecycle

### Integration

- property provider adapter contract tests
- payment webhook replay tests
- PDF generation snapshot tests

## Delivery Phases

### Phase 1: operational MVP

- backend project bootstrap
- database schema and migrations
- auth
- property selection
- request intake
- fee calculation
- checkout
- staff queue
- request detail
- draft generation
- approval and email delivery
- account request history
- audit log

### Phase 2: administrative completeness

- fee management UI
- form settings UI
- email template management
- letter template management
- homepage content management
- permissions UI
- report search and exports

### Phase 3: hardening

- multi-jurisdiction support improvements
- physical mail workflow
- stronger signature workflow
- monitoring and observability
- performance tuning
- archival and retention policy

## First Build Sequence

This is the order I would implement:

1. create `backend/` and `frontend/` scaffolds inside `uzone/`
2. define schema and generate initial migration
3. implement auth and RBAC
4. implement property lookup and selection
5. implement request draft and submission
6. implement fee quote and payment flow
7. implement staff queue and request detail
8. implement letter draft generation and final PDF delivery
9. implement account history
10. implement admin settings modules
11. implement reporting and exports

## Immediate Next Artifact

Before coding the full system, the next useful document should be:

- a schema spec with table definitions and relationships

After that:

- backend scaffold
- initial migration
- route skeletons
- frontend route skeletons

