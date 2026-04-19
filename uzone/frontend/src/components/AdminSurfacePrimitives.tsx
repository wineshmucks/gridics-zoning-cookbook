'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'

import { SuperAdminCustomerIcon } from './SuperAdminCustomerIcons'

type SidebarIconName = Parameters<typeof SuperAdminCustomerIcon>[0]['name']

export function CompactSummaryHeader({
  title,
  status,
  meta,
  icon,
}: {
  title: string
  status?: ReactNode
  meta?: ReactNode
  icon?: SidebarIconName
}) {
  return (
    <div className="compact-summary-header">
      <div className="compact-summary-main">
        <div className="compact-summary-title-row">
          {icon ? <SuperAdminCustomerIcon name={icon} className="is-header" /> : null}
          <h1 className="compact-summary-title">{title}</h1>
        </div>
      </div>
      {(status || meta) && (
        <div className="compact-summary-side">
          {status ? <div className="compact-summary-status">{status}</div> : null}
          {meta ? <div className="compact-summary-meta-copy">{meta}</div> : null}
        </div>
      )}
    </div>
  )
}

export function SectionHeader({
  title,
  actions,
  icon,
}: {
  title: string
  actions?: ReactNode
  icon?: SidebarIconName
}) {
  return (
    <div className="admin-section-header">
      <div className="admin-section-header-copy">
        {icon ? <SuperAdminCustomerIcon name={icon} className="is-header" /> : null}
        <h2 className="admin-section-heading">{title}</h2>
      </div>
      {actions ? <div className="admin-section-actions">{actions}</div> : null}
    </div>
  )
}

export function FormSection({
  title,
  actions,
  children,
  icon,
  className = '',
  hideHeader = false,
}: {
  title: string
  actions?: ReactNode
  children: ReactNode
  icon?: SidebarIconName
  className?: string
  hideHeader?: boolean
}) {
  return (
    <section
      className={`admin-form-section${hideHeader ? ' is-headerless' : ''}${className ? ` ${className}` : ''}`.trim()}
    >
      {hideHeader ? null : <SectionHeader title={title} actions={actions} icon={icon} />}
      <div className="admin-form-section-body">{children}</div>
    </section>
  )
}

export function AdminSidebarGroup({
  label,
  defaultOpen,
  children,
  icon,
}: {
  label: string
  defaultOpen?: boolean
  children: ReactNode
  icon?: SidebarIconName
}) {
  return (
    <details className="admin-sidebar-group" open={defaultOpen}>
      <summary className="admin-sidebar-group-summary">
        <span className="admin-sidebar-group-label">
          {icon ? <SuperAdminCustomerIcon name={icon} className="is-sidebar" /> : null}
          <span>{label}</span>
        </span>
        <span className="admin-sidebar-group-chevron" aria-hidden="true">
          ▾
        </span>
      </summary>
      <div className="admin-sidebar-group-body">{children}</div>
    </details>
  )
}

export function AdminSidebarItem({
  href,
  label,
  active,
  indent = false,
  icon,
  target,
  rel,
}: {
  href: string
  label: string
  active?: boolean
  indent?: boolean
  icon?: SidebarIconName
  target?: string
  rel?: string
}) {
  return (
    <Link
      href={href}
      className={`admin-sidebar-item${active ? ' is-active' : ''}${indent ? ' is-child' : ''}`}
      target={target}
      rel={rel}
    >
      {icon ? <SuperAdminCustomerIcon name={icon} className="is-sidebar" /> : null}
      <span className="admin-sidebar-item-label">{label}</span>
    </Link>
  )
}
