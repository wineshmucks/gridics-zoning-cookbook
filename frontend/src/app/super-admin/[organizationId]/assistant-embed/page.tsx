import { notFound } from 'next/navigation'

import { fetchCustomerEmbedSettings } from '../../../admin/actions'
import { CustomerAssistantEmbedPreview } from '../../../../components/CustomerAssistantEmbedPreview'
import { SuperAdminCustomerHeader } from '../../../../components/SuperAdminCustomerIcons'
import { getClerkManagementClient } from '../../../../lib/clerk'
import { getPermissionContext } from '../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
  searchParams?: Promise<{
    secret?: string | string[]
    origin?: string | string[]
  }>
}

export default async function SuperAdminCustomerAssistantEmbedPage({ params, searchParams }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)
  const backendBase = process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || ''

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          Only super admins can preview jurisdiction embeds.
        </p>
      </section>
    )
  }

  const { organizationId } = await params
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const initialOrigin = Array.isArray(resolvedSearchParams.origin)
    ? resolvedSearchParams.origin[0] || null
    : resolvedSearchParams.origin || null
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
  const embedSettings = await fetchCustomerEmbedSettings(organizationId)

  return (
    <div className="panel-stack">
      <section className="card">
        <SuperAdminCustomerHeader
          icon="assistant"
          eyebrow="Assistant Embed Preview"
          title="Embed Preview"
          description="Mint a short-lived token and preview the widget inside an iframe exactly as a host site would."
        />
      </section>

      <CustomerAssistantEmbedPreview
        backendBase={backendBase}
        customer={{
          id: organization.id,
          name: displayName,
        }}
        embedSettings={embedSettings}
        initialOrigin={initialOrigin}
      />
    </div>
  )
}
