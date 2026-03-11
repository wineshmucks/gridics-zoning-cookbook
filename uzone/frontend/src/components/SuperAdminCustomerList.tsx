import Link from 'next/link'

type CustomerSummary = {
  id: string
  name: string
  membersCount: number | null
  customerId: string | null
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
            Customer management
          </h1>
          <p className="admin-copy">
            Start with the customer list. Open a customer to manage admins, or add a new customer.
          </p>
        </div>
        <div className="button-row">
          <Link href="/super-admin/assistant" className="button secondary">
            Open Assistant
          </Link>
          <Link href="/super-admin/customers/new" className="button">
            Add Customer
          </Link>
        </div>
      </div>

      {flashMessage ? (
        <div className="status-banner status-banner-success">{flashMessage}</div>
      ) : null}

      <div className="admin-list">
        <div className="admin-list-heading">Customers</div>
        {customers.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Clerk Org ID</th>
                <th>Members</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr key={customer.id}>
                  <td>{customer.name}</td>
                  <td>{customer.customerId || 'Unavailable'}</td>
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
          <div style={{ color: 'var(--muted)' }}>No customers have been provisioned yet.</div>
        )}
      </div>
    </section>
  )
}
