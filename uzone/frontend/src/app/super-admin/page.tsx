import { SuperAdminPanel } from '../../components/SuperAdminPanel'
import { getPermissionContext } from '../../lib/permissions'

type PageProps = {
  searchParams?: Promise<{
    status?: string | string[]
    customerName?: string | string[]
  }>
}

export default async function SuperAdminPage({ searchParams }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const status = Array.isArray(resolvedSearchParams.status)
    ? resolvedSearchParams.status[0] || null
    : resolvedSearchParams.status || null
  const customerName = Array.isArray(resolvedSearchParams.customerName)
    ? resolvedSearchParams.customerName[0] || null
    : resolvedSearchParams.customerName || null
  const flashMessage =
    status === 'customer-deleted' ? `${customerName || 'Customer'} was deleted.` : null

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can access customer management.
        </p>
      </section>
    )
  }

  return <SuperAdminPanel flashMessage={flashMessage} />
}
