'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { appendScopePathToHref, buildAssistantHref } from '../lib/org-url'

type NavItem = {
  href: string
  label: string
  requiresJurisdiction?: boolean
}

const navItems: NavItem[] = [
  { href: '/', label: 'Zoning Letters', requiresJurisdiction: true },
  { href: '/ai-assistant', label: 'Assistant', requiresJurisdiction: true },
  { href: '/request/new', label: 'Property Search', requiresJurisdiction: true },
  { href: '/#features-section', label: 'Resources', requiresJurisdiction: true },
  { href: '/#cta-section', label: 'Contact', requiresJurisdiction: true },
]

export function PublicNav({ orgId, scopePath }: { orgId: string | null, scopePath: string | null }) {
  const pathname = usePathname()
  const isAssistantSurface =
    pathname === '/ai-assistant' ||
    pathname.startsWith('/ai-assistant/') ||
    (scopePath ? pathname === `${scopePath}/assistant` || pathname.startsWith(`${scopePath}/assistant/`) : false)
  const isJurisdictionPicker = pathname === '/select-jurisdiction'

  if (isAssistantSurface || isJurisdictionPicker) {
    return null
  }

  return (
    <nav className="nav nav-public" aria-label="Primary">
      {navItems.map((item) => {
        const href =
          item.href === '/ai-assistant'
            ? buildAssistantHref(scopePath)
            : appendScopePathToHref(item.href, scopePath)
        const normalizedHref = item.href.split('#', 1)[0]
        const isActive =
          normalizedHref === '/'
            ? pathname === '/' || (scopePath ? pathname === scopePath : pathname === `/${orgId}`)
            : normalizedHref !== '' &&
              (scopePath ? pathname === `${scopePath}${normalizedHref}` || pathname.startsWith(`${scopePath}${normalizedHref}/`) : pathname.startsWith(normalizedHref))
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
            target={item.href === '/ai-assistant' ? '_blank' : undefined}
            rel={item.href === '/ai-assistant' ? 'noreferrer' : undefined}
            className={`nav-public-link${isActive ? ' is-active' : ''}`}
          >
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}
