import './globals.css'
import { Inter } from 'next/font/google'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { AuthControls, ClerkShell } from '../components/ClerkShell'
import { ClientErrorReporter } from '../components/ClientErrorReporter'
import { HeaderBrand } from '../components/HeaderBrand'
import { PublicNav } from '../components/PublicNav'
import { getCurrentHost, getCurrentOrgId, getCurrentPathname, getCurrentProduct, getCurrentScopePath } from '../lib/org-context'
import { getPermissionContext } from '../lib/permissions'
import { getTenantConfig } from '../lib/tenant'
import { resolveAgenticBrowserTitle } from '../lib/public-branding'

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
      publicSiteTitle: tenant.public_site_title,
      cityName: tenant.city_name,
    }),
    description: 'Zoning verification workflow',
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const orgId = await getCurrentOrgId()
  const currentScopePath = await getCurrentScopePath()
  const currentPathname = await getCurrentPathname()
  const currentHost = await getCurrentHost()
  const currentProduct = await getCurrentProduct()
  const isEmbedSurface = currentScopePath?.startsWith('/embed') ?? false
  const isSuperAdminScope = currentScopePath?.startsWith('/super-admin') ?? false
  const tenant = await getTenantConfig()
  const permissions = await getPermissionContext(clerkEnabled)
  const displayCityName = orgId ? tenant.city_name : 'UZone'
  const displayDepartmentName = orgId ? tenant.department_name : 'Choose a Jurisdiction'
  const isJurisdictionPickerRoute =
    currentPathname === '/select-jurisdiction' ||
    (currentPathname === '/' && currentProduct === 'assistant')
  const brandTitle = resolveAgenticBrowserTitle({
    pathname: currentPathname,
    currentProduct,
    orgId,
    publicSiteTitle: tenant.public_site_title,
    cityName: tenant.city_name,
  })
  const logoUrl = !isSuperAdminScope && !isJurisdictionPickerRoute && orgId ? tenant.logo_path || null : null
  const brandVariant = isSuperAdminScope || isJurisdictionPickerRoute ? 'gridics' : 'tenant'

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
                <header className="topbar topbar-public">
                  <HeaderBrand
                    clerkEnabled={clerkEnabled}
                    cityName={displayCityName}
                    departmentName={displayDepartmentName}
                    title={brandTitle}
                    logoUrl={logoUrl}
                    brandVariant={brandVariant}
                    currentScopePath={currentScopePath}
                    currentProduct={currentProduct}
                    currentOrgId={orgId}
                    currentCustomerName={permissions.currentClientMembership?.organizationName || null}
                    adminMemberships={permissions.adminMemberships}
                    selectedAdminOrganizationId={permissions.selectedAdminMembership?.organizationId || null}
                  />
                  <div className="topbar-actions">
                    <PublicNav
                      orgId={orgId}
                      scopePath={currentScopePath}
                      currentHost={currentHost}
                      currentProduct={currentProduct}
                    />
                    <AuthControls
                      clerkEnabled={clerkEnabled}
                      canAccessAdminScreens={permissions.canAccessAdminScreens}
                      isSuperAdmin={permissions.isSuperAdmin}
                      currentOrgId={orgId}
                      currentScopePath={currentScopePath}
                    />
                  </div>
                </header>
                {children}
              </div>
            </main>
          )}
        </ClerkShell>
      </body>
    </html>
  )
}
