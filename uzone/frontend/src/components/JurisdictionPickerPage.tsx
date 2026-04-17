import { JurisdictionPickerClient } from './JurisdictionPickerClient'
import { buildServerBackendApiUrl } from '../lib/backend'
import { isSelectableJurisdiction, type JurisdictionPickerCustomer } from '../lib/jurisdiction-picker'

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

    const customers = (await response.json()) as JurisdictionPickerCustomer[]
    return customers.filter(isSelectableJurisdiction)
  } catch {
    return []
  }
}

export async function JurisdictionPickerPage({ searchParams }: PageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const requestedReturnTo = Array.isArray(resolvedSearchParams.returnTo)
    ? resolvedSearchParams.returnTo[0] || '/'
    : resolvedSearchParams.returnTo || '/'
  const returnTo = requestedReturnTo.startsWith('/') ? requestedReturnTo : '/'
  const customers = await loadCustomers()
  const suggestedCustomers = customers.slice(0, 4)

  return (
    <section className="jurisdiction-picker-page">
      <div className="jurisdiction-picker-shell">
        <div className="jurisdiction-picker-hero jurisdiction-picker-hero-instruction">
          <h1 className="jurisdiction-picker-title">Select a jurisdiction to continue</h1>
          <p className="subtitle jurisdiction-picker-subtitle">
            The assistant works within a specific city or region. Search and select your jurisdiction to get started.
          </p>
        </div>

        {customers.length > 0 ? (
          <JurisdictionPickerClient
            customers={customers}
            suggestedCustomers={suggestedCustomers}
            returnTo={returnTo}
          />
        ) : (
          <section className="card jurisdiction-picker-empty jurisdiction-picker-empty-state">
            <h2 className="section-title">No jurisdictions available</h2>
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
