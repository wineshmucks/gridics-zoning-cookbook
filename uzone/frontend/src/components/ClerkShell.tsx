'use client'

import { ClerkProvider, SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/nextjs'
import type { ReactNode } from 'react'

type Props = {
  children: ReactNode
  clerkEnabled: boolean
}

type AuthControlsProps = {
  clerkEnabled: boolean
  canAccessAdminScreens: boolean
  isSuperAdmin: boolean
  currentOrgId: string | null
  currentScopePath: string | null
}

function AuthControls({
  clerkEnabled,
  canAccessAdminScreens,
  isSuperAdmin,
  currentOrgId,
  currentScopePath,
}: AuthControlsProps) {
  const adminHref = currentScopePath ? `${currentScopePath}/admin` : currentOrgId ? `/${encodeURIComponent(currentOrgId)}/admin` : '/admin'

  if (!clerkEnabled) {
    return (
      <a className="button button-signin" href="/account/requests">
        <span className="button-signin-icon">•</span>
        Sign In
      </a>
    )
  }

  return (
    <>
      <SignedOut>
        <SignInButton mode="modal">
          <button className="button button-signin">
            <span className="button-signin-icon">•</span>
            Sign In
          </button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        <UserButton afterSignOutUrl="/">
          <UserButton.MenuItems>
            {canAccessAdminScreens ? (
              <UserButton.Link
                href={adminHref}
                label="Admin"
                labelIcon={<span aria-hidden="true">A</span>}
              />
            ) : null}
            {isSuperAdmin ? (
              <UserButton.Link
                href="/super-admin"
                label="Super Admin"
                labelIcon={<span aria-hidden="true">S</span>}
              />
            ) : null}
          </UserButton.MenuItems>
        </UserButton>
      </SignedIn>
    </>
  )
}

export function ClerkShell({ children, clerkEnabled }: Props) {
  if (!clerkEnabled) {
    return <>{children}</>
  }

  return <ClerkProvider>{children}</ClerkProvider>
}

export { AuthControls }
