'use client'

import { useClerk } from '@clerk/nextjs'
import { startTransition, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import type { ClientMembership } from '../lib/permissions'
import type { UzoneProduct } from '../lib/product-routing'
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
  currentProduct?: UzoneProduct
  currentOrgId?: string | null
  currentCustomerName: string | null
  adminMemberships: ClientMembership[]
  selectedAdminOrganizationId: string | null
}

type AssistantToolbarState = {
  title: string
  subtitle: string | null
  canCopy: boolean
  canNewChat: boolean
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
        currentOrgId={currentOrgId}
        currentProduct={currentProduct}
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
  currentOrgId,
  currentProduct,
}: {
  cityName: string
  departmentName: string
  title?: string | null
  superAdminCustomerName?: string | null
  superAdminCustomerId?: string | null
  logoUrl: string | null
  brandVariant: 'tenant' | 'gridics'
  currentProduct?: UzoneProduct
  currentOrgId?: string | null
}) {
  const showSubtitle = Boolean(departmentName.trim())
  const isGridicsBrand = brandVariant === 'gridics'
  const useGridicsFallback = isGridicsBrand || Boolean(currentOrgId)
  const resolvedTitle = currentProduct === 'assistant' ? cityName : title?.trim() || (isGridicsBrand ? 'Gridics' : cityName)
  const subtitle = currentProduct === 'assistant' || isGridicsBrand ? '' : departmentName

  return (
    <div className="brand brand-header">
      <div className={`brand-mark brand-mark-public${logoUrl ? ' brand-mark-has-image' : ''}`}>
        {logoUrl ? (
          <BuildingLogo logoUrl={logoUrl} alt={`${cityName} logo`} />
        ) : useGridicsFallback ? (
          <GridicsLogo />
        ) : (
          <BuildingLogo logoUrl={logoUrl} alt={`${cityName} logo`} />
        )}
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
  const pathname = useHydratedPathname() || '/'
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isOpen, setIsOpen] = useState(false)
  const [pendingOrganizationId, setPendingOrganizationId] = useState<string | null>(null)
  const resolvedAdminMemberships = Array.isArray(adminMemberships) ? adminMemberships : []
  const useGridicsFallback = brandVariant === 'gridics' || Boolean(currentOrgId)
  const [assistantToolbarState, setAssistantToolbarState] = useState<AssistantToolbarState | null>(null)

  const currentScopedPathname =
    currentScopePath && pathname && pathname.startsWith(currentScopePath)
      ? pathname.slice(currentScopePath.length) || '/'
      : pathname || '/'
  const isAdminRoute = currentScopedPathname.startsWith('/admin')
  const isSuperAdminRoute = currentScopedPathname.startsWith('/super-admin')
  const isJurisdictionPickerRoute = isAgenticPickerRoute(pathname)
  const canSwitchOrganizations = isAdminRoute && resolvedAdminMemberships.length > 1
  const selectedMembership =
    resolvedAdminMemberships.find((membership) => membership.organizationId === selectedAdminOrganizationId) ||
    null
  const resolvedCustomerName = currentCustomerName || selectedMembership?.organizationName || cityName
  const resolvedTitle = isSuperAdminRoute
    ? 'SUPER ADMIN'
    : isJurisdictionPickerRoute
      ? title?.trim() || 'Gridics AI Assistant'
      : isAdminRoute
        ? selectedMembership?.organizationName || resolvedCustomerName
        : resolvedCustomerName
  const isAssistantRoute = currentProduct === 'assistant'
  const subtitle = isSuperAdminRoute || isJurisdictionPickerRoute || isAssistantRoute ? '' : departmentName
  const superAdminSubtitle = isSuperAdminRoute && (superAdminCustomerId || currentOrgId || superAdminCustomerName)
    ? {
        name: superAdminCustomerName || resolvedCustomerName,
        id: superAdminCustomerId || currentOrgId || null,
      }
    : null

  useEffect(() => {
    const handleToolbarState = (event: Event) => {
      const detail = (event as CustomEvent<AssistantToolbarState | null>).detail
      if (!detail || !detail.title?.trim()) {
        setAssistantToolbarState(null)
        return
      }

      setAssistantToolbarState({
        title: detail.title.trim(),
        subtitle: detail.subtitle?.trim() || null,
        canCopy: Boolean(detail.canCopy),
        canNewChat: Boolean(detail.canNewChat),
      })
    }

    const windowWithToolbarState = window as Window & {
      __uzoneAssistantToolbarState?: AssistantToolbarState | null
    }
    const initialState = windowWithToolbarState.__uzoneAssistantToolbarState
    if (initialState?.title?.trim()) {
      setAssistantToolbarState({
        title: initialState.title.trim(),
        subtitle: initialState.subtitle?.trim() || null,
        canCopy: Boolean(initialState.canCopy),
        canNewChat: Boolean(initialState.canNewChat),
      })
    }

    window.addEventListener('uzone-assistant-toolbar-state', handleToolbarState as EventListener)
    return () => {
      window.removeEventListener('uzone-assistant-toolbar-state', handleToolbarState as EventListener)
    }
  }, [])

  async function switchOrganization(nextOrganizationId: string) {
    if (!nextOrganizationId || nextOrganizationId === selectedAdminOrganizationId) {
      setIsOpen(false)
      return
    }

    const membership = resolvedAdminMemberships.find((item) => item.organizationId === nextOrganizationId)
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
        {logoUrl ? (
          <BuildingLogo logoUrl={logoUrl} alt={`${resolvedTitle} logo`} />
        ) : useGridicsFallback ? (
          <GridicsLogo />
        ) : (
          <BuildingLogo logoUrl={logoUrl} alt={`${resolvedTitle} logo`} />
        )}
      </div>
      <div className="brand-copy">
        <div className="brand-title-row">
          <div>
            <div className="brand-title">{resolvedTitle}</div>
            {isAssistantRoute && assistantToolbarState ? (
              <div className="brand-assistant-copy">
                <div className="assistant-chat-toolbar-title brand-assistant-toolbar-title">
                  {assistantToolbarState.title}
                </div>
              </div>
            ) : null}
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
                  {resolvedAdminMemberships.map((membership) => (
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
  const [isDarkTheme, setIsDarkTheme] = useState(false)

  useEffect(() => {
    const root = document.documentElement
    const resolveTheme = () => setIsDarkTheme(root.dataset.theme === 'dark')

    resolveTheme()

    const observer = new MutationObserver(resolveTheme)
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })

    return () => {
      observer.disconnect()
    }
  }, [])

  const logoSrc = isDarkTheme
    ? '/logos/R%20-%20Gridics%20(White).png'
    : '/logos/R%20-%20Gridics%20(Grey).png'

  return (
    <img
      src={logoSrc}
      alt="Gridics logo"
      className="building-logo building-logo-image"
    />
  )
}
