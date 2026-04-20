'use client'

import { useEffect } from 'react'

type ErrorPayload = {
  message: string
  stack: string | null
  source: string | null
  location: string
  userAgent: string
  kind: 'error' | 'unhandledrejection'
}

function sendClientError(payload: ErrorPayload) {
  try {
    const body = JSON.stringify(payload)
    if (navigator.sendBeacon) {
      const blob = new Blob([body], { type: 'application/json' })
      if (navigator.sendBeacon('/api/client-error', blob)) {
        return
      }
    }

    void fetch('/api/client-error', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body,
      keepalive: true,
    })
  } catch {
    // Swallow error reporting failures.
  }
}

export function ClientErrorReporter() {
  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      sendClientError({
        kind: 'error',
        message: event.message || 'Unknown browser error',
        stack: event.error instanceof Error ? event.error.stack || null : null,
        source: event.filename ? `${event.filename}:${event.lineno || 0}:${event.colno || 0}` : null,
        location: window.location.href,
        userAgent: navigator.userAgent,
      })
    }

    const handleRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason
      sendClientError({
        kind: 'unhandledrejection',
        message:
          reason instanceof Error
            ? reason.message
            : typeof reason === 'string'
              ? reason
              : 'Unhandled promise rejection',
        stack: reason instanceof Error ? reason.stack || null : null,
        source: null,
        location: window.location.href,
        userAgent: navigator.userAgent,
      })
    }

    window.addEventListener('error', handleError)
    window.addEventListener('unhandledrejection', handleRejection)
    return () => {
      window.removeEventListener('error', handleError)
      window.removeEventListener('unhandledrejection', handleRejection)
    }
  }, [])

  return null
}
