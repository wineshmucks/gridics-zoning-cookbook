'use client'

import { useSearchParams } from 'next/navigation'

import {
  buildAssistantHref,
  buildSuperAdminCustomerAssistantSetupPath,
  buildSuperAdminCustomerAssistantTestsPath,
  buildSuperAdminCustomerConversationsPath,
  buildSuperAdminCustomerPath,
} from '../lib/org-url'
import { AdminSidebarGroup, AdminSidebarItem } from './AdminSurfacePrimitives'
import { useHydratedPathname } from '../lib/use-hydrated-pathname'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
  pathAlias: string | null
  currentHost: string | null
}

export function SuperAdminCustomerSidebar({ customer }: { customer: SelectedCustomer }) {
  const pathname = useHydratedPathname()
  const searchParams = useSearchParams()
  const baseHref = buildSuperAdminCustomerPath(customer.id)
  const assistantSetupHref = buildSuperAdminCustomerAssistantSetupPath(customer.id)
  const assistantTestsHref = buildSuperAdminCustomerAssistantTestsPath(customer.id)
  const conversationsHref = buildSuperAdminCustomerConversationsPath(customer.id)
  const normalizedPathAlias =
    customer.pathAlias?.trim() ? (customer.pathAlias.startsWith('/') ? customer.pathAlias : `/${customer.pathAlias}`) : null
  const publicPageHref = normalizedPathAlias ? buildAssistantHref(normalizedPathAlias, customer.currentHost) : null
  const sectionParam = searchParams.get('section')
  const activeSection = sectionParam === 'admin-users' ? 'admin-users' : sectionParam || 'general'
  const currentPathname = pathname || ''
  const isAssistantSetupRoute =
    currentPathname === assistantSetupHref || currentPathname.startsWith(`${assistantSetupHref}/`)
  const isConversationsRoute =
    currentPathname === conversationsHref || currentPathname.startsWith(`${conversationsHref}/`)
  const isAssistantTestsRoute =
    currentPathname === assistantTestsHref || currentPathname.startsWith(`${assistantTestsHref}/`)
  const isGeneralActive = currentPathname === baseHref && activeSection === 'general'
  const isAdminUsersActive = currentPathname === baseHref && activeSection === 'admin-users'
  const agenticSetupItems = [
    { href: `${assistantSetupHref}?section=api-keys`, label: 'API Keys', icon: 'assistant-setup' as const },
    { href: `${assistantSetupHref}?section=knowledge`, label: 'Knowledge', icon: 'assistant' as const },
    { href: `${assistantSetupHref}?section=integrations`, label: 'Integrations', icon: 'assistant-setup' as const },
  ] as const
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
          <AdminSidebarGroup label="Agentic Setup" defaultOpen={isAssistantSetupRoute} icon="assistant-setup">
            {agenticSetupItems.map((item) => (
              <AdminSidebarItem
                key={item.href}
                href={item.href}
                label={item.label}
                active={sectionParam === item.href.split('section=', 2)[1]}
                indent
                icon={item.icon}
              />
            ))}
          </AdminSidebarGroup>
          <AdminSidebarItem
            href={assistantTestsHref}
            label="Assistant Tests"
            active={isAssistantTestsRoute}
            icon="assistant-setup"
          />
          <AdminSidebarItem
            href={conversationsHref}
            label="Conversations"
            active={isConversationsRoute}
            icon="conversations"
          />
          <AdminSidebarItem
            href={`${baseHref}?section=admin-users`}
            label="Admin Users"
            active={isAdminUsersActive}
            icon="admin-users"
          />
        </nav>
      </div>

      <div className="super-admin-sidebar-footer">
        {publicPageHref ? (
          <AdminSidebarItem
            href={publicPageHref}
            label="Assistant"
            icon="assistant"
            target="_blank"
            rel="noreferrer"
          />
        ) : null}
        <AdminSidebarItem href="/super-admin" label="Exit Setup" icon="back" />
      </div>
    </aside>
  )
}
