'use client'

import dynamic from 'next/dynamic'

const BackendAuthStatusClerk = dynamic(() => import('./BackendAuthStatusClerk'), {
  ssr: false,
})

function LocalBackendAuthStatus() {
  return <div style={{ fontWeight: 700 }}>Backend auth provider: local</div>
}

export function BackendAuthStatus({
  clerkEnabled,
}: {
  apiBase: string
  clerkEnabled: boolean
}) {
  return clerkEnabled ? <BackendAuthStatusClerk /> : <LocalBackendAuthStatus />
}

