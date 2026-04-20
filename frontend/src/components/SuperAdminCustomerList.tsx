import Link from 'next/link'

import { buildSuperAdminCustomerPath } from '../lib/org-url'
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
  const activeCount = customers.filter((customer) => customer.isActive === true).length
  const unprovisionedCount = customers.filter((customer) => customer.isActive !== true).length
  const totalMembers = customers.reduce((sum, customer) => sum + (customer.membersCount ?? 0), 0)

  return (
    <section className="card admin-stack super-admin-jurisdictions-page" style={{ marginBottom: 18 }}>
      <div className="admin-header">
        <div className="super-admin-page-header-copy">
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Jurisdiction Management
          </h1>
          <p className="admin-copy">
            Manage jurisdiction access, setup, and provisioning from one place.
          </p>
        </div>
        <div className="button-row super-admin-header-actions">
          <form action={syncJurisdictionsFromClerkAction}>
            <button type="submit" className="button secondary">
              Sync Clerk
            </button>
          </form>
          <Link href="/super-admin/new" className="button">
            Add Jurisdiction
          </Link>
        </div>
      </div>

      {flashMessage ? (
        <div className={`status-banner ${flashTone === 'error' ? 'status-banner-error' : 'status-banner-success'}`}>
          {flashMessage}
        </div>
      ) : null}

      <div className="super-admin-metrics-row" aria-label="Jurisdiction summary">
        <div className="super-admin-metric">
          <span>Active jurisdictions</span>
          <strong>{activeCount}</strong>
        </div>
        <div className="super-admin-metric">
          <span>Unprovisioned</span>
          <strong>{unprovisionedCount}</strong>
        </div>
        <div className="super-admin-metric">
          <span>Members</span>
          <strong>{totalMembers}</strong>
        </div>
      </div>

      <div className="super-admin-section-shell">
        <div className="super-admin-section-head">
          <div className="admin-list-heading super-admin-section-heading">Jurisdictions</div>
          <div className="super-admin-section-meta">{customers.length} total</div>
        </div>
        {customers.length ? (
          <table className="table super-admin-table">
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
                  <td>
                    <div className="super-admin-customer-name-cell">
                      <div className="super-admin-customer-name">{customer.name}</div>
                    </div>
                  </td>
                  <td>
                    <span className="super-admin-id-text">{customer.customerId || 'Unavailable'}</span>
                  </td>
                  <td>
                    <span className={`status-pill ${statusTone(customer.isActive)}`}>
                      {statusLabel(customer.isActive)}
                    </span>
                  </td>
                  <td className="super-admin-members-cell">{customer.membersCount ?? 0}</td>
                  <td className="super-admin-row-actions">
                    <div className="button-row super-admin-row-action-group" style={{ justifyContent: 'flex-end' }}>
                      <Link
                        href={buildSuperAdminCustomerPath(customer.id)}
                        className="button secondary super-admin-row-primary-action"
                      >
                        Manage
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="super-admin-empty-inline">
            <strong>No jurisdictions yet.</strong>
            <span>Add a jurisdiction to start provisioning access and agentic setup.</span>
          </div>
        )}
      </div>

      <div className="super-admin-section-shell super-admin-inactive-shell" style={{ marginTop: 4 }}>
        <div className="super-admin-section-head">
          <div className="admin-list-heading super-admin-section-heading">Inactive jurisdictions</div>
          <div className="super-admin-section-meta">{inactiveCustomers.length} items</div>
        </div>
        <p className="admin-copy super-admin-section-copy" style={{ marginTop: 0 }}>
          These are database rows that are not active in the public flow. Purging them deletes the tenant mapping and any tenant-specific records we can safely remove.
        </p>
        {inactiveCustomers.length ? (
          <table className="table super-admin-table">
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
                  <td>
                    <div className="super-admin-customer-name">{customer.name}</div>
                  </td>
                  <td>
                    <span className="super-admin-id-text">{customer.id}</span>
                  </td>
                  <td>
                    <span className="super-admin-id-text">{customer.customerId || 'Unavailable'}</span>
                  </td>
                  <td>
                    <span className={`status-pill ${statusTone(customer.isActive)}`}>
                      {statusLabel(customer.isActive)}
                    </span>
                  </td>
                  <td className="super-admin-members-cell">{customer.membersCount ?? 0}</td>
                  <td className="super-admin-row-actions">
                    <div className="button-row super-admin-row-action-group" style={{ justifyContent: 'flex-end' }}>
                      <Link
                        href={buildSuperAdminCustomerPath(customer.id)}
                        className="button secondary super-admin-row-primary-action"
                      >
                        Manage
                      </Link>
                      <form action={purgeInactiveJurisdictionAction}>
                        <input type="hidden" name="organizationId" value={customer.id} />
                        <input type="hidden" name="customerName" value={customer.name} />
                        <button type="submit" className="super-admin-row-secondary-link super-admin-row-danger-link">
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
          <div className="super-admin-empty-inline super-admin-empty-inline-compact">
            <span>No inactive jurisdictions found.</span>
          </div>
        )}
      </div>
    </section>
  )
}
