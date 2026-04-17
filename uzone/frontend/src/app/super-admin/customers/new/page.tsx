import { SuperAdminCustomerCreateClient } from '../../../../components/SuperAdminCustomerCreateClient'
import { SuperAdminWorkspaceShell } from '../../../../components/SuperAdminWorkspaceShell'
import { getMarketOptions } from '../../../../lib/markets'
import { getPermissionContext } from '../../../../lib/permissions'

export default async function SuperAdminNewCustomerPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only super admins can add customers.
        </p>
      </section>
    )
  }

  const marketOptions = getMarketOptions()

  return (
    <SuperAdminWorkspaceShell>
      <SuperAdminCustomerCreateClient marketOptions={marketOptions} />
    </SuperAdminWorkspaceShell>
  )
}
