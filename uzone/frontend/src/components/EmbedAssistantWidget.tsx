'use client'

import { useEffect, useState } from 'react'

import { BuildingLogo } from './BuildingLogo'
import { PublicAssistantExperience } from './PublicAssistantExperience'

type EmbedSession = {
  client_id: string
  city_name: string
  department_name: string
  logo_path?: string | null
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

function dispatchEmbedChatAction(action: 'copy' | 'new-chat') {
  if (typeof window === 'undefined') {
    return
  }

  window.dispatchEvent(new CustomEvent('uzone-embed-chat-action', { detail: { action } }))
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
  const productTitle = 'AI Planning & Zoning Assistant'
  const accentColor = session?.accent_color || '#0b67c2'
  const customerName = session?.city_name || 'Your jurisdiction'
  const backendHeaders = token
    ? {
        'X-UZone-Embed-Token': token,
      }
    : undefined

  return (
    <div className="embed-widget-canvas">
      {!isOpen ? (
        <div className="embed-widget-launcher-wrap">
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            className="embed-widget-launcher"
            style={{ ['--embed-accent' as string]: accentColor }}
          >
            <span className="embed-widget-launcher-kicker">Ask Miami zoning</span>
            <span className="embed-widget-launcher-label">{launcherLabel}</span>
          </button>
        </div>
      ) : (
        <div className="embed-widget-shell" style={{ ['--embed-accent' as string]: accentColor }}>
          <div className="embed-widget-header">
            <div className="embed-widget-header-copy">
              <div className="embed-widget-title-row">
                <div className={`embed-widget-logo${session?.logo_path ? ' has-image' : ''}`}>
                  <BuildingLogo logoUrl={session?.logo_path || null} alt={`${customerName} logo`} />
                </div>
                <div className="embed-widget-city">{customerName}</div>
              </div>
              <div className="embed-widget-eyebrow">{productTitle}</div>
            </div>
            <div className="embed-widget-header-actions">
              <button
                type="button"
                onClick={() => dispatchEmbedChatAction('copy')}
                aria-label="Copy conversation"
                className="embed-widget-header-button"
                title="Copy conversation"
              >
                ⎘
              </button>
              <button
                type="button"
                onClick={() => dispatchEmbedChatAction('new-chat')}
                aria-label="Start a new chat"
                className="embed-widget-header-button"
                title="New chat"
              >
                +
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
                className="embed-widget-close"
              >
                ×
              </button>
            </div>
          </div>

          <div className="embed-widget-body">
            {error ? (
              <div className="embed-widget-state embed-widget-state-error">{error}</div>
            ) : session ? (
              <div className="embed-widget-experience">
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
              <div className="embed-widget-state">Connecting to the assistant…</div>
            )}
          </div>

        </div>
      )}

      {!isOpen && error ? (
        <div className="embed-widget-error-toast">{error}</div>
      ) : null}
    </div>
  )
}
