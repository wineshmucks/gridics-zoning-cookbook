# UZone Data Model

## Scope

This document defines the initial relational model for the Phase 1 UZone MVP.

Design goals:

- preserve a full audit trail
- separate current state from historical events
- freeze the property facts used for each letter
- support public, staff, and admin workflows
- allow later expansion to multi-jurisdiction operation

## Conventions

- Primary keys use `uuid`.
- Public-facing request IDs use a separate human-readable field.
- Money is stored in integer cents.
- Enumerated values should be enforced at the application layer first and promoted to database enums once stable.
- Every mutable business object should have `created_at` and `updated_at`.

## Entity Overview

Core entities:

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

## Users

### `users`

Purpose:

- authenticate public and staff users
- store identity and profile metadata

Fields:

- `id`
- `email` unique
- `password_hash`
- `first_name`
- `last_name`
- `phone`
- `organization`
- `is_active`
- `email_verified_at`
- `last_login_at`
- `created_at`
- `updated_at`

Notes:

- staff and public users can live in the same table
- do not split them until there is a concrete operational need

### `roles`

Fields:

- `id`
- `code` unique
- `name`
- `description`
- `created_at`
- `updated_at`

Seed roles:

- `public_user`
- `request_processor`
- `signer`
- `viewer`
- `admin`
- `super_admin`

### `user_roles`

Fields:

- `id`
- `user_id`
- `role_id`
- `granted_by_user_id`
- `created_at`

Constraint:

- unique on `user_id, role_id`

### `sessions`

Purpose:

- session or refresh-token storage

Fields:

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `revoked_at`
- `ip_address`
- `user_agent`
- `created_at`

## Jurisdictions and Configuration

### `jurisdictions`

Purpose:

- partition requests, fees, templates, and content by operating jurisdiction

Fields:

- `id`
- `code` unique
- `name`
- `department_name`
- `public_site_title`
- `public_contact_email`
- `public_contact_phone`
- `timezone`
- `is_active`
- `settings_json`
- `created_at`
- `updated_at`

`settings_json` can initially hold:

- turnaround defaults
- allowed delivery methods
- branding tokens
- parcel-provider settings

## Property Data

### `properties`

Purpose:

- store canonical parcel references selected by users

Fields:

- `id`
- `jurisdiction_id`
- `source_system`
- `source_property_id`
- `group_id`
- `apn`
- `address_line1`
- `address_line2`
- `city`
- `state`
- `postal_code`
- `latitude`
- `longitude`
- `created_at`
- `updated_at`

Indexes:

- `jurisdiction_id, apn`
- `jurisdiction_id, group_id`

### `property_snapshots`

Purpose:

- freeze the parcel and zoning facts used at request time

Fields:

- `id`
- `property_id`
- `captured_by_user_id` nullable
- `capture_reason`
- `address`
- `apn`
- `group_id`
- `zoning_code`
- `zoning_name`
- `lot_size_sf`
- `permitted_uses_json`
- `restrictions_json`
- `overlays_json`
- `raw_source_payload_json`
- `source_payload_hash`
- `captured_at`
- `created_at`

`capture_reason` values:

- `request_submission`
- `staff_refresh`
- `approval`

## Requests

### `requests`

Purpose:

- primary business record for a zoning verification request

Fields:

- `id`
- `public_id` unique
- `jurisdiction_id`
- `requester_user_id`
- `property_id`
- `property_snapshot_id`
- `letter_type`
- `processing_type`
- `delivery_method`
- `status`
- `payment_status`
- `assigned_to_user_id` nullable
- `requester_first_name`
- `requester_last_name`
- `requester_email`
- `requester_phone`
- `requester_organization`
- `mailing_address_json`
- `special_instructions`
- `submitted_at`
- `paid_at`
- `due_at`
- `approved_at`
- `delivered_at`
- `cancelled_at`
- `rejected_at`
- `total_amount_cents`
- `currency`
- `current_quote_id` nullable
- `current_draft_id` nullable
- `final_letter_version_id` nullable
- `created_at`
- `updated_at`

Recommended enums:

- `letter_type`: `standard`, `comprehensive`
- `processing_type`: `standard`, `expedited`
- `delivery_method`: `email`, `mail`

Denormalized requester fields are intentional:

- they preserve the submission record even if the user later changes profile data

### `request_status_events`

Purpose:

- immutable status history

Fields:

- `id`
- `request_id`
- `from_status`
- `to_status`
- `reason_code`
- `reason_text`
- `acted_by_user_id`
- `created_at`

### `request_assignments`

Purpose:

- track who owned work over time

Fields:

- `id`
- `request_id`
- `assigned_to_user_id`
- `assigned_by_user_id`
- `assignment_reason`
- `started_at`
- `ended_at`
- `created_at`

### `request_notes`

Purpose:

- internal notes and optional public-facing information requests

Fields:

- `id`
- `request_id`
- `author_user_id`
- `note_type`
- `visibility`
- `body`
- `created_at`
- `updated_at`

Suggested values:

- `note_type`: `internal`, `customer_message`, `system`
- `visibility`: `staff_only`, `customer_visible`

## Pricing

### `fee_schedules`

Purpose:

- versioned fee sets by jurisdiction

Fields:

- `id`
- `jurisdiction_id`
- `name`
- `status`
- `effective_start_at`
- `effective_end_at`
- `created_by_user_id`
- `created_at`
- `updated_at`

Suggested `status`:

- `draft`
- `active`
- `retired`

### `fee_schedule_items`

Purpose:

