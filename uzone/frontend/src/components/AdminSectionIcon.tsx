import type { ReactNode } from 'react'

type AdminSectionIconName =
  | 'settings'
  | 'jurisdictions'
  | 'form-settings'
  | 'email-settings'
  | 'fee-structure'
  | 'letter-templates'
  | 'home-page'
  | 'permissions'

function IconShell({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span className={className || 'admin-icon'} aria-hidden="true">
      <svg viewBox="0 0 24 24" focusable="false">
        {children}
      </svg>
    </span>
  )
}

export function AdminSectionIcon({
  name,
  className,
}: {
  name: AdminSectionIconName
  className?: string
}) {
  if (name === 'form-settings') {
    return (
      <IconShell className={className}>
        <path
          d="M8 4.5h6l3.5 3.5V19a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 6.5 19V6A1.5 1.5 0 0 1 8 4.5Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M14 4.5V8h3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <path d="M9 11.5h6M9 15h6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </IconShell>
    )
  }

  if (name === 'email-settings') {
    return (
      <IconShell className={className}>
        <path
          d="M5.5 7.5h13a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="m5 8 7 5 7-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </IconShell>
    )
  }

  if (name === 'fee-structure') {
    return (
      <IconShell className={className}>
        <path d="M14.5 6.5c-.7-.7-1.7-1-2.7-1-1.9 0-3.3 1.1-3.3 2.6 0 3.8 6.8 1.7 6.8 5.5 0 1.6-1.5 2.9-3.6 2.9-1.2 0-2.4-.4-3.2-1.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M12 4.5v15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </IconShell>
    )
  }

  if (name === 'letter-templates') {
    return (
      <IconShell className={className}>
        <path
          d="M8 4.5h6l3.5 3.5V19a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 6.5 19V6A1.5 1.5 0 0 1 8 4.5Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <path d="M14 4.5V8h3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <circle cx="10" cy="15.2" r="1.6" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M11.2 16.4 13 18.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </IconShell>
    )
  }

  if (name === 'home-page') {
    return (
      <IconShell className={className}>
        <circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M12 10v5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="12" cy="7.5" r="1" fill="currentColor" />
      </IconShell>
    )
  }

  if (name === 'permissions') {
    return (
      <IconShell className={className}>
        <circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M4.8 17c.7-2 2.4-3.2 4.2-3.2S12.5 15 13.2 17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="16.5" cy="11" r="2" fill="none" stroke="currentColor" strokeWidth="1.8" />
        <path d="M14.5 17c.4-1.4 1.5-2.4 3-2.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </IconShell>
    )
  }

  if (name === 'jurisdictions') {
    return (
      <IconShell className={className}>
        <path d="M12 20s5.5-4.7 5.5-9.2A5.5 5.5 0 1 0 6.5 10.8C6.5 15.3 12 20 12 20Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
        <circle cx="12" cy="10.5" r="1.8" fill="none" stroke="currentColor" strokeWidth="1.8" />
      </IconShell>
    )
  }

  return (
    <IconShell className={className}>
      <circle cx="12" cy="12" r="2.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 4.8v2.1M12 17.1v2.1M19.2 12h-2.1M6.9 12H4.8M17.1 6.9l-1.5 1.5M8.4 15.6l-1.5 1.5M17.1 17.1l-1.5-1.5M8.4 8.4 6.9 6.9" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </IconShell>
  )
}

export type { AdminSectionIconName }
