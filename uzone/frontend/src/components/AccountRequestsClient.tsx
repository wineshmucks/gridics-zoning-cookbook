'use client'

import Link from 'next/link'
import { useAuth } from '@clerk/nextjs'
import { useEffect, useState } from 'react'

import { buildApiUrl, fetchJsonWithToken, postJsonWithToken } from '../lib/api'
import {
  buildAccountCheckoutPayload,
  buildAccountPaymentReceivedPayload,
  buildAccountSubmitPayload,
} from '../lib/request-action-payloads'
import { ErrorCard, LoadingCard } from './RemoteState'

type RequestRow = {
  id: string
  public_id: string
  status: string
  letter_type: string
  delivery_method: string
  total_amount_cents: number
}

type MeResponse = {
  local_user_id: string | null
}

type DevIdentities = {
  customer_user_id: string | null
}

function ClerkAccountRequests() {
  const { getToken, isSignedIn } = useAuth()
  const [requests, setRequests] = useState<RequestRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [localUserId, setLocalUserId] = useState<string | null>(null)

  async function refresh(currentUserId?: string | null) {
    const userId = currentUserId ?? localUserId
    if (!userId) {
      return
    }
    const data = await fetchJsonWithToken<RequestRow[]>(
      `/api/requests?requester_user_id=${encodeURIComponent(userId)}`,
      async () => (isSignedIn ? getToken() : null),
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
      if (!me?.local_user_id) {
        setError('Unable to resolve current Clerk user in the backend.')
        return
      }
      setLocalUserId(me.local_user_id)
      const data = await fetchJsonWithToken<RequestRow[]>(
        `/api/requests?requester_user_id=${encodeURIComponent(me.local_user_id)}`,
        async () => (isSignedIn ? getToken() : null),
      )
      if (!active) {
        return
      }
      setRequests(data || [])
    }

    run().catch(() => {
      if (active) {
        setError('Failed to load account requests.')
      }
    })

    return () => {
      active = false
    }
  }, [getToken, isSignedIn])

  if (error) {
    return <ErrorCard title="Jurisdiction Requests" message={error} />
  }
  if (!requests) {
    return <LoadingCard title="Jurisdiction Requests" />
  }

  return (
    <AccountRequestsTable
      requests={requests}
      getToken={async () => (isSignedIn ? getToken() : null)}
      onRefresh={refresh}
      clerkEnabled
      localUserId={localUserId}
    />
  )
}

function LocalAccountRequests() {
  const [requests, setRequests] = useState<RequestRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [localUserId, setLocalUserId] = useState<string | null>(null)

  async function refresh() {
    const response = await fetch(buildApiUrl('/api/requests'), { cache: 'no-store' })
    setRequests(response.ok ? ((await response.json()) as RequestRow[]) : [])
  }

  useEffect(() => {
    let active = true
    fetch(buildApiUrl('/api/requests'), { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: RequestRow[] | null) => {
        if (active) {
          setRequests(data || [])
        }
      })
    fetch(buildApiUrl('/api/dev/identities'), { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: DevIdentities | null) => {
        if (active) {
          setLocalUserId(data?.customer_user_id || null)
        }
      })
      .catch(() => {
        if (active) {
          setError('Failed to load account requests.')
        }
      })
    return () => {
      active = false
    }
  }, [])

  if (error) {
    return <ErrorCard title="Jurisdiction Requests" message={error} />
  }
  if (!requests) {
    return <LoadingCard title="Jurisdiction Requests" />
  }

  return (
    <AccountRequestsTable
      requests={requests}
      getToken={async () => null}
      onRefresh={refresh}
      clerkEnabled={false}
      localUserId={localUserId}
    />
  )
}

function AccountRequestsTable({
  requests,
  getToken,
  onRefresh,
  clerkEnabled,
  localUserId,
}: {
  requests: RequestRow[]
  getToken: () => Promise<string | null>
  onRefresh: (userId?: string | null) => Promise<void>
  clerkEnabled: boolean
  localUserId: string | null
}) {
  const [busy, setBusy] = useState<string | null>(null)

  async function act(requestId: string, kind: 'submit' | 'quote' | 'checkout' | 'pay') {
    setBusy(`${requestId}:${kind}`)
    try {
      if (kind === 'submit') {
        await postJsonWithToken(
          `/api/requests/${requestId}/submit`,
          buildAccountSubmitPayload(clerkEnabled, localUserId),
          getToken,
        )
      }
      if (kind === 'quote') {
        await postJsonWithToken(`/api/requests/${requestId}/quote`, {}, getToken)
      }
      if (kind === 'checkout') {
        await postJsonWithToken(
          `/api/requests/${requestId}/checkout`,
          buildAccountCheckoutPayload(clerkEnabled, localUserId),
          getToken,
        )
      }
      if (kind === 'pay') {
        await postJsonWithToken(
          `/api/requests/${requestId}/payment-received`,
          buildAccountPaymentReceivedPayload(clerkEnabled, localUserId),
          getToken,
        )
      }
      await onRefresh(localUserId)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="card page-stack">
      <div className="page-intro">
        <div className="eyebrow">Requests</div>
        <h1 className="section-title">Jurisdiction Requests</h1>
        <p className="page-intro-copy">
          Review request status, delivery method, and the next action for each zoning letter.
        </p>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Request</th>
            <th>Status</th>
            <th>Letter</th>
            <th>Delivery</th>
            <th>Total</th>
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
                <span className="pill">{request.status}</span>
              </td>
              <td>{request.letter_type}</td>
              <td>{request.delivery_method}</td>
              <td>${(request.total_amount_cents / 100).toFixed(2)}</td>
              <td>
                <div className="button-row">
                  {request.status === 'draft' && (
                    <button
                      className="button secondary"
                      onClick={() => act(request.id, 'submit')}
                      disabled={busy === `${request.id}:submit`}
                    >
                      Submit
                    </button>
                  )}
                  {request.status === 'submitted' && (
                    <>
                      <button
                        className="button secondary"
                        onClick={() => act(request.id, 'quote')}
                        disabled={busy === `${request.id}:quote`}
                      >
                        Quote
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => act(request.id, 'checkout')}
                        disabled={busy === `${request.id}:checkout`}
                      >
                        Checkout
                      </button>
                    </>
                  )}
                  {request.status === 'payment_pending' && (
                    <button
                      className="button secondary"
                      onClick={() => act(request.id, 'pay')}
                      disabled={busy === `${request.id}:pay`}
                    >
                      Mark Paid
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

export function AccountRequestsClient({ clerkEnabled }: { clerkEnabled: boolean }) {
  return clerkEnabled ? <ClerkAccountRequests /> : <LocalAccountRequests />
}
