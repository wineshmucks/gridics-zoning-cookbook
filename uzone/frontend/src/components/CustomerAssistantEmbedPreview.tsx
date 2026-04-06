'use client'

import { useEffect, useState } from 'react'

import type { CustomerEmbedSettings } from '../app/admin/actions'

type Props = {
  backendBase: string
  customer: {
    id: string
    name: string
  }
  embedSettings: CustomerEmbedSettings
  embedSecret: string | null
  initialOrigin: string | null
}

type EmbedSessionCreateResponse = {
  token: string
  expires_at: string
  client_id: string
  city_name: string
  department_name: string
  assistant_disclaimer_text: string
  widget_title: string
  launcher_label: string
  accent_color: string
  allowed_origins: string[]
  origin: string | null
}

export function CustomerAssistantEmbedPreview({
  backendBase,
  customer,
  embedSettings,
  embedSecret,
  initialOrigin,
}: Props) {
  const [origin, setOrigin] = useState(initialOrigin || embedSettings.allowed_origins[0] || '')
  const [secret, setSecret] = useState(embedSecret || '')
  const [iframeSrc, setIframeSrc] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [copiedLive, setCopiedLive] = useState(false)
  const [frontendOrigin, setFrontendOrigin] = useState('https://your-uzone-domain')

  useEffect(() => {
    if (initialOrigin) {
      setOrigin(initialOrigin)
      return
    }

    if (embedSettings.allowed_origins.length > 0) {
      setOrigin(embedSettings.allowed_origins[0])
      return
    }

    setOrigin(window.location.origin)
  }, [embedSettings.allowed_origins, initialOrigin])

  useEffect(() => {
    if (embedSecret) {
      setSecret(embedSecret)
    }
  }, [embedSecret])

  useEffect(() => {
    setFrontendOrigin(window.location.origin)
  }, [])

  const iframeSnippet =
    `<iframe src="${frontendOrigin}/embed#token=TOKEN_FROM_YOUR_SERVER" ` +
    'style="position:fixed;right:20px;bottom:20px;width:420px;height:700px;border:0;z-index:2147483647;" ' +
    'allow="clipboard-read; clipboard-write"></iframe>'

  const hostTokenSnippet = `fetch('${backendBase}/api/public/embed/sessions', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-UZone-Embed-Secret': '<your embed secret>',
  },
  body: JSON.stringify({
    client_id: '${customer.id}',
    origin: '${origin}',
  }),
  })`

  const loadPreviewSecret = async () => {
    if (secret.trim()) {
      return secret.trim()
    }

    const response = await fetch(`${backendBase}/api/admin/clients/${customer.id}/assistant-embed/preview-secret`, {
      method: 'POST',
    })
    const payload = (await response.json().catch(() => null)) as { secret?: string; detail?: string } | null

    if (!response.ok) {
      throw new Error(
        typeof payload?.detail === 'string'
          ? payload.detail
          : 'Unable to generate a preview secret.',
      )
    }

    const generatedSecret = typeof payload?.secret === 'string' ? payload.secret.trim() : ''
    if (!generatedSecret) {
      throw new Error('The preview secret was not returned by the server.')
    }

    setSecret(generatedSecret)
    return generatedSecret
  }

  const mintPreviewToken = async () => {
    if (!origin.trim()) {
      setError('Enter an origin to test.')
      return
    }

    setLoading(true)
    setError(null)
    setStatus(null)

    try {
      const activeSecret = await loadPreviewSecret()
      const response = await fetch(`${backendBase}/api/public/embed/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-UZone-Embed-Secret': activeSecret,
        },
        body: JSON.stringify({
          client_id: customer.id,
          origin: origin.trim(),
        }),
      })

      const payload = (await response.json().catch(() => null)) as EmbedSessionCreateResponse | null
      const errorPayload = payload as { detail?: string } | null

      if (!response.ok) {
        const detail = typeof errorPayload?.detail === 'string' ? errorPayload.detail : ''
        if (detail.includes('Embed session signing secret is not configured')) {
          throw new Error(
            'Backend embed signing secret is missing. Set UZONE_EMBED_SESSION_SIGNING_SECRET in uzone/.env and restart the backend.',
          )
        }
        throw new Error(
          detail || 'Unable to mint preview token.',
        )
      }

      const token = typeof payload?.token === 'string' ? payload.token : ''
      if (!token) {
        throw new Error('Preview token was not returned by the server.')
      }

      setIframeSrc(`${frontendOrigin}/embed#token=${encodeURIComponent(token)}`)
      setStatus(`Preview token minted for ${origin.trim()}.`)
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to mint preview token.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!origin.trim()) {
      setOrigin(window.location.origin)
    }
  }, [origin])

  useEffect(() => {
    if (!embedSecret || !origin.trim() || iframeSrc) {
      return
    }

    void mintPreviewToken()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [embedSecret, origin, iframeSrc])

  const copyIframeSnippet = async () => {
    await navigator.clipboard.writeText(iframeSnippet)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2000)
  }

  const liveIframeSnippet = iframeSrc
    ? `<iframe src="${iframeSrc}" style="width:100%;height:720px;border:0;" allow="clipboard-read; clipboard-write"></iframe>`
    : ''

  const copyLiveIframeSnippet = async () => {
    if (!liveIframeSnippet) {
      return
    }

    await navigator.clipboard.writeText(liveIframeSnippet)
    setCopiedLive(true)
    window.setTimeout(() => setCopiedLive(false), 2000)
  }

  return (
    <div className="panel-stack">
      <div className="admin-list">
        <div className="admin-list-heading">Preview controls</div>
        <div style={{ color: 'var(--muted)' }}>
          Use a trusted origin that is allowed in the embed settings. If no secret is entered, the
          preview will generate one automatically for this session.
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 13, lineHeight: 1.45 }}>
          The preview also requires the backend env var <code>UZONE_EMBED_SESSION_SIGNING_SECRET</code>.
          Set it in <code>uzone/.env</code> or your backend container, then restart the backend.
        </div>
        <div className="admin-form">
          <label className="field">
            <span>Embed secret</span>
            <input
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              placeholder="uz_embed_..."
              spellCheck={false}
              autoComplete="off"
            />
          </label>
          <label className="field">
            <span>Preview origin</span>
            <input
              value={origin}
              onChange={(event) => setOrigin(event.target.value)}
              placeholder="https://partner.example.com"
            />
          </label>
        </div>
        <div className="button-row">
          <button type="button" className="button" onClick={() => void mintPreviewToken()} disabled={loading}>
            {loading ? 'Loading…' : 'Load preview'}
          </button>
          <button type="button" className="button secondary" onClick={() => void copyIframeSnippet()}>
            {copied ? 'Copied' : 'Copy iframe snippet'}
          </button>
        </div>
        {error ? <div className="status-banner status-banner-error">{error}</div> : null}
        {status ? <div className="status-banner status-banner-success">{status}</div> : null}
      </div>

      <div className="admin-list">
        <div className="admin-list-heading">Production iframe snippet</div>
        <div style={{ color: 'var(--muted)' }}>
          The host site should mint a short-lived token from its backend, then set that token in the
          iframe fragment.
        </div>
        <div className="assistant-settings-debug">
          <pre>{hostTokenSnippet}</pre>
        </div>
        <div className="assistant-settings-debug">
          <pre>{iframeSnippet}</pre>
        </div>
      </div>

      <div className="admin-list">
        <div className="admin-list-heading">Live preview</div>
        <div style={{ color: 'var(--muted)' }}>
          This iframe loads the widget using a freshly minted embed token.
        </div>
        <div className="button-row">
          <button
            type="button"
            className="button secondary"
            onClick={() => void copyLiveIframeSnippet()}
            disabled={!liveIframeSnippet}
          >
            {copiedLive ? 'Copied' : 'Copy live iframe snippet'}
          </button>
        </div>
        <div
          style={{
            minHeight: 'min(720px, 80vh)',
            border: '1px solid rgba(15, 23, 42, 0.12)',
            borderRadius: 20,
            overflow: 'hidden',
            background: '#fff',
          }}
        >
          {iframeSrc ? (
            <iframe
              src={iframeSrc}
              title={`${customer.name} assistant preview`}
              style={{ width: '100%', height: '100%', minHeight: '720px', border: 0 }}
            />
          ) : (
            <div style={{ padding: 24, color: 'var(--muted)' }}>Loading preview…</div>
          )}
        </div>
      </div>
    </div>
  )
}
