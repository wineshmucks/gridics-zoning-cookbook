import { redirect } from 'next/navigation'

import { AdminDashboardClient } from '../../components/AdminDashboardClient'
import { getCurrentOrgId, getCurrentScopePath } from '../../lib/org-context'
import { getPermissionContext } from '../../lib/permissions'

export default async function AdminPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)
  const requestedOrgId = await getCurrentOrgId()
  const currentScopePath = await getCurrentScopePath()

  if (!permissions.canAccessAdminScreens) {
    return (
      <section className="card">
        <h1 className="section-title">Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          You need Clerk admin access for the current jurisdiction organization. Super admins must belong
          to the Gridics organization with the admin role.
        </p>
      </section>
    )
  }

  const selectedOrganizationId = permissions.selectedAdminMembership?.organizationId || null

  if (selectedOrganizationId && requestedOrgId !== selectedOrganizationId) {
    redirect(`/${encodeURIComponent(selectedOrganizationId)}/admin`)
  }

  return <AdminDashboardClient clerkEnabled={clerkEnabled} currentScopePath={currentScopePath} />
}
