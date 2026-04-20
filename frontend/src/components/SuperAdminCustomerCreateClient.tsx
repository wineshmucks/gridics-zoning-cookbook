'use client'

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

export function SuperAdminCustomerCreateClient({ marketOptions }: { marketOptions: string[] }) {
  const [provisionState, provisionAction, provisionPending] = useActionState(
    provisionClientAction,
    initialProvisionState,
  )
  const router = useRouter()

  useEffect(() => {
    if (!provisionState.organizationId) {
      return
    }

    router.push(`/super-admin/${provisionState.organizationId}`)
    router.refresh()
  }, [provisionState.organizationId, router])

  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="admin-header">
        <div>
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Add Jurisdiction
          </h1>
          <p className="admin-copy">
            Create a new jurisdiction organization, then manage its admins on the next screen.
          </p>
        </div>
      </div>

      <form action={provisionAction} className="admin-form" style={{ maxWidth: 560 }}>
        <div className="admin-list-heading">New jurisdiction</div>
        <label className="field">
          <span>Jurisdiction name</span>
          <input name="clientName" required />
        </label>
        <label className="field">
          <span>Market served</span>
          <input
            name="market"
            list="market-options"
            placeholder="Miami, FL"
            required
          />
          <datalist id="market-options">
            {marketOptions.map((market) => (
              <option key={market} value={market} />
            ))}
          </datalist>
          <small>Start typing to find the Gridics market this jurisdiction belongs to.</small>
        </label>
        <button className="button" type="submit" disabled={provisionPending}>
          {provisionPending ? 'Creating…' : 'Create Jurisdiction'}
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
