import Link from 'next/link'

import type { AdminSection } from '../lib/admin-sections'
import { AdminEmailTemplatesPage } from './AdminEmailTemplatesPage'

export async function AdminSectionPage({ section }: { section: AdminSection }) {
  if (section.slug === 'email-settings') {
    return <AdminEmailTemplatesPage />
  }

  return (
    <div className="admin-sections">
      <section className="card admin-section-detail">
        <div className="admin-header">
          <div>
            <div className="eyebrow">Admin</div>
            <h1 className="section-title" style={{ marginBottom: 8 }}>
              {section.title}
            </h1>
            <p className="admin-copy">{section.description}</p>
          </div>
          <Link href="/admin" className="button secondary">
            Back to Admin
          </Link>
        </div>

        <div className="admin-section-placeholder">
          <div className="admin-section-placeholder-copy">
            <h2 className="admin-section-title">Management Surface</h2>
            <p className="admin-section-copy">
              This section is the entry point for managing {section.title.toLowerCase()} for the
              current customer.
            </p>
          </div>
          <div className="admin-section-meta">Source mock: {section.mockFile}</div>
        </div>
      </section>
    </div>
  )
}
