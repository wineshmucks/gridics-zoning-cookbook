import { CustomerPickerClient } from '../../components/CustomerPickerClient'
import { buildBackendApiUrl } from '../../lib/backend'

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
    const response = await fetch(buildBackendApiUrl('/api/public/customers'), { cache: 'no-store' })
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
    <section className="card" style={{ maxWidth: 720, margin: '48px auto' }}>
      <h1 className="section-title">Choose a Customer</h1>
      <p style={{ color: 'var(--muted)', marginTop: 0 }}>
        Select the customer organization you want to work in before continuing.
      </p>
      {customers.length > 0 ? (
        <CustomerPickerClient customers={customers} returnTo={returnTo} />
      ) : (
        <p style={{ color: 'var(--muted)', marginBottom: 0 }}>
          No active customer organizations are available right now.
        </p>
      )}
      <p style={{ color: 'var(--muted)', marginBottom: 0 }}>
        The selected URL will include the customer org in the path so the customer stays in context.
      </p>
    </section>
  )
}
