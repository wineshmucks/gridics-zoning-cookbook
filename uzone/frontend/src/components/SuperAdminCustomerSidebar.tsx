'use client'

import { usePathname, useSearchParams } from 'next/navigation'

import { AdminSidebarGroup, AdminSidebarItem } from './AdminSurfacePrimitives'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

const agenticSections = [
  { id: 'general', label: 'Disclaimer', icon: 'jurisdiction-details' },
  { id: 'llm', label: 'LLM Setup', icon: 'assistant-setup' },
  { id: 'knowledge', label: 'Knowledge', icon: 'assistant' },
  { id: 'integrations', label: 'Integrations', icon: 'assistant-setup' },
] as const

export function SuperAdminCustomerSidebar({ customer }: { customer: SelectedCustomer }) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const baseHref = `/super-admin/customers/${customer.id}`
  const sectionParam = searchParams.get('section')
  const activeSection = sectionParam === 'admin-users' ? 'admin-users' : sectionParam || 'general'
  const agenticBaseHref = `/super-admin/customers/${customer.id}/assistant-setup`
  const isGeneralActive = pathname === baseHref && activeSection === 'general'
  const isAdminUsersActive = pathname === baseHref && activeSection === 'admin-users'
  return (
    <aside className="super-admin-sidebar">
      <div className="super-admin-sidebar-title">{customer.name}</div>
      <div className="super-admin-sidebar-group">
        <nav className="admin-sidebar-nav" aria-label="Jurisdiction management navigation">
          <AdminSidebarItem
            href={baseHref}
            label="General"
            active={isGeneralActive}
            icon="jurisdiction-details"
          />

          <AdminSidebarGroup label="Agentic Setup" defaultOpen icon="assistant-setup">
            {agenticSections.map((item) => {
              const href = `${agenticBaseHref}?section=${item.id}`
              const isActive = pathname === agenticBaseHref && activeSection === item.id

              return (
                <AdminSidebarItem
                  key={item.id}
                  href={href}
                  label={item.label}
                  active={isActive}
                  indent
                  icon={item.icon}
                />
              )
            })}
          </AdminSidebarGroup>

          <AdminSidebarItem
            href={`${baseHref}?section=admin-users`}
            label="Admin Users"
            active={isAdminUsersActive}
            icon="admin-users"
          />
        </nav>
      </div>

      <div className="super-admin-sidebar-footer">
        <AdminSidebarItem href="/super-admin" label="Exit Setup" icon="back" />
      </div>
    </aside>
  )
}
