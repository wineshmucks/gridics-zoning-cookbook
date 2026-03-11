import Link from 'next/link'

import { AgentChatPanel } from '../../../components/AgentChatPanel'
import { getPermissionContext } from '../../../lib/permissions'
import { getTenantConfig } from '../../../lib/tenant'

export default async function SuperAdminAssistantPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)
  const tenant = await getTenantConfig()
  const backendBase =
    process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || 'http://localhost:8000'

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can access the assistant screen.
        </p>
      </section>
    )
  }

  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="super-admin-toolbar">
        <Link href="/super-admin" className="button secondary">
          Back to Customers
        </Link>
      </div>

      <div className="admin-header">
        <div>
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Assistant
          </h1>
          <p className="admin-copy">
            This reusable assistant surface is now available from super admin and can be mounted in
            other UZone areas next.
          </p>
        </div>
        <div className="button-row">
          <a className="button" href={`${backendBase}/config`} target="_blank" rel="noreferrer">
            View Agent Service
          </a>
          {tenant.zoning_code_url ? (
            <a
              className="button secondary"
              href={tenant.zoning_code_url}
              target="_blank"
              rel="noreferrer"
            >
              Open Zoning Code
            </a>
          ) : null}
        </div>
      </div>

      <AgentChatPanel
        agentId="customer-zoning-agent"
        backendBase={backendBase}
        customerName={tenant.city_name}
        clientId={tenant.client_id}
        surface="super-admin-assistant"
        title="Deployment assistant"
        description="This assistant-ui surface runs against the backend AgentOS deployment for the active tenant and is structured for reuse in other screens."
      />
    </section>
  )
}
