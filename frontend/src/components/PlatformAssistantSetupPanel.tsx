'use client'

import { useEffect, useState, type FormEvent } from 'react'

import type { PlatformAssistantSettings } from '../app/admin/actions'
import { buildApiUrl } from '../lib/api'
import { CompactSummaryHeader, FormSection } from './AdminSurfacePrimitives'
import {
  assistantProviderKeyFields,
} from './agenticSetupConfig'

type PlatformAssistantSettingsState = {
  error: string | null
  success: string | null
  settings: PlatformAssistantSettings | null
}

const initialPlatformAssistantSettingsState: PlatformAssistantSettingsState = {
  error: null,
  success: null,
  settings: null,
}

export function PlatformAssistantSetupPanel({
  initialSettings,
}: {
  initialSettings: PlatformAssistantSettings
}) {
  const [settingsState, setSettingsState] = useState<PlatformAssistantSettingsState>(
    initialPlatformAssistantSettingsState,
  )
  const [pending, setPending] = useState(false)
  const [showProviderKeys, setShowProviderKeys] = useState(false)

  const currentSettings = settingsState.settings || initialSettings
  const providerKeys = currentSettings.assistant_provider_keys || {}

  const renderHiddenFields = (options: {
    includeDisclaimer?: boolean
    includeProviderKeys?: boolean
  }) => (
    <>
      {options.includeDisclaimer ? (
        <input type="hidden" name="assistantDisclaimerText" value={currentSettings.assistant_disclaimer_text} />
      ) : null}
      {options.includeProviderKeys
        ? assistantProviderKeyFields.map((provider) => (
            <input
              key={provider.id}
              type="hidden"
              name={provider.fieldName}
              value={providerKeys[provider.id] || ''}
            />
          ))
        : null}
    </>
  )

  useEffect(() => {
    if (!settingsState.success) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      setSettingsState((current) => ({
        ...current,
        success: null,
      }))
    }, 2500)

    return () => window.clearTimeout(timeoutId)
  }, [settingsState.success])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPending(true)
    setSettingsState(initialPlatformAssistantSettingsState)

    const formData = new FormData(event.currentTarget)
    const payload = {
      assistant_disclaimer_text: String(formData.get('assistantDisclaimerText') || '').trim() || null,
      assistant_provider_keys: {
        gemini: String(formData.get('providerKeyGemini') || '').trim() || null,
      },
      assistant_agent_prompts: {},
    }

    try {
      const response = await fetch(buildApiUrl('/api/admin/platform/assistant-settings'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null)
        throw new Error(
          typeof errorPayload?.detail === 'string'
            ? errorPayload.detail
            : 'Unable to save platform assistant settings.',
        )
      }

      const savedSettings = (await response.json()) as PlatformAssistantSettings
      setSettingsState({
        error: null,
        success: 'Platform agentic setup saved.',
        settings: savedSettings,
      })
    } catch (error) {
      setSettingsState({
        error:
          error instanceof Error && error.message
            ? error.message
            : 'Unable to save platform assistant settings.',
        success: null,
        settings: null,
      })
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="panel-stack super-admin-panel-stack">
      <section className="super-admin-summary-card">
        <CompactSummaryHeader title="Platform Agentic Setup" icon="assistant-setup" />
      </section>

      <section className="super-admin-content-panel">
        <FormSection title="Baseline" icon="assistant-setup" hideHeader>
          <div className="admin-form-note">
            These defaults apply across the platform. Jurisdictions can override any field from their own
            Agentic Setup screen.
          </div>
        </FormSection>

        <FormSection title="Disclaimer" icon="jurisdiction-details">
          <form onSubmit={(event) => void handleSubmit(event)} className="admin-form admin-form-compact">
            {renderHiddenFields({
              includeProviderKeys: true,
            })}
            <label className="field field-full">
              <span>Platform disclaimer</span>
              <textarea
                name="assistantDisclaimerText"
                rows={5}
                placeholder="Explain that the assistant can make mistakes and that users should verify important information."
                defaultValue={currentSettings.assistant_disclaimer_text}
              />
              <small>This text becomes the default disclaimer for every jurisdiction.</small>
            </label>
            <div className="admin-form-actions">
              <button className="button button-fit" type="submit" disabled={pending}>
                {pending ? 'Saving…' : 'Save baseline disclaimer'}
              </button>
            </div>
            {settingsState.error ? <div className="status-banner status-banner-error">{settingsState.error}</div> : null}
            {settingsState.success ? (
              <div className="status-banner status-banner-success">{settingsState.success}</div>
            ) : null}
          </form>
        </FormSection>

        <FormSection title="Gemini Key" icon="assistant-setup">
          <form onSubmit={(event) => void handleSubmit(event)} className="admin-form admin-form-compact">
            {renderHiddenFields({
              includeDisclaimer: true,
            })}
            <label className="api-key-toggle">
              <span className="api-key-toggle-copy">
                <span>Show saved key values</span>
                <span className="api-key-toggle-state">{showProviderKeys ? 'On' : 'Off'}</span>
              </span>
              <span className="api-key-toggle-switch">
                <input
                  type="checkbox"
                  checked={showProviderKeys}
                  onChange={(event) => setShowProviderKeys(event.target.checked)}
                  aria-label="Show saved key values"
                />
                <span className="api-key-toggle-track" aria-hidden="true" />
              </span>
            </label>
            <div className="admin-form-grid admin-form-grid-single">
              {assistantProviderKeyFields.map((provider) => (
                <label key={provider.id} className="field field-full">
                  <span>{provider.label}</span>
                  <input
                    name={provider.fieldName}
                    type={showProviderKeys ? 'text' : 'password'}
                    autoComplete="off"
                    placeholder={`Optional platform ${provider.id} key`}
                    defaultValue={providerKeys[provider.id] || ''}
                  />
                  <small>Used whenever a jurisdiction does not provide its own Gemini key.</small>
                </label>
              ))}
            </div>
            <div className="admin-form-actions">
              <button className="button button-fit" type="submit" disabled={pending}>
                {pending ? 'Saving…' : 'Save Gemini key'}
              </button>
            </div>
            {settingsState.error ? <div className="status-banner status-banner-error">{settingsState.error}</div> : null}
            {settingsState.success ? (
              <div className="status-banner status-banner-success">{settingsState.success}</div>
            ) : null}
          </form>
        </FormSection>

      </section>
    </div>
  )
}
