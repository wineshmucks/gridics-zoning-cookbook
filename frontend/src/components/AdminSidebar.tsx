'use client'

import Link from 'next/link'

import { ADMIN_SECTIONS } from '../lib/admin-sections'
import { appendScopePathToHref } from '../lib/org-url'
import { AdminSectionIcon } from './AdminSectionIcon'

const SIDEBAR_SECTIONS = ADMIN_SECTIONS.filter((section) => section.slug !== 'jurisdictions')

export function AdminSidebar({
  currentScopePath,
  scopedPathname,
}: {
  currentScopePath: string | null
  scopedPathname: string
}) {

  return (
    <aside className="admin-sidebar">
      <div className="admin-sidebar-group">
        <div className="admin-sidebar-heading">Configuration</div>
        <nav className="admin-sidebar-nav" aria-label="Admin configuration navigation">
          <Link
            href={appendScopePathToHref('/admin', currentScopePath)}
            className={`admin-sidebar-home${scopedPathname === '/admin' ? ' is-active' : ''}`}
          >
            <AdminSectionIcon name="settings" />
            <span className="admin-sidebar-home-label">Admin Settings</span>
          </Link>

          {SIDEBAR_SECTIONS.map((section) => {
            const href = appendScopePathToHref(`/admin/${section.slug}`, currentScopePath)
            const isActive = scopedPathname === `/admin/${section.slug}`

            return (
              <Link
                key={section.slug}
                href={href}
                className={`admin-sidebar-item${isActive ? ' is-active' : ''}`}
              >
                <AdminSectionIcon name={section.icon} />
                <span className="admin-sidebar-item-label">{section.title}</span>
              </Link>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
