import type { ReactNode } from 'react'

import { AdminSectionIcon } from './AdminSectionIcon'

export function AdminSectionTitle({
  icon,
  title,
  children,
}: {
  icon: Parameters<typeof AdminSectionIcon>[0]['name']
  title: string
  children?: ReactNode
}) {
  return (
    <div className="admin-title-row">
      <AdminSectionIcon name={icon} className="admin-title-icon" />
      <div>
        <h1 className="section-title" style={{ marginBottom: 8 }}>
          {title}
        </h1>
        {children}
      </div>
    </div>
  )
}
