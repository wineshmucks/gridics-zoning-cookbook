'use client'

import { useEffect, useMemo, useState, useTransition } from 'react'

import { acceptAssistantDisclaimerAction } from '../app/ai-assistant/actions'
import { buildAssistantDisclaimerScopeKey } from '../lib/assistant-disclaimer'
import { AgentChatPanel } from './AgentChatPanel'

const LOCAL_STORAGE_PREFIX = 'uzone:assistant-disclaimer:accepted:'

type Props = {
  backendBase: string
  customerName: string
  clientId: string | null
  disclaimerText: string
  disclaimerScopeId: string
  initialAccepted: boolean
  requestHeaders?: Record<string, string>
  embedSessionToken?: string
}

export function PublicAssistantExperience({
  backendBase,
  customerName,
  clientId,
  disclaimerText,
  disclaimerScopeId,
  initialAccepted,
  requestHeaders,
  embedSessionToken,
}: Props) {
  const [isPending, startTransition] = useTransition()
  const [isAccepted, setIsAccepted] = useState(initialAccepted)
  const [isDismissed, setIsDismissed] = useState(false)
  const scopeKey = useMemo(
    () => buildAssistantDisclaimerScopeKey(disclaimerScopeId),
    [disclaimerScopeId],
  )

  useEffect(() => {
    if (!scopeKey || initialAccepted) {
      return
    }

    try {
      const acceptedAt = window.localStorage.getItem(`${LOCAL_STORAGE_PREFIX}${scopeKey}`)
      if (acceptedAt) {
        setIsAccepted(true)
      }
    } catch {
      // Ignore storage failures and continue showing the notice.
    }
  }, [initialAccepted, scopeKey])

  const handleAcknowledge = () => {
    if (!scopeKey) {
      setIsAccepted(true)
      return
    }

    setIsAccepted(true)
    setIsDismissed(false)

    try {
      window.localStorage.setItem(`${LOCAL_STORAGE_PREFIX}${scopeKey}`, new Date().toISOString())
    } catch {
      // Ignore local storage failures.
    }

    startTransition(async () => {
      await acceptAssistantDisclaimerAction(scopeKey)
    })
  }

  return (
    <>
      {!isAccepted && !isDismissed ? (
        <div className="assistant-disclaimer-overlay" onClick={() => setIsDismissed(true)}>
          <section
            className="card assistant-disclaimer-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Assistant disclaimer"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="assistant-disclaimer-header">
              <h2 style={{ margin: 0 }}>Before you continue</h2>
              <button
                type="button"
                className="assistant-disclaimer-close"
                aria-label="Close disclaimer"
                onClick={() => setIsDismissed(true)}
              >
                x
              </button>
            </div>
            <p className="assistant-disclaimer-copy">{disclaimerText}</p>
            <div className="assistant-disclaimer-actions">
              <button type="button" className="button secondary" onClick={() => setIsDismissed(true)}>
                Close
              </button>
              <button type="button" className="button" onClick={handleAcknowledge} disabled={isPending}>
                {isPending ? 'Saving…' : 'I Understand'}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      <AgentChatPanel
        agentId="customer-zoning-agent"
        backendBase={backendBase}
        customerName={customerName}
        clientId={clientId}
        surface="public-assistant"
        title=""
        description=""
        variant="chatgpt"
        requestHeaders={requestHeaders}
        embedSessionToken={embedSessionToken}
        showEmptyStateHint={false}
        showBrandingFooter={false}
        showModelControls={false}
      />
    </>
  )
}
