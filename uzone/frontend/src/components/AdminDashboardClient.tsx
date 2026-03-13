'use client'

import { AdminSidebar } from './AdminSidebar'
import { AdminSectionTitle } from './AdminSectionTitle'

export function AdminDashboardClient({ clerkEnabled: _clerkEnabled }: { clerkEnabled: boolean }) {
  return (
    <section className="admin-layout">
      <AdminSidebar />

      <div className="admin-content">
        <div className="card admin-sections-hero">
          <div>
            <div className="eyebrow">Admin</div>
            <AdminSectionTitle icon="settings" title="Admin Settings">
              <p className="admin-copy" style={{ maxWidth: 720 }}>
                Use the sidebar to move between jurisdiction-specific admin tools and configuration
                sections.
              </p>
            </AdminSectionTitle>
          </div>
        </div>

        <section className="card admin-section-detail">
          <div className="admin-section-placeholder">
            <div className="admin-section-placeholder-copy">
              <h2 className="admin-section-title">Configuration Workspace</h2>
              <p className="admin-section-copy">
                Pick a section from the sidebar to manage jurisdictions, forms, emails, fees,
                templates, homepage content, or permissions for the current jurisdiction.
              </p>
            </div>
          </div>
        </section>
      </div>
    </section>
  )
}
