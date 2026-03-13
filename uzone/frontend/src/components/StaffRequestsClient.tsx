'use client'

import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useEffect, useState } from 'react'

import { API_BASE, fetchJsonWithToken, postJsonWithToken } from '../lib/api'
import { ErrorCard, LoadingCard } from './RemoteState'

type RequestRow = {
  id: string
  public_id: string
  status: string
  assigned_to_user_id: string | null
  letter_type: string
  requester_first_name: string
  requester_last_name: string
}

type MeResponse = {
  local_user_id: string | null
}

type DevIdentities = {
  staff_user_id: string | null
}

function ClerkStaffRequests() {
  const { getToken, isSignedIn } = useAuth()
  const [requests, setRequests] = useState<RequestRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [localUserId, setLocalUserId] = useState<string | null>(null)

  async function refresh() {
    const data = await fetchJsonWithToken<RequestRow[]>('/api/staff/requests', async () =>
      isSignedIn ? getToken() : null,
    )
    setRequests(data || [])
  }

  useEffect(() => {
    let active = true

    async function run() {
      const me = await fetchJsonWithToken<MeResponse>('/api/auth/me', async () =>
        isSignedIn ? getToken() : null,
      )
      if (!active) {
        return
      }
      setLocalUserId(me?.local_user_id || null)
      const data = await fetchJsonWithToken<RequestRow[]>('/api/staff/requests', async () =>
        isSignedIn ? getToken() : null,
      )
      if (active) {
        setRequests(data || [])
      }
    }

    run().catch(() => {
      if (active) {
        setError('Failed to load staff requests.')
      }
    })

    return () => {
      active = false
    }
  }, [getToken, isSignedIn])

  if (error) {
    return <ErrorCard title="Staff Queue" message={error} />
  }
  if (!requests) {
    return <LoadingCard title="Staff Queue" />
  }
  return (
    <StaffRequestsTable
      requests={requests}
      getToken={async () => (isSignedIn ? getToken() : null)}
      onRefresh={refresh}
      clerkEnabled
      localUserId={localUserId}
    />
  )
}

function LocalStaffRequests() {
  const [requests, setRequests] = useState<RequestRow[] | null>(null)
  const [localUserId, setLocalUserId] = useState<string | null>(null)

  async function refresh() {
    const response = await fetch(`${API_BASE}/api/staff/requests`, { cache: 'no-store' })
    setRequests(response.ok ? ((await response.json()) as RequestRow[]) : [])
  }

  useEffect(() => {
    let active = true
    fetch(`${API_BASE}/api/staff/requests`, { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : []))
      .then((data: RequestRow[]) => {
        if (active) {
          setRequests(data)
        }
      })
    fetch(`${API_BASE}/api/dev/identities`, { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: DevIdentities | null) => {
        if (active) {
          setLocalUserId(data?.staff_user_id || null)
        }
      })
    return () => {
      active = false
    }
  }, [])

  if (!requests) {
    return <LoadingCard title="Staff Queue" />
  }
  return (
    <StaffRequestsTable
      requests={requests}
      getToken={async () => null}
      onRefresh={refresh}
      clerkEnabled={false}
      localUserId={localUserId}
    />
  )
}

function StaffRequestsTable({
  requests,
  getToken,
  onRefresh,
  clerkEnabled,
  localUserId,
}: {
  requests: RequestRow[]
  getToken: () => Promise<string | null>
  onRefresh: () => Promise<void>
  clerkEnabled: boolean
  localUserId: string | null
}) {
  const [busy, setBusy] = useState<string | null>(null)

  async function act(requestId: string, kind: 'assign' | 'start' | 'draft' | 'approve' | 'deliver') {
    setBusy(`${requestId}:${kind}`)
    try {
      if (kind === 'assign') {
        await postJsonWithToken(
          `/api/staff/requests/${requestId}/assign`,
          {
            assigned_to_user_id: localUserId,
            ...(clerkEnabled ? {} : { assigned_by_user_id: localUserId }),
          },
          getToken,
        )
      }
      if (kind === 'start') {
        await postJsonWithToken(
          `/api/staff/requests/${requestId}/start-review`,
          clerkEnabled ? {} : { actor_user_id: localUserId },
          getToken,
        )
      }
      if (kind === 'draft') {
        await postJsonWithToken(
          `/api/staff/requests/${requestId}/drafts`,
          clerkEnabled ? {} : { actor_user_id: localUserId },
          getToken,
        )
      }
      if (kind === 'approve') {
        await postJsonWithToken(
          `/api/staff/requests/${requestId}/approve`,
          clerkEnabled ? {} : { actor_user_id: localUserId },
          getToken,
        )
      }
      if (kind === 'deliver') {
        await postJsonWithToken(
          `/api/staff/requests/${requestId}/deliver`,
          {
            ...(clerkEnabled ? {} : { actor_user_id: localUserId }),
            destination: 'customer@delivery.local',
          },
          getToken,
        )
      }
      await onRefresh()
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="card page-stack">
      <div className="page-intro">
        <div className="eyebrow">Staff</div>
        <h1 className="section-title">Staff Queue</h1>
        <p className="page-intro-copy">
          Assign, review, approve, and deliver zoning letter requests from one queue.
        </p>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Request</th>
            <th>Requester</th>
            <th>Status</th>
            <th>Letter</th>
            <th>Assigned</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => (
            <tr key={request.id}>
              <td>
                <Link href={`/requests/${request.public_id}`}>{request.public_id}</Link>
              </td>
              <td>
                {request.requester_first_name} {request.requester_last_name}
              </td>
              <td>
                <span className="pill">{request.status}</span>
              </td>
              <td>{request.letter_type}</td>
              <td>{request.assigned_to_user_id || 'Unassigned'}</td>
              <td>
                <div className="button-row">
                  {!request.assigned_to_user_id && (
                    <button
                      className="button secondary"
                      onClick={() => act(request.id, 'assign')}
                      disabled={busy === `${request.id}:assign` || !localUserId}
                    >
                      Assign to me
                    </button>
                  )}
                  {(request.status === 'paid' || request.status === 'pending_review') && (
                    <button
                      className="button secondary"
                      onClick={() => act(request.id, 'start')}
                      disabled={busy === `${request.id}:start`}
                    >
                      Start review
                    </button>
                  )}
                  {request.status === 'in_progress' && (
                    <>
                      <button
                        className="button secondary"
                        onClick={() => act(request.id, 'draft')}
                        disabled={busy === `${request.id}:draft`}
                      >
                        Draft
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => act(request.id, 'approve')}
                        disabled={busy === `${request.id}:approve`}
                      >
                        Approve
                      </button>
                    </>
                  )}
                  {request.status === 'approved' && (
                    <button
                      className="button secondary"
                      onClick={() => act(request.id, 'deliver')}
                      disabled={busy === `${request.id}:deliver`}
                    >
                      Deliver
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

export function StaffRequestsClient({ clerkEnabled }: { clerkEnabled: boolean }) {
  return clerkEnabled ? <ClerkStaffRequests /> : <LocalStaffRequests />
}
