'use client'

import { useAuth } from '@clerk/nextjs'
import { useEffect, useState } from 'react'

import { fetchJsonWithToken } from '../lib/api'

type MeResponse = {
  auth_provider: string
  user_id: string | null
  session_id: string | null
  email: string | null
}

export default function BackendAuthStatusClerk() {
  const { getToken, isSignedIn } = useAuth()
  const [status, setStatus] = useState<string>('Checking backend auth')

  useEffect(() => {
    let active = true

    async function run() {
      try {
        const payload = await fetchJsonWithToken<MeResponse>(
          '/api/auth/me',
          async () => (isSignedIn ? getToken() : null),
        )
        if (!active) {
          return
        }
        if (!payload) {
          setStatus('Backend auth not verified')
          return
        }
        setStatus(`Backend auth provider: ${payload.auth_provider}`)
      } catch {
        if (active) {
          setStatus('Backend auth unavailable')
        }
      }
    }

    run()
    return () => {
      active = false
    }
  }, [getToken, isSignedIn])

  return <div style={{ fontWeight: 700 }}>{status}</div>
}

