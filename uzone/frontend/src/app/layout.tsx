import './globals.css'
import { Inter } from 'next/font/google'
import type { ReactNode } from 'react'

import { AuthControls, ClerkShell } from '../components/ClerkShell'
import { HeaderBrand } from '../components/HeaderBrand'
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
                  adminMemberships={permissions.adminMemberships}
                  selectedAdminOrganizationId={permissions.selectedAdminMembership?.organizationId || null}
                />
                <div className="topbar-actions">
                  <nav className="nav nav-public">
                    <a href="/" className="nav-current">
                      Zoning Verification Letters
                    </a>
                    <a href="/assistant">Assistant</a>
                    <a href="/request/new">Property Search</a>
                    <a href="/#features-section">Resources</a>
                    <a href="/#cta-section">Contact</a>
                  </nav>
                  <AuthControls
                    clerkEnabled={clerkEnabled}
                    canAccessAdminScreens={permissions.canAccessAdminScreens}
                    isSuperAdmin={permissions.isSuperAdmin}
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
