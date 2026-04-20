import { SuperAdminPanel } from '../../components/SuperAdminPanel'
import { SuperAdminWorkspaceShell } from '../../components/SuperAdminWorkspaceShell'
import { getPermissionContext } from '../../lib/permissions'

type PageProps = {
  searchParams?: Promise<{
    status?: string | string[]
    customerName?: string | string[]
    created?: string | string[]
    updated?: string | string[]
    deactivated?: string | string[]
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
  const created = Array.isArray(resolvedSearchParams.created)
    ? resolvedSearchParams.created[0] || null
    : resolvedSearchParams.created || null
  const updated = Array.isArray(resolvedSearchParams.updated)
    ? resolvedSearchParams.updated[0] || null
    : resolvedSearchParams.updated || null
  const deactivated = Array.isArray(resolvedSearchParams.deactivated)
    ? resolvedSearchParams.deactivated[0] || null
    : resolvedSearchParams.deactivated || null
  let flashMessage: string | null = null
  let flashTone: 'success' | 'error' | null = null

  if (status === 'customer-deleted') {
    flashMessage = `${customerName || 'Jurisdiction'} was deleted.`
    flashTone = 'success'
  } else if (status === 'jurisdiction-purged') {
    flashMessage = `${customerName || 'Jurisdiction'} was purged.`
    flashTone = 'success'
  } else if (status === 'jurisdiction-purge-failed') {
    flashMessage = `Unable to purge ${customerName || 'jurisdiction'}.`
    flashTone = 'error'
  } else if (status === 'jurisdictions-synced') {
    flashMessage = `Jurisdictions synced from Clerk${created || updated || deactivated ? ` (${created || 0} created, ${updated || 0} updated, ${deactivated || 0} deactivated)` : ''}.`
    flashTone = 'success'
  }

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can access jurisdiction management.
        </p>
      </section>
    )
  }

  return (
    <SuperAdminWorkspaceShell>
      <SuperAdminPanel flashMessage={flashMessage} flashTone={flashTone} />
    </SuperAdminWorkspaceShell>
  )
}
