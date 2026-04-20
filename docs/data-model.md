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

Tables are organized into three logical domains:

### Shared Entities

Core infrastructure and multi-domain entities:

- `shared_users`
- `shared_roles`
- `shared_user_roles`
- `shared_sessions`
- `shared_jurisdictions`
- `shared_tenant_clients`
- `shared_tenant_domains`
- `shared_platform_settings`
- `shared_properties`
- `shared_property_snapshots`
- `shared_email_templates`
- `shared_jurisdiction_home_page_content`
- `shared_email_events`
- `shared_audit_log`

### Agentic Entities

AI agent, observability, and knowledge management:

- `agentic_assistant_message_feedback`
- `agentic_assistant_turn_events`
- `agentic_assistant_run_telemetry`
- `agentic_zoning_code_ingestion_runs`
- `agentic_zoning_code_documents`
- `agentic_zoning_code_sections`

### Letters Entities

Zoning letter requests, fulfillment, and pricing:

- `letters_requests`
- `letters_request_status_events`
- `letters_request_assignments`
- `letters_request_notes`
- `letters_fee_schedules`
- `letters_fee_schedule_items`
- `letters_quotes`
- `letters_payments`
- `letters_payment_events`
- `letters_letter_templates`
- `letters_letter_drafts`
- `letters_letter_versions`
- `letters_deliveries`

## Shared Entities

### Users and Sessions

#### `shared_users`

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

#### `shared_roles`

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

#### `shared_user_roles`

Fields:

- `id`
- `user_id`
- `role_id`
- `granted_by_user_id`
- `created_at`

Constraint:

- unique on `user_id, role_id`

#### `shared_sessions`

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

### Jurisdictions and Configuration

#### `shared_jurisdictions`

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

#### `shared_tenant_clients`

Purpose:

- partition work by tenant and customer organization

Fields:

- `id`
- `client_id` unique
- `clerk_organization_id` unique nullable
- `jurisdiction_id` nullable
- `city_name`
- `department_name`
- `standard_letter_fee_cents`
- `comprehensive_letter_fee_cents`
- `expedited_fee_cents`
- `support_phone`
- `support_email`
- `contact_address`
- `is_active`
- `settings_json`
- `created_at`
- `updated_at`

#### `shared_tenant_domains`

Purpose:

- map domain names to tenant clients

Fields:

- `id`
- `tenant_client_id`
- `hostname` unique
- `is_primary`
- `created_at`
- `updated_at`

#### `shared_platform_settings`

Purpose:

- store platform-wide configuration

Fields:

- `id`
- `key` unique
- `json_value` nullable
- `created_at`
- `updated_at`

### Property Data

#### `shared_properties`

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

#### `shared_property_snapshots`

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

## Letters Entities

### Requests

#### `letters_requests`

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

#### `letters_request_status_events`

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

#### `letters_request_assignments`

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

#### `letters_request_notes`

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

### Pricing

#### `letters_fee_schedules`

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

#### `letters_fee_schedule_items`

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

#### `letters_quotes`

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

### Payments

#### `letters_payments`

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

#### `letters_payment_events`

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

### Documents

#### `letters_letter_templates`

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

#### `letters_letter_drafts`

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

#### `letters_letter_versions`

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

### Delivery

#### `letters_deliveries`

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

### Email

#### `shared_email_templates`

Purpose:

- jurisdiction and tenant-scoped email templates with default/override support

Fields:

- `id`
- `jurisdiction_id` nullable
- `tenant_client_id` nullable
- `owner_organization_id` nullable
- `base_template_id` nullable (for overrides)
- `code`
- `trigger_state`
- `name`
- `description` nullable
- `category`
- `subject_template`
- `body_template`
- `status`
- `version`
- `created_by_user_id` nullable
- `is_system_default`
- `created_at`
- `updated_at`

#### `shared_email_events`

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

### Home Page Content

#### `shared_jurisdiction_home_page_content`

Purpose:

- store jurisdiction-specific home page content and layout

Fields:

- `id`
- `jurisdiction_id` unique
- `hero_json`
- `services_json`
- `about_json`
- `faq_json`
- `contact_json`
- `created_at`
- `updated_at`

### Audit

#### `shared_audit_log`

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

## Agentic Entities

### Assistant Feedback and Telemetry

