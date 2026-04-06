import './globals.css'
import { Inter } from 'next/font/google'
import type { ReactNode } from 'react'

import { AuthControls, ClerkShell } from '../components/ClerkShell'
import { HeaderBrand } from '../components/HeaderBrand'
import { PublicNav } from '../components/PublicNav'
import { getCurrentOrgId, getCurrentScopePath } from '../lib/org-context'
import { getPermissionContext } from '../lib/permissions'
import { getTenantConfig } from '../lib/tenant'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

export const metadata = {
  title: 'UZone',
  description: 'Zoning verification workflow',
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const orgId = await getCurrentOrgId()
  const currentScopePath = await getCurrentScopePath()
  const isEmbedSurface = currentScopePath?.startsWith('/embed') ?? false
  const isSuperAdminScope = currentScopePath?.startsWith('/super-admin') ?? false
  const tenant = await getTenantConfig()
  const permissions = await getPermissionContext(clerkEnabled)
  const displayCityName = orgId ? tenant.city_name : 'UZone'
  const displayDepartmentName = orgId ? tenant.department_name : 'Choose a Jurisdiction'
  const logoUrl = !isSuperAdminScope && orgId ? tenant.logo_path || null : null

  return (
    <html lang="en" className={inter.variable}>
      <body>
        <ClerkShell clerkEnabled={clerkEnabled}>
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
                    logoUrl={logoUrl}
                    brandVariant={isSuperAdminScope ? 'gridics' : 'tenant'}
                    currentScopePath={currentScopePath}
                    currentCustomerName={permissions.currentClientMembership?.organizationName || null}
                    adminMemberships={permissions.adminMemberships}
                    selectedAdminOrganizationId={permissions.selectedAdminMembership?.organizationId || null}
                  />
                  <div className="topbar-actions">
                    <PublicNav orgId={orgId} scopePath={currentScopePath} />
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
