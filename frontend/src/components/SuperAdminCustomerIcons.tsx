'use client'

type IconName = 'jurisdiction-details' | 'assistant-setup' | 'assistant' | 'admin-users' | 'database' | 'conversations' | 'traces' | 'back'

function IconPath({ name }: { name: IconName }) {
  if (name === 'jurisdiction-details') {
    return (
      <path
        d="M4 20V7.5L12 4l8 3.5V20h-3v-4.5a2.5 2.5 0 0 0-5 0V20H4Zm3-9h2V9H7v2Zm0 4h2v-2H7v2Zm4-4h2V9h-2v2Zm4 0h2V9h-2v2Z"
        fill="currentColor"
      />
    )
  }

  if (name === 'assistant-setup') {
    return (
      <path
        d="M10.9 3.6 9.9 6a6.9 6.9 0 0 0-1.4.8L6 5.9 4 7.9l.9 2.5a6.9 6.9 0 0 0-.4 1.6L2 13v2l2.5 1a6.9 6.9 0 0 0 .4 1.6L4 20.1l2 2 2.5-.9c.4.3.9.6 1.4.8l1 2.4h2.2l1-2.4c.5-.2 1-.5 1.4-.8l2.5.9 2-2-.9-2.5c.2-.5.3-1 .4-1.6l2.5-1v-2l-2.5-1a6.9 6.9 0 0 0-.4-1.6l.9-2.5-2-2-2.5.9a6.9 6.9 0 0 0-1.4-.8l-1-2.4h-2.2ZM12 16.9A2.9 2.9 0 1 1 12 11a2.9 2.9 0 0 1 0 5.8Z"
        fill="currentColor"
      />
    )
  }

  if (name === 'assistant') {
    return (
      <path
        d="M6 5.5A3.5 3.5 0 0 0 2.5 9v5A3.5 3.5 0 0 0 6 17.5h1.7l2.7 2.3c.7.6 1.6.1 1.6-.8v-1.5H18A3.5 3.5 0 0 0 21.5 14V9A3.5 3.5 0 0 0 18 5.5H6Zm2.5 5.3a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm3.5 0a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm3.5 0a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"
        fill="currentColor"
      />
    )
  }

  if (name === 'admin-users') {
    return (
      <path
        d="M8.3 11.3a3.3 3.3 0 1 1 0-6.6 3.3 3.3 0 0 1 0 6.6Zm7.4-1.1a2.7 2.7 0 1 1 0-5.4 2.7 2.7 0 0 1 0 5.4ZM3 18.7c0-2.4 2.8-4.3 5.3-4.3s5.3 1.9 5.3 4.3V20H3v-1.3Zm12.7 1.3v-1c0-1.1-.3-2.1-.9-3 .4-.1.8-.1 1.2-.1 2 0 4 1.4 4 3.2V20h-4.3Z"
        fill="currentColor"
      />
    )
  }

  if (name === 'database') {
    return (
      <path
        d="M12 3c-4.4 0-8 1.7-8 3.8v10.4C4 19.3 7.6 21 12 21s8-1.7 8-3.8V6.8C20 4.7 16.4 3 12 3Zm0 2c3.5 0 6 .9 6 1.8s-2.5 1.8-6 1.8-6-.9-6-1.8S8.5 5 12 5Zm0 14c-3.5 0-6-.9-6-1.8v-2c1.4 1 3.7 1.5 6 1.5s4.6-.5 6-1.5v2c0 .9-2.5 1.8-6 1.8Zm0-5.8c-3.5 0-6-.9-6-1.8v-2c1.4 1 3.7 1.5 6 1.5s4.6-.5 6-1.5v2c0 .9-2.5 1.8-6 1.8Z"
        fill="currentColor"
      />
    )
  }

  if (name === 'conversations') {
    return (
      <path
        d="M6.5 5.5A3.5 3.5 0 0 0 3 9v5a3.5 3.5 0 0 0 3.5 3.5H8l3 2.5c.7.6 1.8.1 1.8-.9v-1.6H17A3.5 3.5 0 0 0 20.5 14V9A3.5 3.5 0 0 0 17 5.5H6.5Zm2 4.7a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Zm3.5 0a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Zm3.5 0a1.1 1.1 0 1 1 0-2.2 1.1 1.1 0 0 1 0 2.2Z"
        fill="currentColor"
      />
    )
  }

  if (name === 'traces') {
    return (
      <path
        d="M4 17.5h16M6.5 14.5l2.6-3.2 3 2.4 4.3-6.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    )
  }

  return (
    <path
      d="M10 6 4 12l6 6 1.4-1.4L7.8 13H20v-2H7.8l3.6-3.6L10 6Z"
      fill="currentColor"
    />
  )
}

export function SuperAdminCustomerIcon({
  name,
  className = '',
}: {
  name: IconName
  className?: string
}) {
  return (
    <span className={`super-admin-icon ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 24 24" focusable="false">
        <IconPath name={name} />
      </svg>
    </span>
  )
}

export function SuperAdminCustomerHeader({
  icon,
  eyebrow,
  title,
  description,
}: {
  icon: IconName
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div className="page-intro">
      <div className="section-icon-row">
        <SuperAdminCustomerIcon name={icon} className="is-header" />
        <div className="eyebrow" style={{ marginBottom: 0 }}>
          {eyebrow}
        </div>
      </div>
      <h1 className="section-title" style={{ marginBottom: 8 }}>
        {title}
      </h1>
      <p className="page-intro-copy">{description}</p>
    </div>
  )
}
