'use client'

import { useClerk } from '@clerk/nextjs'
import { startTransition, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import type { ClientMembership } from '../lib/permissions'
import { buildInternalOrgScopePath, replaceScopePathInPathname } from '../lib/org-url'
import { useHydratedPathname } from '../lib/use-hydrated-pathname'
import { isAgenticPickerRoute } from '../lib/public-branding'
import { BuildingLogo } from './BuildingLogo'

type Props = {
  clerkEnabled: boolean
  cityName: string
  departmentName: string
  title?: string | null
  superAdminCustomerName?: string | null
  superAdminCustomerId?: string | null
  logoUrl: string | null
  brandVariant: 'tenant' | 'gridics'
  currentScopePath: string | null
  currentProduct?: 'assistant' | 'letters'
  currentOrgId?: string | null
  currentCustomerName: string | null
  adminMemberships: ClientMembership[]
  selectedAdminOrganizationId: string | null
}

export function HeaderBrand({
  clerkEnabled,
  cityName,
  departmentName,
  title,
  superAdminCustomerName,
  superAdminCustomerId,
  logoUrl,
  brandVariant,
  currentScopePath,
  currentProduct,
  currentOrgId,
  currentCustomerName,
  adminMemberships,
  selectedAdminOrganizationId,
}: Props) {
  if (!clerkEnabled) {
    return (
      <StaticHeaderBrand
        cityName={cityName}
        departmentName={departmentName}
        title={title}
        superAdminCustomerName={superAdminCustomerName}
        superAdminCustomerId={superAdminCustomerId}
        logoUrl={logoUrl}
        brandVariant={brandVariant}
      />
    )
  }

  return (
    <ClerkHeaderBrand
      cityName={cityName}
      departmentName={departmentName}
      title={title}
      superAdminCustomerName={superAdminCustomerName}
      superAdminCustomerId={superAdminCustomerId}
      logoUrl={logoUrl}
      brandVariant={brandVariant}
      currentScopePath={currentScopePath}
      currentProduct={currentProduct}
      currentOrgId={currentOrgId}
      currentCustomerName={currentCustomerName}
      adminMemberships={adminMemberships}
      selectedAdminOrganizationId={selectedAdminOrganizationId}
    />
  )
}

function StaticHeaderBrand({
  cityName,
  departmentName,
  title,
  superAdminCustomerName,
  superAdminCustomerId,
  logoUrl,
  brandVariant,
}: {
  cityName: string
  departmentName: string
  title?: string | null
  superAdminCustomerName?: string | null
  superAdminCustomerId?: string | null
  logoUrl: string | null
  brandVariant: 'tenant' | 'gridics'
  currentProduct?: 'assistant' | 'letters'
  currentOrgId?: string | null
}) {
  const showSubtitle = Boolean(departmentName.trim())
  const isGridicsBrand = brandVariant === 'gridics'
  const resolvedTitle = title?.trim() || (isGridicsBrand ? 'Gridics' : cityName)
  const subtitle = isGridicsBrand ? '' : departmentName

  return (
    <div className="brand brand-header">
      <div className={`brand-mark brand-mark-public${logoUrl ? ' brand-mark-has-image' : ''}`}>
        {isGridicsBrand ? <GridicsLogo /> : <BuildingLogo logoUrl={logoUrl} alt={`${cityName} logo`} />}
      </div>
      <div className="brand-copy">
        <div className="brand-title">{resolvedTitle}</div>
        {showSubtitle && subtitle ? <div className="brand-subtitle">{subtitle}</div> : null}
      </div>
    </div>
  )
}

function ClerkHeaderBrand({
  cityName,
  departmentName,
  title,
  logoUrl,
  brandVariant,
  currentProduct,
  currentOrgId,
  currentScopePath,
  currentCustomerName,
  superAdminCustomerName,
  superAdminCustomerId,
  adminMemberships,
  selectedAdminOrganizationId,
}: Omit<Props, 'clerkEnabled'>) {
  const { setActive } = useClerk()
  const pathname = useHydratedPathname()
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
  const isJurisdictionPickerRoute = isAgenticPickerRoute({
    pathname,
    currentProduct: currentProduct ?? null,
    orgId: currentOrgId ?? null,
  })
  const canSwitchOrganizations = isAdminRoute && adminMemberships.length > 1
  const selectedMembership =
    adminMemberships.find((membership) => membership.organizationId === selectedAdminOrganizationId) ||
    null
  const resolvedCustomerName = currentCustomerName || selectedMembership?.organizationName || cityName
  const resolvedTitle = isSuperAdminRoute
    ? 'SUPER ADMIN'
    : isJurisdictionPickerRoute
      ? title?.trim() || 'Gridics AI Assistant'
    : isAdminRoute
      ? selectedMembership?.organizationName || resolvedCustomerName
      : title?.trim() || resolvedCustomerName
  const subtitle = isSuperAdminRoute || isJurisdictionPickerRoute ? '' : departmentName
  const superAdminSubtitle = isSuperAdminRoute
    ? {
        name: superAdminCustomerName || resolvedCustomerName,
        id: superAdminCustomerId || currentOrgId || null,
      }
    : null

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
        {brandVariant === 'gridics' ? <GridicsLogo /> : <BuildingLogo logoUrl={logoUrl} alt={`${resolvedTitle} logo`} />}
      </div>
      <div className="brand-copy">
        <div className="brand-title-row">
          <div>
            <div className="brand-title">{resolvedTitle}</div>
            {superAdminSubtitle ? (
              <div className="brand-super-admin-meta">
                <div className="brand-subtitle brand-super-admin-name">{superAdminSubtitle.name}</div>
                {superAdminSubtitle.id ? (
                  <div className="brand-super-admin-orgid">{superAdminSubtitle.id}</div>
                ) : null}
              </div>
            ) : subtitle ? (
              <div className="brand-subtitle">{subtitle}</div>
            ) : null}
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

function GridicsLogo() {
  return (
    <svg aria-hidden="true" focusable="false" viewBox="0 0 64 64" className="building-logo">
      <rect width="64" height="64" rx="16" fill="#377c36" />
      <path
        fill="#ffffff"
        d="M16 10.667C12.318 10.667 9.333 13.651 9.333 17.333v29.334c0 3.682 2.985 6.666 6.667 6.666h13.333v-11.11c0-3.682 2.985-6.666 6.667-6.666s6.667 2.984 6.667 6.666v11.11H48c3.682 0 6.667-2.984 6.667-6.666V17.333c0-3.682-2.985-6.666-6.667-6.666H16Zm2.222 31.111c0-1.222 1-2.223 2.222-2.223h4.445c1.222 0 2.222 1.001 2.222 2.223v4.444c0 1.223-1 2.222-2.222 2.222h-4.445c-1.222 0-2.222-.999-2.222-2.222v-4.444Zm15.556-2.223h4.444c1.223 0 2.223 1.001 2.223 2.223v4.444c0 1.223-1 2.222-2.223 2.222h-4.444c-1.223 0-2.223-.999-2.223-2.222v-4.444c0-1.222 1-2.223 2.223-2.223Zm13.333 2.223c0-1.222 1-2.223 2.222-2.223h4.445c1.222 0 2.222 1.001 2.222 2.223v4.444c0 1.223-1 2.222-2.222 2.222h-4.445c-1.222 0-2.222-.999-2.222-2.222v-4.444ZM20.444 23.999h4.445c1.222 0 2.222 1 2.222 2.223v4.444c0 1.222-1 2.222-2.222 2.222h-4.445c-1.222 0-2.222-1-2.222-2.222v-4.444c0-1.223 1-2.223 2.222-2.223Zm13.334 2.223c0-1.223 1-2.223 2.222-2.223h4.444c1.223 0 2.223 1 2.223 2.223v4.444c0 1.222-1 2.222-2.223 2.222H36c-1.222 0-2.222-1-2.222-2.222v-4.444Zm13.333-2.223h4.445c1.222 0 2.222 1 2.222 2.223v4.444c0 1.222-1 2.222-2.222 2.222h-4.445c-1.222 0-2.222-1-2.222-2.222v-4.444c0-1.223 1-2.223 2.222-2.223Z"
      />
    </svg>
  )
}
