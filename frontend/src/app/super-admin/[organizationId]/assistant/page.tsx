import { notFound } from 'next/navigation'

import { AgentChatPanel } from '../../../../components/AgentChatPanel'
import { SuperAdminCustomerHeader } from '../../../../components/SuperAdminCustomerIcons'
import { fetchCustomerRecord, fetchCustomerZoningKnowledgeStatus } from '../../../admin/actions'
import { getServerBackendOrigin } from '../../../../lib/backend'
import { getClerkManagementClient } from '../../../../lib/clerk'
import { getPermissionContext } from '../../../../lib/permissions'
import { DEFAULT_ASSISTANT_TARGET_ID } from '../../../../components/assistantTargetIds'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerAssistantPage({ params }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)
  const backendBase = getServerBackendOrigin()
  const agentId = DEFAULT_ASSISTANT_TARGET_ID

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
  const tenantRecord = await fetchCustomerRecord(organizationId)

  if (!organization) {
    notFound()
  }

  const displayName = organization.name
  const zoningKnowledgeStatus = await fetchCustomerZoningKnowledgeStatus(organizationId)
  const market =
    tenantRecord?.settings_json && typeof tenantRecord.settings_json.market === 'string'
      ? tenantRecord.settings_json.market
      : tenantRecord?.settings_json &&
          typeof (tenantRecord.settings_json as Record<string, unknown>).marketName === 'string'
        ? ((tenantRecord.settings_json as Record<string, unknown>).marketName as string)
        : null

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
        agentId={agentId}
        backendBase={backendBase}
        customerName={displayName}
        market={market}
        clientId={zoningKnowledgeStatus.client_id}
        showProModeToggle
        surface="super-admin-customer-assistant"
        title=""
        description=""
        variant="chatgpt"
      />
    </div>
  )
}
