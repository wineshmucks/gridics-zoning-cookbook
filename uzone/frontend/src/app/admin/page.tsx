import { redirect } from 'next/navigation'

import { AdminDashboardClient } from '../../components/AdminDashboardClient'
import { getPermissionContext } from '../../lib/permissions'

type PageProps = {
  searchParams?: Promise<{
    clientid?: string | string[]
  }>
}

export default async function AdminPage({ searchParams }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const permissions = await getPermissionContext(clerkEnabled)
  const requestedClientId = Array.isArray(resolvedSearchParams.clientid)
    ? resolvedSearchParams.clientid[0] || null
    : resolvedSearchParams.clientid || null

  if (!permissions.canAccessAdminScreens) {
    return (
      <section className="card">
        <h1 className="section-title">Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          You need Clerk admin access for the current customer organization. Super admins must belong
          to the Gridics organization with the admin role.
        </p>
      </section>
    )
  }

  const selectedClientId =
    permissions.selectedAdminMembership?.clientId || permissions.selectedAdminMembership?.organizationId || null

  if (selectedClientId && requestedClientId !== selectedClientId) {
    const params = new URLSearchParams()
    params.set('clientid', selectedClientId)
    redirect(`/admin?${params.toString()}`)
  }

  return <AdminDashboardClient clerkEnabled={clerkEnabled} />
}
