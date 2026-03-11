'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

const customerNav = [
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}`,
    label: 'Customer',
    description: 'Overview, lifecycle controls, and admin users.',
  },
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}/assistant-setup`,
    label: 'Assistant Setup',
    description: 'Save the zoning code URL, ingest content, and inspect knowledge status.',
  },
  {
    href: (organizationId: string) => `/super-admin/customers/${organizationId}/assistant`,
    label: 'Assistant',
    description: 'Open the customer-scoped zoning chat interface.',
  },
]

export function SuperAdminCustomerSidebar({ customer }: { customer: SelectedCustomer }) {
  const pathname = usePathname()

  return (
    <aside className="super-admin-sidebar">
      <div className="admin-list super-admin-customer-card">
        <Link href="/super-admin" className="button secondary super-admin-sidebar-back">
          Back to Customers
        </Link>
        <div className="admin-list-heading">{customer.name}</div>
        <div className="super-admin-meta">{customer.customerId || 'Organization ID unavailable'}</div>
        <div className="super-admin-meta">{customer.slug || 'no-slug'}</div>
      </div>

      <div className="super-admin-sidebar-group">
        <div className="super-admin-sidebar-heading">Customer</div>
        <nav className="super-admin-nav" aria-label="Customer management navigation">
          {customerNav.map((item) => {
            const href = item.href(customer.id)
            const isActive = pathname === href

            return (
              <Link
                key={href}
                href={href}
                className={`super-admin-nav-item super-admin-nav-link${isActive ? ' is-active' : ''}`}
              >
                <span className="super-admin-nav-label">{item.label}</span>
                <span className="super-admin-nav-description">{item.description}</span>
              </Link>
            )
          })}
        </nav>
      </div>
    </aside>
  )
}
