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
  const client = await getClerkManagementClient()
  const organizations = await client.organizations.getOrganizationList({
    includeMembersCount: true,
    limit: 100,
  })
  const organization = organizations.data.find((item) => item.id === organizationId)

  if (!organization) {
    notFound()
  }

  const [membershipResponse, invitationResponse] = await Promise.all([
    client.organizations.getOrganizationMembershipList({
      organizationId,
      role: ['org:admin'],
      limit: 100,
    }),
    client.organizations.getOrganizationInvitationList({
      organizationId,
      limit: 100,
    }),
  ])

  const adminMembers = membershipResponse.data.map((membership) => ({
    userId: membership.publicUserData?.userId || membership.id,
    identifier: membership.publicUserData?.identifier || 'Unknown user',
    name:
      [membership.publicUserData?.firstName, membership.publicUserData?.lastName]
        .filter(Boolean)
        .join(' ') || membership.publicUserData?.identifier || 'Unknown user',
    role: membership.role,
  }))

  const pendingInvites = invitationResponse.data
    .filter((invitation) => invitation.role === 'org:admin' && invitation.status === 'pending')
    .map((invitation) => ({
      id: invitation.id,
      emailAddress: invitation.emailAddress,
      role: invitation.role,
      status: invitation.status || 'pending',
    }))
  const tenantRecord = await fetchCustomerRecord(organizationId)

  return (
    <SuperAdminCustomerManageClient
      customer={{
        id: organization.id,
        name: organization.name,
        slug: organization.slug,
        customerId: organization.id,
        isActive: tenantRecord?.is_active ?? null,
      }}
      adminMembers={adminMembers}
      pendingInvites={pendingInvites}
    />
  )
}
