import './globals.css'
import { Inter } from 'next/font/google'
import type { ReactNode } from 'react'

import { AuthControls, ClerkShell } from '../components/ClerkShell'
import { HeaderBrand } from '../components/HeaderBrand'
import { getCurrentOrgId } from '../lib/org-context'
import { appendOrgIdToHref } from '../lib/org-url'
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
  const tenant = await getTenantConfig()
  const permissions = await getPermissionContext(clerkEnabled)
  const orgId = await getCurrentOrgId()

  return (
    <html lang="en" className={inter.variable}>
      <body>
        <ClerkShell clerkEnabled={clerkEnabled}>
          <main>
            <div className="shell shell-wide">
              <header className="topbar topbar-public">
                <HeaderBrand
                  clerkEnabled={clerkEnabled}
                  cityName={tenant.city_name}
                  departmentName={tenant.department_name}
                  currentCustomerName={permissions.currentClientMembership?.organizationName || null}
                  adminMemberships={permissions.adminMemberships}
                  selectedAdminOrganizationId={permissions.selectedAdminMembership?.organizationId || null}
                />
                <div className="topbar-actions">
                  <nav className="nav nav-public">
                    <a href={appendOrgIdToHref('/', orgId)} className="nav-current">
                      Zoning Verification Letters
                    </a>
                    <a href={appendOrgIdToHref('/assistant', orgId)}>Assistant</a>
                    <a href={appendOrgIdToHref('/request/new', orgId)}>Property Search</a>
                    <a href={appendOrgIdToHref('/#features-section', orgId)}>Resources</a>
                    <a href={appendOrgIdToHref('/#cta-section', orgId)}>Contact</a>
                  </nav>
                  <AuthControls
                    clerkEnabled={clerkEnabled}
                    canAccessAdminScreens={permissions.canAccessAdminScreens}
                    isSuperAdmin={permissions.isSuperAdmin}
                    currentOrgId={orgId}
                  />
                </div>
              </header>
              {children}
            </div>
          </main>
        </ClerkShell>
      </body>
    </html>
  )
}
