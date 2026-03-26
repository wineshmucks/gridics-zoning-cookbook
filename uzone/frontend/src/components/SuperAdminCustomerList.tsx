import Link from 'next/link'

import {
  purgeInactiveJurisdictionAction,
  syncJurisdictionsFromClerkAction,
} from '../app/admin/actions'

type CustomerSummary = {
  id: string
  name: string
  membersCount: number | null
  customerId: string | null
  isActive: boolean | null
}

function statusTone(isActive: boolean | null): string {
  if (isActive === true) {
    return 'is-active'
  }
  if (isActive === false) {
    return 'is-inactive'
  }
  return 'is-draft'
}

function statusLabel(isActive: boolean | null): string {
  if (isActive === true) {
    return 'Active'
  }
  if (isActive === false) {
    return 'Inactive'
  }
  return 'Unprovisioned'
}

export function SuperAdminCustomerList({
  customers,
  inactiveCustomers,
  flashMessage,
  flashTone,
}: {
  customers: CustomerSummary[]
  inactiveCustomers: CustomerSummary[]
  flashMessage: string | null
  flashTone: 'success' | 'error' | null
}) {
  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="admin-header">
        <div>
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Jurisdiction management
          </h1>
          <p className="admin-copy">
            Start with the jurisdiction list. Open a jurisdiction to manage admins, or add a new jurisdiction.
          </p>
        </div>
        <div className="button-row">
          <form action={syncJurisdictionsFromClerkAction}>
            <button type="submit" className="button secondary">
              Sync Clerk
            </button>
          </form>
          <Link href="/super-admin/gridics-debug" className="button secondary">
            Gridics Debug
          </Link>
          <Link href="/super-admin/assistant" className="button secondary">
            Open Assistant
          </Link>
          <Link href="/super-admin/customers/new" className="button">
            Add Jurisdiction
          </Link>
        </div>
      </div>

      {flashMessage ? (
        <div className={`status-banner ${flashTone === 'error' ? 'status-banner-error' : 'status-banner-success'}`}>
          {flashMessage}
        </div>
      ) : null}

      <div className="admin-list">
        <div className="admin-list-heading">Jurisdictions</div>
        {customers.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Clerk Org ID</th>
                <th>Status</th>
                <th>Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr key={customer.id}>
                  <td>{customer.name}</td>
                  <td>{customer.customerId || 'Unavailable'}</td>
                  <td>
                    <span className={`status-pill ${statusTone(customer.isActive)}`}>
                      {statusLabel(customer.isActive)}
                    </span>
                  </td>
                  <td>{customer.membersCount ?? 0}</td>
                  <td>
                    <Link
                      href={`/super-admin/customers/${customer.id}`}
                      className="button secondary"
                    >
                      Manage
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ color: 'var(--muted)' }}>No jurisdictions have been provisioned yet.</div>
        )}
      </div>

      <div className="admin-list" style={{ marginTop: 24 }}>
        <div className="admin-list-heading">Inactive jurisdictions</div>
        <p className="admin-copy" style={{ marginTop: 0 }}>
          These are database rows that are not active in the public flow. Purging them deletes the tenant mapping and any tenant-specific records we can safely remove.
        </p>
        {inactiveCustomers.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Tenant ID</th>
                <th>Clerk Org ID</th>
                <th>Status</th>
                <th>Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {inactiveCustomers.map((customer) => (
                <tr key={customer.id}>
                  <td>{customer.name}</td>
                  <td>{customer.id}</td>
                  <td>{customer.customerId || 'Unavailable'}</td>
                  <td>
                    <span className={`status-pill ${statusTone(customer.isActive)}`}>
                      {statusLabel(customer.isActive)}
                    </span>
                  </td>
                  <td>{customer.membersCount ?? 0}</td>
                  <td>
                    <div className="button-row" style={{ justifyContent: 'flex-end' }}>
                      <Link href={`/super-admin/customers/${customer.id}`} className="button secondary">
                        Manage
                      </Link>
                      <form action={purgeInactiveJurisdictionAction}>
                        <input type="hidden" name="organizationId" value={customer.id} />
                        <input type="hidden" name="customerName" value={customer.name} />
                        <button type="submit" className="button secondary">
                          Purge
                        </button>
                      </form>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ color: 'var(--muted)' }}>No inactive jurisdictions found.</div>
        )}
      </div>
    </section>
  )
}
