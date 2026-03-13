import { CustomerPickerClient } from '../../components/CustomerPickerClient'
import { buildServerBackendApiUrl } from '../../lib/backend'

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

export default async function SelectCustomerPage({ searchParams }: PageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const requestedReturnTo = Array.isArray(resolvedSearchParams.returnTo)
    ? resolvedSearchParams.returnTo[0] || '/'
    : resolvedSearchParams.returnTo || '/'
  const returnTo = requestedReturnTo.startsWith('/') ? requestedReturnTo : '/'
  const customers = await loadCustomers()

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

        {customers.length > 0 ? (
          <CustomerPickerClient customers={customers} returnTo={returnTo} />
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
