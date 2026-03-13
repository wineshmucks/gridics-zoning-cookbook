import { RequestIntakeClient } from '../../../components/RequestIntakeClient'
import { getTenantConfig } from '../../../lib/tenant'

export default async function NewRequestPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const tenant = await getTenantConfig()
  return (
    <RequestIntakeClient
      clerkEnabled={clerkEnabled}
      tenantClientId={tenant.client_id}
      tenantJurisdictionId={tenant.jurisdiction_id}
    />
  )
}
