# UZone Request State Machine

## Goal

Define the allowed lifecycle for `requests` so UI behavior, service logic, and audit logging stay consistent.

## Primary States

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

## State Intent

### `draft`

Request exists but has not been formally submitted.

### `submitted`

User completed the form and the request is ready for checkout.

### `payment_pending`

Checkout exists but payment is not yet confirmed.

### `paid`

Payment is confirmed and the request is financially valid.

### `pending_review`

The request is in the staff queue and not yet actively worked.

### `in_progress`

A processor is actively reviewing or editing the request.

### `awaiting_additional_info`

Staff cannot proceed until the requester provides missing information.

### `awaiting_final_signature`

Draft is ready and waiting for signer approval.

### `approved`

The letter has been approved and finalized.

### `rejected`

The request will not proceed to issuance.

### `delivered`

The final approved letter has been sent to the requester.

### `cancelled`

The request was cancelled before completion.

### `refunded`

The request payment was refunded after payment had been captured.

## Allowed Transitions

### Public-side transitions

- `draft -> submitted`
- `submitted -> payment_pending`
- `payment_pending -> paid`
- `submitted -> cancelled`
- `payment_pending -> cancelled`

### Staff-side transitions

- `paid -> pending_review`
- `pending_review -> in_progress`
- `in_progress -> awaiting_additional_info`
- `awaiting_additional_info -> in_progress`
- `in_progress -> awaiting_final_signature`
- `awaiting_final_signature -> approved`
- `pending_review -> rejected`
- `in_progress -> rejected`
- `approved -> delivered`

### Exceptional transitions

- `paid -> refunded`
- `approved -> refunded`
- `paid -> cancelled`
- `pending_review -> cancelled`

## Transition Rules

### Submit request

From:

- `draft`

To:

- `submitted`

Checks:

- required requester fields present
- property selected
- valid letter type selected
- delivery method selected

Effects:

- create status event
- create audit log

### Create checkout

From:

- `submitted`

To:

- `payment_pending`

Checks:

- current quote exists
- quote is not expired

Effects:

- create payment record
- create audit log

### Confirm payment

From:

- `payment_pending`

To:

- `paid`

Checks:

- provider webhook or confirmation validates payment

Effects:

- mark payment successful
- set `paid_at`
- create status event
- create audit log
- enqueue confirmation email

### Enter queue

From:

- `paid`

To:

- `pending_review`

Checks:

- request is complete enough for staff handling

Effects:

- compute `due_at`
- create status event
- enqueue staff notification if desired

### Start work

From:

- `pending_review`

To:

- `in_progress`

Checks:

- actor has processor role

Effects:

- set assignment if needed
- create assignment history if changed
- create audit log

### Ask for more information

From:

- `in_progress`

To:

- `awaiting_additional_info`

Checks:

- actor has processor role
- staff note or message body present

Effects:

- create customer-visible note
- enqueue email
- pause SLA clock if the business chooses

### Resume from additional information

From:

- `awaiting_additional_info`

To:

- `in_progress`

Checks:

- required info has been supplied

Effects:

- create audit log

### Send to signer

From:

- `in_progress`

To:

- `awaiting_final_signature`

Checks:

- current draft exists
- draft marked ready

Effects:

- create audit log

### Approve

From:

- `awaiting_final_signature`

To:

- `approved`

Checks:

- actor has signer privilege
- final PDF generation succeeds

Effects:

- create immutable final letter version
- set `approved_at`
- store signature event if applicable
- create audit log

### Deliver

From:

- `approved`

To:

- `delivered`

Checks:

- final letter artifact exists
- delivery target is valid

Effects:

- create delivery record
- set `delivered_at`
- enqueue delivery email if email delivery
- create audit log

### Reject

From:

- `pending_review`
- `in_progress`

To:

- `rejected`

Checks:

- rejection reason required

Effects:

- create status event
- notify requester
- create audit log

### Cancel

From:

- `submitted`
- `payment_pending`
- `paid`
- `pending_review`

To:

- `cancelled`

Checks:

- cancellation reason captured

Effects:

- determine whether refund is needed
- create audit log

### Refund

From:

- `paid`
- `approved`

To:

- `refunded`

Checks:

- payment provider refund succeeded

Effects:

- update payment status
- create payment event
- create audit log

## Invalid Transitions

Examples that should be blocked:

- `draft -> approved`
- `payment_pending -> delivered`
- `rejected -> approved`
- `delivered -> in_progress`
- `cancelled -> approved`

## UI Implications

Public UI:

- show customer-safe labels only
- hide internal workflow detail where appropriate

Staff UI:

- expose assign, note, draft, approve, and deliver actions based on state and permissions

Admin UI:

- allow reporting across all states

## Audit Requirements

Every successful transition must create:

- a `request_status_event`
- an `audit_log` record

Transitions triggered by external systems must also preserve:

- raw provider payload reference
- system actor metadata

