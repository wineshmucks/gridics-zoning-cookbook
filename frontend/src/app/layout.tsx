import './globals.css'
import { Inter } from 'next/font/google'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { AuthControls, ClerkShell } from '../components/ClerkShell'
import { ClientErrorReporter } from '../components/ClientErrorReporter'
import { HeaderBrand } from '../components/HeaderBrand'
import { PublicNav } from '../components/PublicNav'
import { fetchCustomerRecord } from './admin/actions'
import { getCurrentHost, getCurrentOrgId, getCurrentPathname, getCurrentProduct, getCurrentScopePath } from '../lib/org-context'
import { logClerkConfigDiagnostics } from '../lib/clerk-config'
import { getPermissionContext } from '../lib/permissions'
import { getTenantConfig } from '../lib/tenant'
import { resolveAgenticBrowserTitle } from '../lib/public-branding'
import { logJurisdictionBrandingResolution } from '../lib/branding-diagnostics'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

export async function generateMetadata(): Promise<Metadata> {
  const currentPathname = await getCurrentPathname()
  const currentProduct = await getCurrentProduct()
  const orgId = await getCurrentOrgId()
  const tenant = await getTenantConfig()

  return {
    title: resolveAgenticBrowserTitle({
      pathname: currentPathname,
      currentProduct,
      orgId,
    }),
    description: 'Zoning verification workflow',
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const appVersion = process.env.NEXT_PUBLIC_APP_VERSION?.trim() || 'dev'
  if (clerkEnabled) {
    logClerkConfigDiagnostics()
  }
  const orgId = await getCurrentOrgId()
  const currentScopePath = await getCurrentScopePath()
  const currentPathname = await getCurrentPathname()
  const currentHost = await getCurrentHost()
  const currentProduct = await getCurrentProduct()
  const isEmbedSurface = currentScopePath?.startsWith('/embed') ?? false
  const isSuperAdminScope = currentPathname?.startsWith('/super-admin') ?? false
  const superAdminPathSegments = currentPathname?.split('/').filter(Boolean) || []
  const superAdminReservedSegments = new Set(['assistant', 'assistant-setup', 'database', 'gridics-debug', 'new', 'customers'])
  const superAdminPathCustomerId =
    isSuperAdminScope && superAdminPathSegments.length >= 2 && !superAdminReservedSegments.has(superAdminPathSegments[1])
      ? superAdminPathSegments[1]
      : currentPathname?.match(/^\/super-admin\/customers\/([^/]+)/)?.[1] || null
  const superAdminCustomerId = superAdminPathCustomerId
  const superAdminCustomerRecord =
    isSuperAdminScope && superAdminCustomerId ? await fetchCustomerRecord(superAdminCustomerId) : null
  const tenant = await getTenantConfig()
  const permissions = await getPermissionContext(clerkEnabled)
  const effectiveBrandOrgId = isSuperAdminScope ? superAdminCustomerId : orgId
  const displayCityName = isSuperAdminScope
    ? superAdminCustomerRecord?.city_name || 'Gridics'
    : orgId
      ? tenant?.city_name || 'UZone'
      : 'UZone'
  const displayDepartmentName =
    isSuperAdminScope ? '' : orgId ? tenant?.department_name || 'Choose a Jurisdiction' : 'Choose a Jurisdiction'
  const isJurisdictionPickerRoute =
    currentPathname === '/select-jurisdiction' ||
    (currentPathname === '/' && currentProduct === 'assistant')
  const brandTitle = resolveAgenticBrowserTitle({
    pathname: currentPathname,
    currentProduct,
    orgId,
  })
  const superAdminCustomerLogoUrl =
    superAdminCustomerRecord?.logo_path ||
    (superAdminCustomerRecord?.settings_json &&
    typeof superAdminCustomerRecord.settings_json.header_logo_path === 'string'
      ? superAdminCustomerRecord.settings_json.header_logo_path
      : null)
  const logoUrl = isJurisdictionPickerRoute
    ? null
    : isSuperAdminScope
      ? superAdminCustomerLogoUrl
      : orgId
        ? tenant?.logo_path || null
        : null
  const brandVariant = isSuperAdminScope || isJurisdictionPickerRoute ? 'gridics' : 'tenant'

  logJurisdictionBrandingResolution({
    pathname: currentPathname,
    scopePath: currentScopePath,
    orgId: effectiveBrandOrgId,
    cityName: tenant?.city_name || null,
    logoUrl,
    logoSource: isSuperAdminScope ? superAdminCustomerRecord?.logo_source || null : tenant?.logo_source || null,
  })

  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function () {
                try {
                  var theme = localStorage.getItem('uzone-theme');
                  if (theme === 'dark' || theme === 'light') {
                    document.documentElement.dataset.theme = theme;
                  }
                } catch (error) {}
              })();
            `,
          }}
        />
      </head>
      <body>
        <ClerkShell clerkEnabled={clerkEnabled}>
          <ClientErrorReporter />
          {isEmbedSurface ? (
            <main>{children}</main>
          ) : (
            <main>
              <div className="shell shell-wide">
                <header className={`topbar${isSuperAdminScope ? ' topbar-super-admin' : ' topbar-public'}`}>
                  <HeaderBrand
                    clerkEnabled={clerkEnabled}
                    cityName={displayCityName}
                    departmentName={displayDepartmentName}
                    title={brandTitle}
                    logoUrl={logoUrl}
                    brandVariant={brandVariant}
                    currentScopePath={currentScopePath}
                    currentProduct={currentProduct}
                    currentOrgId={effectiveBrandOrgId}
                    currentCustomerName={permissions.currentClientMembership?.organizationName || null}
                    superAdminCustomerName={superAdminCustomerRecord?.city_name || null}
                    superAdminCustomerId={superAdminCustomerRecord?.clerk_organization_id || superAdminCustomerId}
                    adminMemberships={permissions.adminMemberships}
                    selectedAdminOrganizationId={permissions.selectedAdminMembership?.organizationId || null}
                  />
                  <div className={`topbar-actions${isSuperAdminScope ? ' is-super-admin' : ''}`}>
                    {currentProduct === 'letters' && !isSuperAdminScope ? (
                      <PublicNav
                        orgId={orgId}
                        scopePath={currentScopePath}
                        currentHost={currentHost}
                        currentProduct={currentProduct}
                      />
                    ) : null}
                    <AuthControls
                      clerkEnabled={clerkEnabled}
                      canAccessAdminScreens={permissions.canAccessAdminScreens}
                      isSuperAdmin={permissions.isSuperAdmin}
                      currentOrgId={orgId}
                      currentScopePath={currentScopePath}
                      compact={isSuperAdminScope}
                    />
                  </div>
                </header>
                {children}
                <footer className="app-shell-footer">
                  <div className="app-shell-footer-inner">
                    <span className="app-shell-footer-label">Build</span>
                    <span className="app-build-version" title={`Build version: ${appVersion}`}>
                      {appVersion}
                    </span>
                  </div>
                </footer>
              </div>
            </main>
          )}
        </ClerkShell>
      </body>
    </html>
  )
}
