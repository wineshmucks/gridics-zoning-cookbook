import { notFound } from 'next/navigation'
import type { ReactNode } from 'react'

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

  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="super-admin-layout">
        <SuperAdminCustomerSidebar
          customer={{
            id: organization.id,
            name: organization.name,
            slug: organization.slug,
            customerId: organization.id,
          }}
        />
        <div className="super-admin-content">{children}</div>
      </div>
    </section>
  )
}
