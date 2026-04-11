import { notFound } from 'next/navigation'

import { AdminSectionPage } from '../../../components/AdminSectionPage'
import { getAdminSection } from '../../../lib/admin-sections'
import { getPermissionContext } from '../../../lib/permissions'

type PageProps = {
  params: Promise<{
    section: string
  }>
}

export default async function AdminSectionRoute({ params }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.canAccessAdminScreens) {
    return (
      <section className="card">
        <h1 className="section-title">Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          You need Clerk admin access for the current jurisdiction organization.
        </p>
      </section>
    )
  }

  const { section } = await params
  const config = getAdminSection(section)

  if (!config) {
    notFound()
  }

  return <AdminSectionPage section={config} />
}
