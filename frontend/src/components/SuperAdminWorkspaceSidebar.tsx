'use client'

import { AdminSidebarItem } from './AdminSurfacePrimitives'
import { useHydratedPathname } from '../lib/use-hydrated-pathname'

const workspaceItems = [
  { href: '/super-admin', label: 'Jurisdictions', icon: 'jurisdiction-details' as const },
  { href: '/super-admin/database', label: 'Database', icon: 'database' as const },
  { href: '/super-admin/assistant-setup', label: 'Platform Agentic Setup', icon: 'assistant-setup' as const },
  { href: '/super-admin/gridics-debug', label: 'Gridics Debug', icon: 'assistant-setup' as const },
  { href: '/super-admin/new', label: 'Add Jurisdiction', icon: 'jurisdiction-details' as const },
] as const

function isItemActive(pathname: string | null, href: string) {
  if (!pathname) {
    return false
  }
  if (href === '/super-admin') {
    return pathname === '/super-admin'
  }
  return pathname === href || pathname.startsWith(`${href}/`)
}

export function SuperAdminWorkspaceSidebar() {
  const pathname = useHydratedPathname()

  return (
    <aside className="super-admin-sidebar super-admin-workspace-sidebar">
      <div className="super-admin-sidebar-title">Super Admin</div>
      <div className="super-admin-sidebar-subtitle">Platform controls</div>
      <div className="super-admin-sidebar-group">
        <nav className="admin-sidebar-nav" aria-label="Super admin navigation">
          {workspaceItems.map((item) => (
            <AdminSidebarItem
              key={item.href}
              href={item.href}
              label={item.label}
              active={isItemActive(pathname, item.href)}
              icon={item.icon}
            />
          ))}
        </nav>
        <div className="admin-sidebar-divider" />
        <nav className="admin-sidebar-nav" aria-label="Exit super admin">
          <AdminSidebarItem
            href="/"
            label="Exit Super Admin"
            active={false}
            icon="back"
          />
        </nav>
      </div>
    </aside>
  )
}
