'use client'

import { ClerkProvider, SignedIn, SignedOut, UserButton } from '@clerk/nextjs'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { appendScopePathToHref } from '../lib/org-url'

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
  compact?: boolean
}

type AppTheme = 'light' | 'dark'

type AssistantToolbarState = {
  title: string
  subtitle: string | null
  canCopy: boolean
  canNewChat: boolean
}

const THEME_STORAGE_KEY = 'uzone-theme'

function applyTheme(theme: AppTheme) {
  if (typeof document === 'undefined') {
    return
  }
  document.documentElement.dataset.theme = theme
}

function ThemeToggleIcon({ theme }: { theme: AppTheme }) {
  if (theme === 'light') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 4.5a1 1 0 0 1 1 1v1.25a1 1 0 1 1-2 0V5.5a1 1 0 0 1 1-1Zm0 11.75a4.25 4.25 0 1 0 0-8.5 4.25 4.25 0 0 0 0 8.5Zm7.5-5.25a1 1 0 0 1-1 1h-1.25a1 1 0 1 1 0-2h1.25a1 1 0 0 1 1 1ZM7 12a1 1 0 0 1-1 1H4.75a1 1 0 1 1 0-2H6a1 1 0 0 1 1 1Zm9.364-5.864a1 1 0 0 1 1.414 0l.884.884a1 1 0 1 1-1.414 1.414l-.884-.884a1 1 0 0 1 0-1.414Zm-10.142 10.142a1 1 0 0 1 1.414 0l.884.884a1 1 0 0 1-1.414 1.414l-.884-.884a1 1 0 0 1 0-1.414Zm12.44 2.298a1 1 0 0 1-1.414 0l-.884-.884a1 1 0 1 1 1.414-1.414l.884.884a1 1 0 0 1 0 1.414ZM8.636 7.02a1 1 0 0 1-1.414 0l-.884-.884A1 1 0 0 1 7.752 4.72l.884.884a1 1 0 0 1 0 1.414ZM12 17.25a1 1 0 0 1 1 1v1.25a1 1 0 1 1-2 0V18.25a1 1 0 0 1 1-1Z"
          fill="currentColor"
        />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M14.72 3.38a1 1 0 0 1 .84 1.5 7.5 7.5 0 1 0 3.56 10.54 1 1 0 0 1 1.84.76A9.5 9.5 0 1 1 13.94 2.9a1 1 0 0 1 .78.48Z"
        fill="currentColor"
      />
    </svg>
  )
}

function ThemeToggleButton() {
  const [theme, setTheme] = useState<AppTheme>('light')

  useEffect(() => {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    const resolvedTheme: AppTheme = storedTheme === 'dark' ? 'dark' : 'light'
    setTheme(resolvedTheme)
    applyTheme(resolvedTheme)
  }, [])

  const handleToggle = () => {
    const nextTheme: AppTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(nextTheme)
    applyTheme(nextTheme)
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme)
  }

  return (
    <button
      className="app-theme-toggle"
      type="button"
      onClick={handleToggle}
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
      title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
    >
      <ThemeToggleIcon theme={theme} />
    </button>
  )
}

function AuthControls({
  clerkEnabled,
  canAccessAdminScreens,
  isSuperAdmin,
  currentOrgId,
  currentScopePath,
  compact = false,
}: AuthControlsProps) {
  const adminHref = currentScopePath
    ? appendScopePathToHref('/admin', currentScopePath)
    : currentOrgId
      ? `/_internal/${encodeURIComponent(currentOrgId)}/admin`
      : '/admin'
  const [assistantToolbarState, setAssistantToolbarState] = useState<AssistantToolbarState | null>(null)

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

  if (!clerkEnabled) {
    return (
      <div className={`auth-controls-group${compact ? ' auth-controls-group-compact' : ''}`}>
        <ThemeToggleButton />
        {assistantToolbarState ? (
          <div className="assistant-header-controls">
            <button
              className="assistant-chat-toolbar-icon-button assistant-header-control-button"
              type="button"
              aria-label="Copy chat"
              title={assistantToolbarState.canCopy ? 'Copy chat' : 'No conversation to copy yet'}
              disabled={!assistantToolbarState.canCopy}
              onClick={() => {
                window.dispatchEvent(new CustomEvent('uzone-assistant-toolbar-action', { detail: { action: 'copy' } }))
              }}
            >
              <span aria-hidden="true">⎘</span>
            </button>
            <button
              className="assistant-chat-toolbar-button assistant-header-control-button"
              type="button"
              onClick={() => {
                window.dispatchEvent(
                  new CustomEvent('uzone-assistant-toolbar-action', { detail: { action: 'new-chat' } }),
                )
              }}
              disabled={!assistantToolbarState.canNewChat}
            >
              New Chat
            </button>
          </div>
        ) : null}
        <a className="button button-signin" href="/account/requests">
          <span className="button-signin-icon">•</span>
          Sign In
        </a>
      </div>
    )
  }

  return (
    <div className={`auth-controls-group${compact ? ' auth-controls-group-compact' : ''}`}>
      <ThemeToggleButton />
      {assistantToolbarState ? (
        <div className="assistant-header-controls">
          <button
            className="assistant-chat-toolbar-icon-button assistant-header-control-button"
            type="button"
            aria-label="Copy chat"
            title={assistantToolbarState.canCopy ? 'Copy chat' : 'No conversation to copy yet'}
            disabled={!assistantToolbarState.canCopy}
            onClick={() => {
              window.dispatchEvent(new CustomEvent('uzone-assistant-toolbar-action', { detail: { action: 'copy' } }))
            }}
          >
            <span aria-hidden="true">⎘</span>
          </button>
          <button
            className="assistant-chat-toolbar-button assistant-header-control-button"
            type="button"
            onClick={() => {
              window.dispatchEvent(
                new CustomEvent('uzone-assistant-toolbar-action', { detail: { action: 'new-chat' } }),
              )
            }}
            disabled={!assistantToolbarState.canNewChat}
          >
            New Chat
          </button>
        </div>
      ) : null}
      <SignedOut>
        {compact ? (
          <Link className="button secondary button-signin button-signin-compact" href="/sign-in">
            Sign In
          </Link>
        ) : (
          <Link className="button button-signin" href="/sign-in">
            <span className="button-signin-icon">•</span>
            Sign In
          </Link>
        )}
      </SignedOut>
      <SignedIn>
        <UserButton afterSignOutUrl="/">
          {compact ? null : (
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
          )}
        </UserButton>
      </SignedIn>
    </div>
  )
}

export function ClerkShell({ children, clerkEnabled }: Props) {
  if (!clerkEnabled) {
    return <>{children}</>
  }

  return <ClerkProvider>{children}</ClerkProvider>
}

export { AuthControls }
