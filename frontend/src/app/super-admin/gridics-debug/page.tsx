import { SuperAdminGridicsDebugClient } from '../../../components/SuperAdminGridicsDebugClient'
import { SuperAdminWorkspaceShell } from '../../../components/SuperAdminWorkspaceShell'
import { getPermissionContext } from '../../../lib/permissions'

export default async function SuperAdminGridicsDebugPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can access the debug screen.
        </p>
      </section>
    )
  }

  return (
    <SuperAdminWorkspaceShell>
      <SuperAdminGridicsDebugClient />
    </SuperAdminWorkspaceShell>
  )
}
