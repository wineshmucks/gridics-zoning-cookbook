'use client'

import { useClerk } from '@clerk/nextjs'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { startTransition, useState } from 'react'

import type { ClientMembership } from '../lib/permissions'
import { buildInternalOrgScopePath, replaceScopePathInPathname } from '../lib/org-url'
import { BuildingLogo } from './BuildingLogo'

type Props = {
  clerkEnabled: boolean
  cityName: string
  departmentName: string
  logoUrl: string | null
  currentScopePath: string | null
  currentCustomerName: string | null
  adminMemberships: ClientMembership[]
  selectedAdminOrganizationId: string | null
}

export function HeaderBrand({
  clerkEnabled,
  cityName,
  departmentName,
  logoUrl,
  currentScopePath,
  currentCustomerName,
  adminMemberships,
  selectedAdminOrganizationId,
}: Props) {
  if (!clerkEnabled) {
    return <StaticHeaderBrand cityName={cityName} departmentName={departmentName} logoUrl={logoUrl} />
  }

  return (
    <ClerkHeaderBrand
      cityName={cityName}
      departmentName={departmentName}
      logoUrl={logoUrl}
      currentScopePath={currentScopePath}
      currentCustomerName={currentCustomerName}
      adminMemberships={adminMemberships}
      selectedAdminOrganizationId={selectedAdminOrganizationId}
    />
  )
}

function StaticHeaderBrand({
  cityName,
  departmentName,
  logoUrl,
}: {
  cityName: string
  departmentName: string
  logoUrl: string | null
}) {
  const showSubtitle = Boolean(departmentName.trim())

  return (
    <div className="brand brand-header">
      <div className={`brand-mark brand-mark-public${logoUrl ? ' brand-mark-has-image' : ''}`}>
        <BuildingLogo logoUrl={logoUrl} alt={`${cityName} logo`} />
      </div>
      <div className="brand-copy">
        <div className="brand-title">{cityName}</div>
        {showSubtitle ? <div className="brand-subtitle">{departmentName}</div> : null}
      </div>
    </div>
  )
}

function ClerkHeaderBrand({
  cityName,
  departmentName,
  logoUrl,
  currentScopePath,
  currentCustomerName,
  adminMemberships,
  selectedAdminOrganizationId,
}: Omit<Props, 'clerkEnabled'>) {
  const { setActive } = useClerk()
  const pathname = usePathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isOpen, setIsOpen] = useState(false)
  const [pendingOrganizationId, setPendingOrganizationId] = useState<string | null>(null)

  const currentScopedPathname =
    currentScopePath && pathname.startsWith(currentScopePath)
      ? pathname.slice(currentScopePath.length) || '/'
      : pathname
  const isAdminRoute = currentScopedPathname.startsWith('/admin')
  const isSuperAdminRoute = currentScopedPathname.startsWith('/super-admin')
  const isJurisdictionPickerRoute = pathname.startsWith('/select-jurisdiction')
  const canSwitchOrganizations = isAdminRoute && adminMemberships.length > 1
  const selectedMembership =
    adminMemberships.find((membership) => membership.organizationId === selectedAdminOrganizationId) ||
    null
  const resolvedCustomerName = currentCustomerName || selectedMembership?.organizationName || cityName
  const title = isSuperAdminRoute
    ? 'Super Admin'
    : isJurisdictionPickerRoute
      ? 'Gridics'
    : isAdminRoute
      ? selectedMembership?.organizationName || resolvedCustomerName
      : resolvedCustomerName
  const subtitle = isJurisdictionPickerRoute ? '' : departmentName

  async function switchOrganization(nextOrganizationId: string) {
    if (!nextOrganizationId || nextOrganizationId === selectedAdminOrganizationId) {
      setIsOpen(false)
      return
    }

    const membership = adminMemberships.find((item) => item.organizationId === nextOrganizationId)
    if (!membership) {
      return
    }

    setPendingOrganizationId(nextOrganizationId)

    try {
      await setActive({ organization: nextOrganizationId })
      const params = new URLSearchParams(searchParams.toString())
      params.delete('clientid')
      const nextPathname = replaceScopePathInPathname(
        pathname,
        currentScopePath,
        buildInternalOrgScopePath(membership.organizationId),
      )
      const nextSearch = params.toString()

      startTransition(() => {
        router.replace(nextSearch ? `${nextPathname}?${nextSearch}` : nextPathname)
        router.refresh()
      })
    } finally {
      setIsOpen(false)
      setPendingOrganizationId(null)
    }
  }

  return (
    <div className="brand brand-header">
      <div className={`brand-mark brand-mark-public${logoUrl ? ' brand-mark-has-image' : ''}`}>
        <BuildingLogo logoUrl={logoUrl} alt={`${title} logo`} />
      </div>
      <div className="brand-copy">
        <div className="brand-title-row">
          <div>
            <div className="brand-title">{title}</div>
            {subtitle ? <div className="brand-subtitle">{subtitle}</div> : null}
          </div>
          {canSwitchOrganizations ? (
            <div className="brand-switcher">
              <button
                className="button secondary brand-switch-button"
                type="button"
                onClick={() => {
                  setIsOpen((value) => !value)
                }}
                disabled={pendingOrganizationId !== null}
              >
                Switch jurisdiction
              </button>
              {isOpen ? (
                <div className="brand-switch-menu">
                  {adminMemberships.map((membership) => (
                    <button
                      key={membership.organizationId}
                      className="brand-switch-option"
                      type="button"
                      onClick={() => {
                        void switchOrganization(membership.organizationId)
                      }}
                    >
                      {membership.organizationName}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
