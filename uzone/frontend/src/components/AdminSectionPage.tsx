import Link from 'next/link'
import { headers } from 'next/headers'

import type { AdminSection } from '../lib/admin-sections'
import { AdminSidebar } from './AdminSidebar'
import { AdminEmailTemplatesPage } from './AdminEmailTemplatesPage'
import { AdminFeeStructurePage } from './AdminFeeStructurePage'
import { AdminHomePagePage } from './AdminHomePagePage'
import { AdminSectionTitle } from './AdminSectionTitle'

export async function AdminSectionPage({ section }: { section: AdminSection }) {
  const headerStore = await headers()
  const currentOrgId = headerStore.get('x-uzone-orgid') || null
  const adminOverviewHref = currentOrgId ? `/${encodeURIComponent(currentOrgId)}/admin` : '/admin'

  if (section.slug === 'email-settings') {
    return (
      <div className="admin-layout">
        <AdminSidebar />
        <div className="admin-content">
          <AdminEmailTemplatesPage />
        </div>
      </div>
    )
  }

  if (section.slug === 'fee-structure') {
    return (
      <div className="admin-layout">
        <AdminSidebar />
        <div className="admin-content">
          <AdminFeeStructurePage />
        </div>
      </div>
    )
  }

  if (section.slug === 'home-page') {
    return (
      <div className="admin-layout">
        <AdminSidebar />
        <div className="admin-content">
          <AdminHomePagePage />
        </div>
      </div>
    )
  }

  return (
    <div className="admin-layout">
      <AdminSidebar />

      <section className="card admin-section-detail admin-content">
        <div className="admin-header">
          <div>
            <div className="eyebrow">Admin</div>
            <AdminSectionTitle icon={section.icon} title={section.title}>
              <p className="admin-copy">{section.description}</p>
            </AdminSectionTitle>
          </div>
          <Link href={adminOverviewHref} className="button secondary">
            Overview
          </Link>
        </div>

        <div className="admin-section-placeholder">
          <div className="admin-section-placeholder-copy">
            <h2 className="admin-section-title">Management Surface</h2>
            <p className="admin-section-copy">
              This section is the entry point for managing {section.title.toLowerCase()} for the
              current jurisdiction.
            </p>
          </div>
          <div className="admin-section-meta">Source mock: {section.mockFile}</div>
        </div>
      </section>
    </div>
  )
}
