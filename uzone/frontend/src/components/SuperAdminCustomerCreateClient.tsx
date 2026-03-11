'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useActionState, useEffect } from 'react'

import {
  provisionClientAction,
  type ProvisionClientState,
} from '../app/admin/actions'

const initialProvisionState: ProvisionClientState = {
  error: null,
  success: null,
  organizationId: null,
}

export function SuperAdminCustomerCreateClient() {
  const [provisionState, provisionAction, provisionPending] = useActionState(
    provisionClientAction,
    initialProvisionState,
  )
  const router = useRouter()

  useEffect(() => {
    if (!provisionState.organizationId) {
      return
    }

    router.push(`/super-admin/customers/${provisionState.organizationId}`)
    router.refresh()
  }, [provisionState.organizationId, router])

  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="admin-header">
        <div>
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Add Customer
          </h1>
          <p className="admin-copy">
            Create a new customer organization, then manage its admins on the next screen.
          </p>
        </div>
        <Link href="/super-admin" className="button secondary">
          Back to Customers
        </Link>
      </div>

      <form action={provisionAction} className="admin-form" style={{ maxWidth: 560 }}>
        <div className="admin-list-heading">New customer</div>
        <label className="field">
          <span>Customer name</span>
          <input name="clientName" required />
        </label>
        <button className="button" type="submit" disabled={provisionPending}>
          {provisionPending ? 'Creating…' : 'Create Customer'}
        </button>
        {provisionState.error ? (
          <div className="status-banner status-banner-error">{provisionState.error}</div>
        ) : null}
        {provisionState.success ? (
          <div className="status-banner status-banner-success">{provisionState.success}</div>
        ) : null}
      </form>
    </section>
  )
}
