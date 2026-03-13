'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { appendOrgIdToHref } from '../lib/org-url'

type NavItem = {
  href: string
  label: string
  requiresJurisdiction?: boolean
}

const navItems: NavItem[] = [
  { href: '/', label: 'Zoning Letters', requiresJurisdiction: true },
  { href: '/assistant', label: 'Assistant', requiresJurisdiction: true },
  { href: '/request/new', label: 'Property Search', requiresJurisdiction: true },
  { href: '/#features-section', label: 'Resources', requiresJurisdiction: true },
  { href: '/#cta-section', label: 'Contact', requiresJurisdiction: true },
]

export function PublicNav({ orgId }: { orgId: string | null }) {
  const pathname = usePathname()

  return (
    <nav className="nav nav-public" aria-label="Primary">
      {navItems.map((item) => {
        const href = appendOrgIdToHref(item.href, orgId)
        const normalizedHref = item.href.split('#', 1)[0]
        const isActive =
          normalizedHref === '/'
            ? pathname === '/' || pathname === `/${orgId}`
            : normalizedHref !== '' && pathname.startsWith(normalizedHref)
        const isDisabled = item.requiresJurisdiction && !orgId

        if (isDisabled) {
          return (
            <span
              key={item.label}
              className="nav-public-link is-disabled"
              aria-disabled="true"
              title="Choose a jurisdiction to unlock this area."
            >
              {item.label}
            </span>
          )
        }

        return (
          <Link
            key={item.label}
            href={href}
            className={`nav-public-link${isActive ? ' is-active' : ''}`}
          >
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}