#### `agentic_assistant_message_feedback`

Purpose:

- collect user feedback on individual assistant messages

Fields:

- `id`
- `tenant_client_id`
- `clerk_user_id` nullable
- `agent_id`
- `surface`
- `conversation_id`
- `message_id`
- `run_id` nullable
- `feedback_value`
- `message_excerpt` nullable
- `metadata_json` nullable
- `created_at`
- `updated_at`

Constraint:

- unique on `tenant_client_id, conversation_id, message_id`

#### `agentic_assistant_turn_events`

Purpose:

- track assistant turn metrics and decision points

Fields:

- `id`
- `tenant_client_id` nullable
- `conversation_id` nullable
- `message_id` nullable
- `run_id` nullable
- `agent_id` nullable
- `intent_type` nullable
- `jurisdiction_status` nullable
- `policy_decision` nullable
- `reason_code` nullable
- `payload_json` nullable
- `created_at`
- `updated_at`

#### `agentic_assistant_run_telemetry`

Purpose:

- track LLM model performance and costs

Fields:

- `id`
- `tenant_client_id` nullable
- `run_scope`
- `agent_id` nullable
- `conversation_id` nullable
- `message_id` nullable
- `run_id` nullable
- `session_id` nullable
- `model_provider` nullable
- `model_name` nullable
- `model_id` nullable
- `input_tokens`
- `output_tokens`
- `total_tokens`
- `cost` nullable
- `time_to_first_token` nullable
- `duration_seconds` nullable
- `metrics_json` nullable
- `created_at`
- `updated_at`

### Zoning Code Knowledge

#### `agentic_zoning_code_ingestion_runs`

Purpose:

- track zoning code document ingestion and processing

Fields:

- `id`
- `tenant_client_id`
- `mode`
- `status`
- `source_url`
- `pages_crawled`
- `documents_extracted`
- `sections_extracted`
- `chunks_upserted`
- `error_message` nullable
- `started_at`
- `completed_at` nullable
- `created_at`
- `updated_at`

#### `agentic_zoning_code_documents`

Purpose:

- store raw zoning code documents from sources

Fields:

- `id`
- `tenant_client_id`
- `ingestion_run_id` nullable
- `source_url`
- `source_path` nullable
- `source_title` nullable
- `source_hash`
- `fetch_status_code` nullable
- `raw_text`
- `metadata_json` nullable
- `fetched_at`
- `created_at`
- `updated_at`

Constraint:

- unique on `tenant_client_id, source_url`

#### `agentic_zoning_code_sections`

Purpose:

- store extracted and chunked zoning code sections for embedding and retrieval

Fields:

- `id`
- `tenant_client_id`
- `ingestion_run_id` nullable
- `document_id`
- `section_key`
- `section_title`
- `section_level`
- `section_order`
- `section_path` nullable
- `normalized_text`
- `source_anchor` nullable
- `metadata_json` nullable
- `content_hash`
- `created_at`
- `updated_at`

Constraint:

- unique on `tenant_client_id, section_key`

## Relationships

Important relationships:

- `shared_users 1:n shared_sessions`
- `shared_users n:n shared_roles` via `shared_user_roles`
- `shared_jurisdictions 1:n shared_properties`
- `shared_jurisdictions 1:n shared_email_templates`
- `shared_tenant_clients 1:n shared_tenant_domains`
- `shared_properties 1:n shared_property_snapshots`
- `letters_requests n:1 shared_users` via `requester_user_id`
- `letters_requests n:1 shared_properties`
- `letters_requests n:1 shared_property_snapshots`
- `letters_requests 1:n letters_request_status_events`
- `letters_requests 1:n letters_request_assignments`
- `letters_requests 1:n letters_request_notes`
- `letters_requests 1:n letters_quotes`
- `letters_requests 1:n letters_payments`
- `letters_requests 1:n letters_letter_drafts`
- `letters_requests 1:n letters_letter_versions`
- `letters_requests 1:n letters_deliveries`
- `letters_fee_schedules 1:n letters_fee_schedule_items`
- `letters_letter_templates n:1 shared_jurisdictions`
- `agentic_zoning_code_ingestion_runs 1:n agentic_zoning_code_documents`
- `agentic_zoning_code_documents 1:n agentic_zoning_code_sections`

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

