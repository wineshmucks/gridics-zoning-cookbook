import { fetchPlatformAssistantSettings } from '../../../app/admin/actions'
import { PlatformAssistantSetupPanel } from '../../../components/PlatformAssistantSetupPanel'
import { SuperAdminWorkspaceShell } from '../../../components/SuperAdminWorkspaceShell'
import { getPermissionContext } from '../../../lib/permissions'

export default async function SuperAdminPlatformAssistantSetupPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can manage platform agentic defaults.
        </p>
      </section>
    )
  }

  const settings = await fetchPlatformAssistantSettings()

  return (
    <SuperAdminWorkspaceShell>
      <PlatformAssistantSetupPanel initialSettings={settings} />
    </SuperAdminWorkspaceShell>
  )
}
