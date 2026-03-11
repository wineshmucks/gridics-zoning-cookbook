'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { API_BASE } from '../lib/api'
import { ErrorCard, LoadingCard } from './RemoteState'

type RequestRecord = {
  id: string
  public_id: string
  status: string
  payment_status: string
  letter_type: string
  processing_type: string
  delivery_method: string
  requester_first_name: string
  requester_last_name: string
  requester_email: string
  requester_phone: string | null
  requester_organization: string | null
  special_instructions: string | null
  total_amount_cents: number
  currency: string
  submitted_at: string | null
  paid_at: string | null
  approved_at: string | null
  delivered_at: string | null
  final_letter_version_id: string | null
}

type StatusEvent = {
  id: string
  from_status: string | null
  to_status: string
  reason_code: string | null
  reason_text: string | null
  created_at: string
}

function formatDate(value: string | null) {
  if (!value) {
    return 'Not yet'
  }
  return new Date(value).toLocaleString()
}

export function RequestDetailClient({ requestId }: { requestId: string }) {
  const [request, setRequest] = useState<RequestRecord | null>(null)
  const [events, setEvents] = useState<StatusEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    Promise.all([
      fetch(`${API_BASE}/api/requests/${encodeURIComponent(requestId)}`, { cache: 'no-store' }),
      fetch(`${API_BASE}/api/requests/${encodeURIComponent(requestId)}/status-events`, {
        cache: 'no-store',
      }),
    ])
      .then(async ([requestResponse, eventsResponse]) => {
        if (!active) {
          return
        }
        if (!requestResponse.ok) {
          throw new Error('Request not found.')
        }
        const requestData = (await requestResponse.json()) as RequestRecord
        const eventData = eventsResponse.ok ? ((await eventsResponse.json()) as StatusEvent[]) : []
        setRequest(requestData)
        setEvents(eventData)
      })
      .catch((loadError) => {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Failed to load request.')
        }
      })

    return () => {
      active = false
    }
  }, [requestId])

  if (error) {
    return <ErrorCard title="Request Detail" message={error} />
  }
  if (!request || !events) {
    return <LoadingCard title="Request Detail" />
  }

  return (
    <div className="grid" style={{ gap: 20 }}>
      <section className="card">
        <div className="stack-header">
          <div>
            <p style={{ color: 'var(--accent-2)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Request detail
            </p>
            <h1 className="section-title" style={{ marginBottom: 8 }}>
              {request.public_id}
            </h1>
            <p className="subtitle" style={{ marginBottom: 0, fontSize: 16 }}>
              {request.requester_first_name} {request.requester_last_name} · {request.requester_email}
            </p>
          </div>
          <div className="button-row">
            <Link className="button secondary" href="/account/requests">
              Account
            </Link>
            <Link className="button secondary" href="/staff/requests">
              Staff
            </Link>
            {request.final_letter_version_id ? (
              <a
                className="button"
                href={`${API_BASE}/api/documents/${request.final_letter_version_id}/download`}
                target="_blank"
                rel="noreferrer"
              >
                Download PDF
              </a>
            ) : null}
          </div>
        </div>
      </section>

      <section className="grid two-up">
        <div className="card">
          <h2 className="section-title" style={{ fontSize: 24 }}>
            Summary
          </h2>
          <dl className="detail-list">
            <div>
              <dt>Status</dt>
              <dd>
                <span className="pill">{request.status}</span>
              </dd>
            </div>
            <div>
              <dt>Payment</dt>
              <dd>{request.payment_status}</dd>
            </div>
            <div>
              <dt>Letter</dt>
              <dd>{request.letter_type}</dd>
            </div>
            <div>
              <dt>Processing</dt>
              <dd>{request.processing_type}</dd>
            </div>
            <div>
              <dt>Delivery</dt>
              <dd>{request.delivery_method}</dd>
            </div>
            <div>
              <dt>Total</dt>
              <dd>
                {(request.total_amount_cents / 100).toLocaleString(undefined, {
                  style: 'currency',
                  currency: request.currency || 'USD',
                })}
              </dd>
            </div>
          </dl>
        </div>

        <div className="card">
          <h2 className="section-title" style={{ fontSize: 24 }}>
            Timeline
          </h2>
          <dl className="detail-list">
            <div>
              <dt>Submitted</dt>
              <dd>{formatDate(request.submitted_at)}</dd>
            </div>
            <div>
              <dt>Paid</dt>
              <dd>{formatDate(request.paid_at)}</dd>
            </div>
            <div>
              <dt>Approved</dt>
              <dd>{formatDate(request.approved_at)}</dd>
            </div>
            <div>
              <dt>Delivered</dt>
              <dd>{formatDate(request.delivered_at)}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="grid two-up">
        <div className="card">
          <h2 className="section-title" style={{ fontSize: 24 }}>
            Requester
          </h2>
          <dl className="detail-list">
            <div>
              <dt>Name</dt>
              <dd>
                {request.requester_first_name} {request.requester_last_name}
              </dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{request.requester_email}</dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{request.requester_phone || 'Not provided'}</dd>
            </div>
            <div>
              <dt>Organization</dt>
              <dd>{request.requester_organization || 'Not provided'}</dd>
            </div>
          </dl>
        </div>

        <div className="card">
          <h2 className="section-title" style={{ fontSize: 24 }}>
            Instructions
          </h2>
          <p style={{ color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
            {request.special_instructions || 'No special instructions were supplied.'}
          </p>
        </div>
      </section>

      <section className="card">
        <h2 className="section-title">Status History</h2>
        <div className="timeline-list">
          {events.map((event) => (
            <div key={event.id} className="timeline-item">
              <div className="timeline-marker" />
              <div>
                <div style={{ fontWeight: 700 }}>{event.to_status}</div>
                <div style={{ color: 'var(--muted)', fontSize: 14 }}>
                  {event.reason_text || event.reason_code || 'State transition'}
                </div>
                <div style={{ color: 'var(--muted)', fontSize: 13 }}>{formatDate(event.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
