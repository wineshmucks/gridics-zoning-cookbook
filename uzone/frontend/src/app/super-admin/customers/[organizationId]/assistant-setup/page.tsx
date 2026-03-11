import { notFound } from 'next/navigation'

import {
  fetchCustomerExperienceSettings,
  fetchCustomerZoningKnowledgeStatus,
} from '../../../../admin/actions'
import { CustomerAssistantSetupPanel } from '../../../../../components/CustomerAssistantSetupPanel'
import { getClerkManagementClient } from '../../../../../lib/clerk'
import { getPermissionContext } from '../../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerAssistantSetupPage({ params }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only super admins can manage customer assistant setup.
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

  const [experienceSettings, zoningKnowledgeStatus] = await Promise.all([
    fetchCustomerExperienceSettings(organizationId),
    fetchCustomerZoningKnowledgeStatus(organizationId),
  ])

  return (
    <div className="panel-stack">
      <div className="admin-header">
        <div>
          <div className="eyebrow">Assistant Setup</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            {organization.name}
          </h1>
          <p className="admin-copy">
            Save the zoning code source, run ingestion, and inspect the customer knowledge base.
          </p>
        </div>
      </div>

      <CustomerAssistantSetupPanel
        customer={{
          id: organization.id,
          name: organization.name,
          slug: organization.slug,
          customerId: organization.id,
        }}
        experienceSettings={experienceSettings}
        zoningKnowledgeStatus={zoningKnowledgeStatus}
      />
    </div>
  )
}
