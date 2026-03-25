import { notFound } from 'next/navigation'

import { fetchCustomerRecord } from '../../../../app/admin/actions'
import { SuperAdminCustomerManageClient } from '../../../../components/SuperAdminCustomerManageClient'
import { getClerkManagementClient } from '../../../../lib/clerk'
import { getPermissionContext } from '../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerPage({ params }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only super admins can manage customers.
        </p>
      </section>
    )
  }

  const { organizationId } = await params
  const tenantRecord = await fetchCustomerRecord(organizationId)
  const client = await getClerkManagementClient()
  const organization = tenantRecord?.clerk_organization_id
    ? await client.organizations
        .getOrganization({ organizationId: tenantRecord.clerk_organization_id })
        .catch(() => null)
    : await client.organizations.getOrganization({ organizationId }).catch(() => null)

  if (!tenantRecord && !organization) {
    notFound()
  }

  const [adminMembers, pendingInvites] = organization
    ? await Promise.all([
        client.organizations
          .getOrganizationMembershipList({
            organizationId: organization.id,
            role: ['org:admin'],
            limit: 100,
          })
          .then((membershipResponse) =>
            membershipResponse.data.map((membership) => ({
              userId: membership.publicUserData?.userId || membership.id,
              identifier: membership.publicUserData?.identifier || 'Unknown user',
              name:
                [membership.publicUserData?.firstName, membership.publicUserData?.lastName]
                  .filter(Boolean)
                  .join(' ') || membership.publicUserData?.identifier || 'Unknown user',
              role: membership.role,
            })),
          ),
        client.organizations
          .getOrganizationInvitationList({
            organizationId: organization.id,
            limit: 100,
          })
          .then((invitationResponse) =>
            invitationResponse.data
              .filter((invitation) => invitation.role === 'org:admin' && invitation.status === 'pending')
              .map((invitation) => ({
                id: invitation.id,
                emailAddress: invitation.emailAddress,
                role: invitation.role,
                status: invitation.status || 'pending',
              })),
          ),
      ])
    : [[], []]

  return (
    <SuperAdminCustomerManageClient
      customer={{
        id: organizationId,
        clientId: tenantRecord?.client_id || organizationId,
        name: tenantRecord?.city_name || organization?.name || organizationId,
        departmentName: tenantRecord?.department_name || null,
        pathAlias:
          tenantRecord?.settings_json &&
          typeof tenantRecord.settings_json.path_alias === 'string'
            ? tenantRecord.settings_json.path_alias
            : tenantRecord?.settings_json &&
                typeof (tenantRecord.settings_json as Record<string, unknown>).pathAlias === 'string'
              ? ((tenantRecord.settings_json as Record<string, unknown>).pathAlias as string)
            : null,
        logoPath:
          tenantRecord?.settings_json &&
          typeof tenantRecord.settings_json.header_logo_path === 'string'
            ? tenantRecord.settings_json.header_logo_path
            : null,
        clerkOrganizationId: tenantRecord?.clerk_organization_id || organization?.id || organizationId,
        slug: organization?.slug || null,
        customerId: organization?.id || tenantRecord?.clerk_organization_id || null,
        isActive: tenantRecord?.is_active ?? null,
      }}
      adminMembers={adminMembers}
      pendingInvites={pendingInvites}
    />
  )
}
