import { notFound } from 'next/navigation'

import { AgentChatPanel } from '../../../../../components/AgentChatPanel'
import { fetchCustomerZoningKnowledgeStatus } from '../../../../admin/actions'
import { getClerkManagementClient } from '../../../../../lib/clerk'
import { getPermissionContext } from '../../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerAssistantPage({ params }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)
  const backendBase =
    process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || 'http://localhost:8000'

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only super admins can access the customer assistant.
        </p>
      </section>
    )
  }

  const { organizationId } = await params
  const client = await getClerkManagementClient()
  const organizations = await client.organizations.getOrganizationList({
    includeMembersCount: true,
    limit: 100,
  })
  const organization = organizations.data.find((item) => item.id === organizationId)

  if (!organization) {
    notFound()
  }

  const zoningKnowledgeStatus = await fetchCustomerZoningKnowledgeStatus(organizationId)

  return (
    <div className="panel-stack">
      <div className="admin-header">
        <div>
          <div className="eyebrow">Assistant</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            {organization.name}
          </h1>
          <p className="admin-copy">
            Chat with the customer-scoped zoning assistant using the current knowledge corpus.
          </p>
        </div>
      </div>

      <AgentChatPanel
        agentId="customer-zoning-agent"
        backendBase={backendBase}
        customerName={organization.name}
        clientId={zoningKnowledgeStatus.client_id}
        surface="super-admin-customer-assistant"
        title="Assistant"
        description="Customer-scoped zoning chat"
        variant="chatgpt"
      />
    </div>
  )
}
