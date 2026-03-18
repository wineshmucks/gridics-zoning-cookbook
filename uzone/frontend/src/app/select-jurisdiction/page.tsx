import { JurisdictionPickerClient } from '../../components/JurisdictionPickerClient'
import { buildServerBackendApiUrl } from '../../lib/backend'
import { getClerkManagementClient } from '../../lib/clerk'

type CustomerChoice = {
  orgid: string
  client_id: string
  city_name: string
  department_name: string
}

type PageProps = {
  searchParams?: Promise<{
    returnTo?: string | string[]
  }>
}

async function loadCustomers() {
  try {
    const response = await fetch(await buildServerBackendApiUrl('/api/public/customers'), {
      cache: 'no-store',
    })
    if (!response.ok) {
      return []
    }

    return (await response.json()) as CustomerChoice[]
  } catch {
    return []
  }
}

async function loadClerkOrganizationIds() {
  try {
    const client = await getClerkManagementClient()
    const organizations = await client.organizations.getOrganizationList({
      limit: 100,
    })

    return new Set(
      organizations.data
        .map((organization) => organization.id?.trim())
        .filter((organizationId): organizationId is string => Boolean(organizationId)),
    )
  } catch {
    return null
  }
}

export default async function SelectJurisdictionPage({ searchParams }: PageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const requestedReturnTo = Array.isArray(resolvedSearchParams.returnTo)
    ? resolvedSearchParams.returnTo[0] || '/'
    : resolvedSearchParams.returnTo || '/'
  const returnTo = requestedReturnTo.startsWith('/') ? requestedReturnTo : '/'
  const [customers, clerkOrganizationIds] = await Promise.all([
    loadCustomers(),
    loadClerkOrganizationIds(),
  ])
  const visibleCustomers =
    clerkOrganizationIds === null
      ? customers
      : customers.filter((customer) => clerkOrganizationIds.has(customer.orgid.trim()))

  return (
    <section className="jurisdiction-picker-page">
      <div className="jurisdiction-picker-shell">
        <div className="jurisdiction-picker-hero">
          <div className="eyebrow">Get started</div>
          <h1 className="jurisdiction-picker-title">Choose your jurisdiction</h1>
          <p className="subtitle jurisdiction-picker-subtitle">
            Your jurisdiction determines the zoning letter workflow, property search tools, and
            assistant guidance available to you.
          </p>
        </div>

        {visibleCustomers.length > 0 ? (
          <JurisdictionPickerClient customers={visibleCustomers} returnTo={returnTo} />
        ) : (
          <section className="card jurisdiction-picker-empty">
            <h2 className="section-title">No Jurisdictions Available</h2>
            <p style={{ color: 'var(--muted)', margin: 0 }}>
              No active jurisdictions are available right now.
            </p>
          </section>
        )}

        <div className="jurisdiction-picker-support">
          Need access to another jurisdiction? Contact your administrator or support.
        </div>
      </div>
    </section>
  )
}
