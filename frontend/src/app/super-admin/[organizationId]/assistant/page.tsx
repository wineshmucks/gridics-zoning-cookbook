import { notFound } from 'next/navigation'

import { AgentChatPanel } from '../../../../components/AgentChatPanel'
import { CUSTOMER_ZONING_ASSISTANT_ROUTE_ID } from '../../../../components/assistantRouteIds'
import { SuperAdminCustomerHeader } from '../../../../components/SuperAdminCustomerIcons'
import { fetchCustomerZoningKnowledgeStatus } from '../../../admin/actions'
import { getClerkManagementClient } from '../../../../lib/clerk'
import { getPermissionContext } from '../../../../lib/permissions'

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
          Only super admins can access the jurisdiction assistant.
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

  const displayName = organization.name
  const zoningKnowledgeStatus = await fetchCustomerZoningKnowledgeStatus(organizationId)

  return (
    <div className="panel-stack">
      <section className="card">
        <SuperAdminCustomerHeader
          icon="assistant"
          eyebrow="Assistant"
          title="Assistant"
          description="Chat with the jurisdiction-scoped assistant using the current zoning knowledge base."
        />
      </section>

      <AgentChatPanel
        agentId={CUSTOMER_ZONING_ASSISTANT_ROUTE_ID}
        backendBase={backendBase}
        customerName={displayName}
        clientId={zoningKnowledgeStatus.client_id}
        surface="super-admin-customer-assistant"
        title=""
        description=""
        variant="chatgpt"
      />
    </div>
  )
}
