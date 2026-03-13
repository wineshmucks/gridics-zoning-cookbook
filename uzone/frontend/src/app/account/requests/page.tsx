import Link from 'next/link'

import { AccountRequestsClient } from '../../../components/AccountRequestsClient'

export default function AccountRequestsPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  return (
    <>
      <section className="card" style={{ marginBottom: 20 }}>
        <div className="stack-header">
          <div>
            <h1 className="section-title">Jurisdiction Requests</h1>
            <p className="subtitle" style={{ marginBottom: 0, fontSize: 16 }}>
              Track submitted letters, quotes, payment state, and delivery.
            </p>
          </div>
          <Link className="button" href="/request/new">
            New request
          </Link>
        </div>
      </section>
      <AccountRequestsClient clerkEnabled={clerkEnabled} />
    </>
  )
}
