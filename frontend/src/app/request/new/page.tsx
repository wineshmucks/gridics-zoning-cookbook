import { RequestIntakeClient } from '../../../components/RequestIntakeClient'
import { getTenantConfig } from '../../../lib/tenant'

export default async function NewRequestPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const tenant = await getTenantConfig()

  if (!tenant?.client_id) {
    return (
      <section className="card">
        <h1 className="section-title">Jurisdiction Configuration Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          This request form needs an active tenant client configuration before new requests can be created.
        </p>
      </section>
    )
  }

  return (
    <RequestIntakeClient
      clerkEnabled={clerkEnabled}
      tenantClientId={tenant.client_id}
      tenantJurisdictionId={tenant.jurisdiction_id ?? null}
    />
  )
}
