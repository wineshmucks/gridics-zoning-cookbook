'use client'

import Link from 'next/link'

import { ADMIN_SECTIONS } from '../lib/admin-sections'

export function AdminDashboardClient({ clerkEnabled: _clerkEnabled }: { clerkEnabled: boolean }) {
  return (
    <section className="admin-sections">
      <div className="card admin-sections-hero">
        <div>
          <div className="eyebrow">Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Admin Settings
          </h1>
          <p className="admin-copy" style={{ maxWidth: 720 }}>
            Choose a section to manage customer-specific administration settings.
          </p>
        </div>
      </div>

      <div className="admin-section-grid">
        {ADMIN_SECTIONS.map((section) => (
          <Link key={section.slug} href={`/admin/${section.slug}`} className="card admin-section-card">
            <div className="admin-section-card-top">
              <span className="pill">Manage</span>
            </div>
            <div>
              <h2 className="admin-section-title">{section.title}</h2>
              <p className="admin-section-copy">{section.description}</p>
            </div>
            <div className="admin-section-meta">Mock reference: {section.mockFile}</div>
          </Link>
        ))}
      </div>
    </section>
  )
}
