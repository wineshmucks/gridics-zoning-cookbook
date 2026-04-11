import { notFound } from 'next/navigation'
import type { ReactNode } from 'react'

import { fetchCustomerRecord } from '../../../../app/admin/actions'
import { SuperAdminCustomerSidebar } from '../../../../components/SuperAdminCustomerSidebar'
import { getClerkManagementClient } from '../../../../lib/clerk'
import { getPermissionContext } from '../../../../lib/permissions'

type LayoutProps = {
  children: ReactNode
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerLayout({ children, params }: LayoutProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="super-admin-empty-state">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Only super admins can manage customers.</p>
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

  const displayName = organization?.name || tenantRecord?.city_name || organizationId

  return (
    <div className="super-admin-shell">
      <div className="super-admin-layout">
        <SuperAdminCustomerSidebar
          customer={{
            id: organizationId,
            name: displayName,
            slug: organization?.slug || null,
            customerId: organization?.id || tenantRecord?.clerk_organization_id || organizationId,
          }}
        />
        <div className="super-admin-content">{children}</div>
      </div>
    </div>
  )
}
