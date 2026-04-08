'use client'

import { useEffect, useState } from 'react'

import { PublicAssistantExperience } from './PublicAssistantExperience'

type EmbedSession = {
  client_id: string
  city_name: string
  department_name: string
  assistant_disclaimer_text: string
  widget_title: string
  launcher_label: string
  accent_color: string
  allowed_origins: string[]
  origin: string | null
  expires_at: string
}

type Props = {
  backendBase: string
}

function readTokenFromLocation(): string {
  if (typeof window === 'undefined') {
    return ''
  }

  const searchParams = new URLSearchParams(window.location.search)
  const queryToken = searchParams.get('token')
  if (queryToken) {
    return queryToken.trim()
  }

  const hash = window.location.hash.replace(/^#/, '')
  if (!hash) {
    return ''
  }

  const hashParams = new URLSearchParams(hash)
  return (hashParams.get('token') || '').trim()
}

function normalizeBackendBase(base: string): string {
  return base.replace(/\/+$/, '').replace(/\/api$/, '')
}

export function EmbedAssistantWidget({ backendBase }: Props) {
  const [token, setToken] = useState('')
  const [session, setSession] = useState<EmbedSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    const nextToken = readTokenFromLocation()
    if (!nextToken) {
      setError('Missing embed session token.')
      return
    }

    setToken(nextToken)
  }, [])

  useEffect(() => {
    if (!token) {
      return
    }

    const controller = new AbortController()

    void (async () => {
      try {
        const response = await fetch(`${normalizeBackendBase(backendBase)}/api/public/embed/session`, {
          cache: 'no-store',
          headers: {
            'X-UZone-Embed-Token': token,
          },
          signal: controller.signal,
        })

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as { detail?: string } | null
          throw new Error(payload?.detail || 'Unable to load the embed session.')
        }

        const data = (await response.json()) as EmbedSession
        setSession(data)
        setError(null)
      } catch (nextError) {
        if (controller.signal.aborted) {
          return
        }
        setError(nextError instanceof Error ? nextError.message : 'Unable to load the embed session.')
      }
    })()

    return () => controller.abort()
  }, [backendBase, token])

  const launcherLabel = session?.launcher_label || 'Have a question?'
  const widgetTitle = session?.widget_title || 'Zoning Assistant'
  const accentColor = session?.accent_color || '#0b67c2'
  const customerName = session?.city_name || 'Your jurisdiction'
  const backendHeaders = token
    ? {
        'X-UZone-Embed-Token': token,
      }
    : undefined

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: '100dvh',
        overflow: 'hidden',
        background:
          'radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 28%), radial-gradient(circle at bottom right, rgba(14, 165, 233, 0.16), transparent 26%), linear-gradient(180deg, #eef4fb 0%, #f8fbff 100%)',
      }}
    >
      {!isOpen ? (
        <div
          style={{
            position: 'fixed',
            right: 20,
            bottom: 20,
            zIndex: 50,
          }}
        >
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 10,
              border: '2px solid #ffffff',
              borderRadius: 999,
              background: accentColor,
              color: '#fff',
              padding: '12px 18px',
              font: 'inherit',
              fontWeight: 700,
              boxShadow: '0 18px 34px rgba(15, 23, 42, 0.22)',
              cursor: 'pointer',
            }}
          >
            <span aria-hidden="true">+</span>
            <span>{launcherLabel}</span>
          </button>
        </div>
      ) : (
        <div
          style={{
            position: 'fixed',
            right: 20,
            bottom: 20,
            top: 'auto',
            width: 'min(420px, calc(100vw - 24px))',
            height: 'min(700px, calc(100dvh - 24px))',
            zIndex: 50,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            borderRadius: 28,
            border: '1px solid rgba(15, 23, 42, 0.08)',
            background: '#ffffff',
            boxShadow: '0 28px 64px rgba(15, 23, 42, 0.24)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              padding: '14px 16px',
              background: `linear-gradient(135deg, ${accentColor} 0%, #0f172a 100%)`,
              color: '#fff',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 700, opacity: 0.82, textTransform: 'uppercase' }}>
                {widgetTitle}
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, lineHeight: 1.2 }}>{customerName}</div>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                border: '1px solid rgba(255,255,255,0.45)',
                background: 'rgba(255,255,255,0.12)',
                color: '#fff',
                fontSize: 20,
                cursor: 'pointer',
              }}
            >
              ×
            </button>
          </div>

          <div style={{ flex: 1, minHeight: 0 }}>
            {error ? (
              <div
                style={{
                  padding: 20,
                  color: '#b91c1c',
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                {error}
              </div>
            ) : session ? (
              <div style={{ height: '100%' }}>
                <PublicAssistantExperience
                  backendBase={backendBase}
                  customerName={customerName}
                  clientId={session.client_id}
                  disclaimerText={session.assistant_disclaimer_text}
                  disclaimerScopeId={session.client_id}
                  initialAccepted={false}
                  requestHeaders={backendHeaders}
                  embedSessionToken={token}
                />
              </div>
            ) : (
              <div
                style={{
                  padding: 20,
                  color: '#475569',
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                Connecting to the assistant…
              </div>
            )}
          </div>

          <div
            style={{
              padding: '10px 16px 12px',
              borderTop: '1px solid rgba(148, 163, 184, 0.18)',
              fontSize: 10,
              color: '#64748b',
              background: '#f8fbff',
              whiteSpace: 'nowrap',
            }}
          >
            <span>Copyright © {new Date().getFullYear()} Gridics. All rights reserved.</span>{' '}
            <a href="https://gridics.com/privacy/" target="_blank" rel="noreferrer" style={{ color: '#0f766e' }}>
              Privacy
            </a>{' '}
            <a href="https://gridics.com/terms/" target="_blank" rel="noreferrer" style={{ color: '#0f766e' }}>
              Terms of Service
            </a>
          </div>
        </div>
      )}

      {!isOpen && error ? (
        <div
          style={{
            position: 'fixed',
            left: 20,
            bottom: 20,
            padding: '10px 12px',
            borderRadius: 12,
            background: '#fff7ed',
            border: '1px solid #fdba74',
            color: '#9a3412',
            fontSize: 12,
            maxWidth: 320,
            boxShadow: '0 16px 28px rgba(15, 23, 42, 0.12)',
          }}
        >
          {error}
        </div>
      ) : null}
    </div>
  )
}