- individual fee rules

Fields:

- `id`
- `fee_schedule_id`
- `code`
- `name`
- `fee_type`
- `amount_cents`
- `currency`
- `applies_to_letter_type`
- `applies_to_processing_type`
- `applies_to_delivery_method`
- `tax_mode`
- `is_active`
- `metadata_json`
- `created_at`
- `updated_at`

Typical items:

- standard letter fee
- comprehensive letter fee
- rush processing fee
- certified copy fee
- physical mail fee

### `quotes`

Purpose:

- preserve what the customer was shown and charged

Fields:

- `id`
- `request_id`
- `fee_schedule_id`
- `status`
- `line_items_json`
- `subtotal_cents`
- `tax_cents`
- `total_cents`
- `currency`
- `generated_at`
- `expires_at`
- `created_at`

Suggested `status`:

- `draft`
- `finalized`
- `superseded`

## Payments

### `payments`

Purpose:

- store checkout and settlement state

Fields:

- `id`
- `request_id`
- `quote_id`
- `provider`
- `provider_payment_id`
- `provider_checkout_id`
- `status`
- `amount_cents`
- `currency`
- `paid_at`
- `failure_code`
- `failure_message`
- `receipt_url`
- `created_at`
- `updated_at`

Suggested `status`:

- `unpaid`
- `checkout_created`
- `authorized`
- `paid`
- `failed`
- `refunded`

### `payment_events`

Fields:

- `id`
- `payment_id`
- `provider_event_id`
- `event_type`
- `payload_json`
- `processed_at`
- `created_at`

Constraint:

- unique on `provider_event_id`

## Documents

### `letter_templates`

Purpose:

- jurisdiction-scoped versioned letter definitions

Fields:

- `id`
- `jurisdiction_id`
- `code`
- `name`
- `letter_type`
- `status`
- `template_body`
- `merge_variables_json`
- `version`
- `created_by_user_id`
- `created_at`
- `updated_at`

Suggested `status`:

- `draft`
- `active`
- `archived`

### `letter_drafts`

Purpose:

- working draft attached to a request

Fields:

- `id`
- `request_id`
- `template_id`
- `status`
- `generated_body`
- `editable_sections_json`
- `generated_from_snapshot_id`
- `created_by_user_id`
- `updated_by_user_id`
- `created_at`
- `updated_at`

Suggested `status`:

- `draft`
- `ready_for_approval`
- `superseded`

### `letter_versions`

Purpose:

- immutable stored versions of generated output

Fields:

- `id`
- `request_id`
- `draft_id` nullable
- `version_number`
- `version_type`
- `html_body`
- `pdf_storage_key`
- `pdf_sha256`
- `signed_by_user_id` nullable
- `signed_at` nullable
- `created_at`

Suggested `version_type`:

- `draft_pdf`
- `approved_pdf`
- `signed_pdf`
- `delivered_pdf`

## Delivery

### `deliveries`

Purpose:

- track final delivery attempts

Fields:

- `id`
- `request_id`
- `letter_version_id`
- `delivery_method`
- `status`
- `destination`
- `provider_reference`
- `delivered_at`
- `failure_reason`
- `created_at`
- `updated_at`

Suggested `status`:

- `pending`
- `sent`
- `delivered`
- `failed`

## Email

### `email_templates`

Fields:

- `id`
- `jurisdiction_id`
- `code`
- `name`
- `subject_template`
- `body_template`
- `status`
- `version`
- `created_by_user_id`
- `created_at`
- `updated_at`

### `email_events`

Fields:

- `id`
- `request_id` nullable
- `template_id`
- `recipient_email`
- `subject_rendered`
- `body_rendered`
- `provider`
- `provider_message_id`
- `status`
- `error_message`
- `sent_at`
- `created_at`

## Audit

### `audit_log`

Purpose:

- append-only record of significant system actions

Fields:

- `id`
- `actor_user_id` nullable
- `entity_type`
- `entity_id`
- `action`
- `before_json`
- `after_json`
- `metadata_json`
- `ip_address`
- `user_agent`
- `created_at`

Examples:

- request submitted
- request assigned
- note added
- quote finalized
- payment confirmed
- letter approved
- permissions changed

## Relationships

Important relationships:

- `users 1:n sessions`
- `users n:n roles`
- `jurisdictions 1:n properties`
- `jurisdictions 1:n requests`
- `properties 1:n property_snapshots`
- `requests n:1 users` through `requester_user_id`
- `requests n:1 properties`
- `requests n:1 property_snapshots`
- `requests 1:n request_status_events`
- `requests 1:n request_assignments`
- `requests 1:n request_notes`
- `requests 1:n quotes`
- `requests 1:n payments`
- `requests 1:n letter_drafts`
- `requests 1:n letter_versions`
- `requests 1:n deliveries`
- `requests 1:n email_events`
- `jurisdictions 1:n fee_schedules`
- `fee_schedules 1:n fee_schedule_items`
- `jurisdictions 1:n letter_templates`
- `jurisdictions 1:n email_templates`

## Seed Data

Phase 1 seed records should include:

- one jurisdiction
- all base roles
- one active fee schedule
- one standard letter template
- one comprehensive letter template
- core email templates
- one admin user

## Open Decisions

These should be locked before migration work starts:

- exact payment provider
- whether physical mail is Phase 1 or deferred
- whether signers are separate from processors in MVP
- whether customer-visible messaging is allowed from staff notes or requires a separate model
- whether multiple property snapshots per request are shown in UI or only latest/current

