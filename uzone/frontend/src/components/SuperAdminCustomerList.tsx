import Link from 'next/link'

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
  flashMessage,
}: {
  customers: CustomerSummary[]
  flashMessage: string | null
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
          <Link href="/super-admin/assistant" className="button secondary">
            Open Assistant
          </Link>
          <Link href="/super-admin/customers/new" className="button">
            Add Jurisdiction
          </Link>
        </div>
      </div>

      {flashMessage ? (
        <div className="status-banner status-banner-success">{flashMessage}</div>
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
    </section>
  )
}
