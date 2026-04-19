import { SuperAdminDatabaseClient } from '../../../components/SuperAdminDatabaseClient'
import { SuperAdminWorkspaceShell } from '../../../components/SuperAdminWorkspaceShell'
import { fetchDatabaseInfo } from '../../admin/actions'
import { getPermissionContext } from '../../../lib/permissions'

export default async function SuperAdminDatabasePage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can access the database screen.
        </p>
      </section>
    )
  }

  let databaseInfo = null
  let loadError: string | null = null

  try {
    databaseInfo = await fetchDatabaseInfo()
  } catch {
    loadError = 'Unable to load database information.'
  }

  return (
    <SuperAdminWorkspaceShell>
      <SuperAdminDatabaseClient databaseInfo={databaseInfo} loadError={loadError} />
    </SuperAdminWorkspaceShell>
  )
}
