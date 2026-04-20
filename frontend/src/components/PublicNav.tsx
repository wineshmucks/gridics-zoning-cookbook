'use client'

import Link from 'next/link'

import { appendScopePathToHref, buildAssistantHref, buildLettersHref } from '../lib/org-url'
import type { UzoneProduct } from '../lib/product-routing'
import { useHydratedPathname } from '../lib/use-hydrated-pathname'
import { isAgenticPickerRoute } from '../lib/public-branding'

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

export function PublicNav({
  orgId,
  scopePath,
  currentHost,
  currentProduct,
}: {
  orgId: string | null
  scopePath: string | null
  currentHost: string | null
  currentProduct: UzoneProduct
}) {
  const pathname = useHydratedPathname() || '/'
  const isJurisdictionPicker = isAgenticPickerRoute(pathname)

  if (currentProduct !== 'letters' || isJurisdictionPicker) {
    return null
  }

  return (
    <nav className="nav nav-public" aria-label="Primary">
      {navItems.map((item) => {
        const href =
          item.href === '/ai-assistant'
            ? buildAssistantHref(scopePath, currentHost)
            : item.href === '/'
              ? buildLettersHref(scopePath, currentHost)
              : appendScopePathToHref(item.href, scopePath)
        const normalizedHref = item.href.split('#', 1)[0]
        const isActive =
          normalizedHref === '/'
            ? currentProduct === 'letters' &&
              (pathname === '/' || (scopePath ? pathname === scopePath : pathname === `/${orgId}`))
            : normalizedHref !== '' &&
              (scopePath
                ? pathname === `${scopePath}${normalizedHref}` || pathname.startsWith(`${scopePath}${normalizedHref}/`)
                : pathname.startsWith(normalizedHref))
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
