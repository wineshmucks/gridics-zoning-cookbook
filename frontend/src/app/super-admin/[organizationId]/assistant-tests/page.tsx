import { notFound } from 'next/navigation'

import { fetchCustomerRecord } from '../../../admin/actions'
import { SuperAdminAssistantTestsClient } from '../../../../components/SuperAdminAssistantTestsClient'
import { SuperAdminCustomerHeader } from '../../../../components/SuperAdminCustomerIcons'
import { getPermissionContext } from '../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminAssistantTestsPage({ params }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only Gridics super admins can define and run assistant tests.
        </p>
      </section>
    )
  }

  const { organizationId } = await params
  const customer = await fetchCustomerRecord(organizationId)

  if (!customer) {
    notFound()
  }

  return (
    <div className="panel-stack">
      <section className="card">
        <SuperAdminCustomerHeader
          icon="assistant-setup"
          eyebrow="Assistant Tests"
          title="Assistant Tests"
          description="Define and run assistant test cases for this jurisdiction using explicit session state."
        />
      </section>
      <SuperAdminAssistantTestsClient customer={customer} />
    </div>
  )
}
