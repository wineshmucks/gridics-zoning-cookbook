'use client'

import { useEffect, useState, type FormEvent } from 'react'

import type { PlatformAssistantSettings } from '../app/admin/actions'
import { buildApiUrl } from '../lib/api'
import { CompactSummaryHeader, FormSection } from './AdminSurfacePrimitives'
import {
  describeAssistantModelTarget,
  hasAssistantModelTarget,
  modelTargetFields,
  providerFields,
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
  const modelTargets = currentSettings.assistant_model_targets || {}
  const codeDefaultModelTargets = currentSettings.code_default_assistant_model_targets || {}
  const agentPrompts = currentSettings.assistant_agent_prompts || {}

  const renderHiddenFields = (options: {
    includeDisclaimer?: boolean
    includeProviderKeys?: boolean
    includeModelTargets?: boolean
    includeAgentPrompts?: boolean
  }) => (
    <>
      {options.includeDisclaimer ? (
        <input type="hidden" name="assistantDisclaimerText" value={currentSettings.assistant_disclaimer_text} />
      ) : null}
      {options.includeProviderKeys
        ? providerFields.map((provider) => (
            <input
              key={provider.id}
              type="hidden"
              name={provider.fieldName}
              value={providerKeys[provider.id] || ''}
            />
          ))
        : null}
      {options.includeModelTargets
        ? modelTargetFields.map((target) => {
            const targetSettings = modelTargets[target.id] || {
              provider: null,
              model_id: null,
              base_url: null,
            }

            return (
              <span key={target.id}>
                <input
                  type="hidden"
                  name={target.providerFieldName}
                  value={targetSettings.provider || ''}
                />
                <input
                  type="hidden"
                  name={target.modelFieldName}
                  value={targetSettings.model_id || ''}
                />
                <input
                  type="hidden"
                  name={target.baseUrlFieldName}
                  value={targetSettings.base_url || ''}
                />
              </span>
            )
          })
        : null}
      {options.includeAgentPrompts
        ? Object.entries(agentPrompts).map(([targetId, prompt]) => (
            <input
              key={targetId}
              type="hidden"
              name={(() => {
                switch (targetId) {
                  case 'customer-zoning-agent':
                    return 'promptCustomerZoningAgent'
                  case 'parcel-data-agent':
                    return 'promptParcelDataAgent'
                  case 'code-researcher-agent':
                    return 'promptCodeResearcherAgent'
                  default:
                    return `prompt-${targetId}`
                }
              })()}
              value={prompt || ''}
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
        openrouter: String(formData.get('providerKeyOpenrouter') || '').trim() || null,
        openai: String(formData.get('providerKeyOpenai') || '').trim() || null,
        groq: String(formData.get('providerKeyGroq') || '').trim() || null,
      },
      assistant_model_targets: {
        'customer-zoning-agent': {
          provider: String(formData.get('targetProviderCustomerZoningAgent') || '').trim() || null,
          model_id: String(formData.get('targetModelCustomerZoningAgent') || '').trim() || null,
          base_url: String(formData.get('targetBaseUrlCustomerZoningAgent') || '').trim() || null,
        },
        'parcel-data-agent': {
          provider: String(formData.get('targetProviderParcelDataAgent') || '').trim() || null,
          model_id: String(formData.get('targetModelParcelDataAgent') || '').trim() || null,
          base_url: String(formData.get('targetBaseUrlParcelDataAgent') || '').trim() || null,
        },
        'code-researcher-agent': {
          provider: String(formData.get('targetProviderCodeResearcherAgent') || '').trim() || null,
          model_id: String(formData.get('targetModelCodeResearcherAgent') || '').trim() || null,
          base_url: String(formData.get('targetBaseUrlCodeResearcherAgent') || '').trim() || null,
        },
      },
      assistant_agent_prompts: {
        'customer-zoning-agent': agentPrompts['customer-zoning-agent'] || null,
        'parcel-data-agent': agentPrompts['parcel-data-agent'] || null,
        'code-researcher-agent': agentPrompts['code-researcher-agent'] || null,
      },
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
              includeModelTargets: true,
              includeAgentPrompts: true,
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

        <FormSection title="API Keys" icon="assistant-setup">
          <form onSubmit={(event) => void handleSubmit(event)} className="admin-form admin-form-compact">
            {renderHiddenFields({
              includeDisclaimer: true,
              includeModelTargets: true,
              includeAgentPrompts: true,
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
              {providerFields.map((provider) => (
                <label key={provider.id} className="field field-full">
                  <span>{provider.label}</span>
                  <input
                    name={provider.fieldName}
                    type={showProviderKeys ? 'text' : 'password'}
                    autoComplete="off"
                    placeholder={`Optional platform ${provider.id} key`}
                    defaultValue={providerKeys[provider.id] || ''}
                  />
                  <small>Used whenever a jurisdiction does not provide its own provider key.</small>
                </label>
              ))}
            </div>
            <div className="admin-form-actions">
              <button className="button button-fit" type="submit" disabled={pending}>
                {pending ? 'Saving…' : 'Save baseline API keys'}
              </button>
            </div>
            {settingsState.error ? <div className="status-banner status-banner-error">{settingsState.error}</div> : null}
            {settingsState.success ? (
              <div className="status-banner status-banner-success">{settingsState.success}</div>
            ) : null}
          </form>
        </FormSection>

        <FormSection title="Models" icon="assistant">
          <form onSubmit={(event) => void handleSubmit(event)} className="admin-form admin-form-compact">
            {renderHiddenFields({
              includeDisclaimer: true,
              includeProviderKeys: true,
              includeAgentPrompts: true,
            })}
            <div className="admin-form-grid admin-form-grid-single">
              {modelTargetFields.map((target) => {
                const targetSettings = modelTargets[target.id] || {
                  provider: null,
                  model_id: null,
                  base_url: null,
                }

                return (
                  <div key={target.id} className="admin-target-row">
                    <div className="admin-target-row-head">
                      <strong>{target.label}</strong>
                    </div>
                    <div className="admin-form-grid admin-form-grid-3">
                      <label className="field">
                        <span>Provider</span>
                        <select name={target.providerFieldName} defaultValue={targetSettings.provider || ''}>
                          <option value="">Use code default</option>
                          <option value="gemini">Gemini</option>
                          <option value="openrouter">OpenRouter</option>
                          <option value="openai">OpenAI</option>
                          <option value="groq">Groq</option>
                        </select>
                      </label>
                      <label className="field">
                        <span>Model ID</span>
                        <input
                          name={target.modelFieldName}
                          type="text"
                          placeholder="Use code default"
                          defaultValue={targetSettings.model_id || ''}
                        />
                      </label>
                      <label className="field">
                        <span>Base URL</span>
                        <input
                          name={target.baseUrlFieldName}
                          type="text"
                          placeholder="Optional custom base URL"
                          defaultValue={targetSettings.base_url || ''}
                        />
                      </label>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="admin-form-actions">
              <button className="button button-fit" type="submit" disabled={pending}>
                {pending ? 'Saving…' : 'Save baseline models'}
              </button>
            </div>
            {settingsState.error ? <div className="status-banner status-banner-error">{settingsState.error}</div> : null}
            {settingsState.success ? (
              <div className="status-banner status-banner-success">{settingsState.success}</div>
            ) : null}
          </form>
        </FormSection>

        <FormSection title="Agent Prompts" icon="assistant">
          <div className="admin-form-note">
            Prompt editing is temporarily disabled. The platform currently uses the assistant
            instructions checked into the codebase.
          </div>
        </FormSection>
      </section>
    </div>
  )
}
