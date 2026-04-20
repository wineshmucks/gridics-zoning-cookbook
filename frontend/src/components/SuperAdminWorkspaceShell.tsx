import type { ReactNode } from 'react'

import { SuperAdminWorkspaceSidebar } from './SuperAdminWorkspaceSidebar'

export function SuperAdminWorkspaceShell({ children }: { children: ReactNode }) {
  return (
    <div className="super-admin-shell super-admin-workspace-shell">
      <div className="super-admin-layout super-admin-workspace-layout">
        <SuperAdminWorkspaceSidebar />
        <div className="super-admin-content super-admin-workspace-content">{children}</div>
      </div>
    </div>
  )
}
