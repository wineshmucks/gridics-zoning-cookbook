import { notFound } from 'next/navigation'

import {
  fetchCustomerAssistantConversationReview,
  fetchCustomerEmbedSettings,
  fetchCustomerExperienceSettings,
  fetchPlatformAssistantSettings,
  fetchCustomerZoningKnowledgeStatus,
} from '../../../../admin/actions'
import { CustomerAssistantSetupPanel } from '../../../../../components/CustomerAssistantSetupPanel'
import { getClerkManagementClient } from '../../../../../lib/clerk'
import { getPermissionContext } from '../../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
  searchParams: Promise<{
    section?: string
    page?: string
    search?: string
    conversation_id?: string
  }>
}

export default async function SuperAdminCustomerAssistantSetupPage({ params, searchParams }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="super-admin-empty-state">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Only super admins can manage jurisdiction agent setup.</p>
      </section>
    )
  }

  const { organizationId } = await params
  const query = await searchParams
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
  const [experienceSettings, embedSettings, zoningKnowledgeStatus, baselineSettings, conversationReview] =
    await Promise.all([
    fetchCustomerExperienceSettings(organizationId),
    fetchCustomerEmbedSettings(organizationId),
    fetchCustomerZoningKnowledgeStatus(organizationId),
    fetchPlatformAssistantSettings(),
    fetchCustomerAssistantConversationReview(organizationId, {
      page: query.page ? Number(query.page) : undefined,
      search: query.search,
      conversationId: query.conversation_id,
    }),
  ])

  return (
    <CustomerAssistantSetupPanel
      customer={{
        id: organization.id,
        name: displayName,
        slug: organization.slug,
        customerId: organization.id,
      }}
      experienceSettings={experienceSettings}
      embedSettings={embedSettings}
      zoningKnowledgeStatus={zoningKnowledgeStatus}
      baselineSettings={baselineSettings}
      conversationReview={conversationReview}
    />
  )
}
