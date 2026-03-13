'use client'

import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'

import { SuperAdminCustomerIcon } from './SuperAdminCustomerIcons'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

const customerNav = [
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}`,
    label: 'Jurisdiction Details',
    description: 'Overview, lifecycle controls, and admin users.',
    icon: 'jurisdiction-details' as const,
  },
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}/assistant-setup`,
    label: 'Assistant Setup',
    description: 'Save the zoning code URL, ingest content, and inspect knowledge status.',
    icon: 'assistant-setup' as const,
  },
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}/assistant`,
    label: 'Assistant',
    description: 'Open the customer-scoped zoning chat interface.',
    icon: 'assistant' as const,
  },
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}?section=admin-users`,
    label: 'Admin Users',
    description: 'Invites, assignments, and pending access.',
    icon: 'admin-users' as const,
  },
]

export function SuperAdminCustomerSidebar({ customer }: { customer: SelectedCustomer }) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const baseHref = `/super-admin/customers/${customer.id}`
  const activeSection = searchParams.get('section') === 'admin-users' ? 'admin-users' : 'general'

  return (
    <aside className="super-admin-sidebar">
      <div className="admin-list super-admin-customer-card">
        <div className="admin-list-heading">{customer.name}</div>
        <div className="super-admin-meta">{customer.customerId || 'Organization ID unavailable'}</div>
        <div className="super-admin-meta">{customer.slug || 'no-slug'}</div>
      </div>

      <div className="super-admin-sidebar-group">
        <nav className="super-admin-nav" aria-label="Jurisdiction management navigation">
          {customerNav.map((item) => {
            const href = item.href(customer.id)
            const isActive =
              item.label === 'Admin Users'
                ? pathname === baseHref && activeSection === 'admin-users'
                : item.label === 'Jurisdiction Details'
                  ? pathname === baseHref && activeSection === 'general'
                  : pathname === href

            return (
              <Link
                key={href}
                href={href}
                className={`super-admin-nav-item super-admin-nav-link${isActive ? ' is-active' : ''}`}
              >
                <span className="super-admin-nav-head">
                  <SuperAdminCustomerIcon name={item.icon} />
                  <span className="super-admin-nav-label">{item.label}</span>
                </span>
                <span className="super-admin-nav-description">{item.description}</span>
              </Link>
            )
          })}
        </nav>
      </div>

      <div className="super-admin-sidebar-footer">
        <Link href="/super-admin" className="button secondary super-admin-sidebar-back">
          <SuperAdminCustomerIcon name="back" />
          Back to Jurisdictions
        </Link>
      </div>
    </aside>
  )
}
