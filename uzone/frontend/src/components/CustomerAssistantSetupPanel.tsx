'use client'

import { useActionState, useEffect, useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'

import {
  ingestCustomerZoningKnowledgeAction,
  reindexCustomerZoningKnowledgeAction,
  type CustomerExperienceSettings,
  type CustomerExperienceSettingsState,
  type CustomerZoningKnowledgeMutationState,
  type CustomerZoningKnowledgeStatus,
} from '../app/admin/actions'
import { buildApiUrl } from '../lib/api'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

const providerFields = [
  { id: 'gemini', label: 'Gemini API key', fieldName: 'providerKeyGemini' },
  { id: 'openrouter', label: 'OpenRouter API key', fieldName: 'providerKeyOpenrouter' },
  { id: 'openai', label: 'OpenAI API key', fieldName: 'providerKeyOpenai' },
  { id: 'groq', label: 'Groq API key', fieldName: 'providerKeyGroq' },
] as const

const modelTargetFields = [
  {
    id: 'customer-zoning-agent',
    label: 'Lead team',
    description: 'Controls the customer zoning lead agent that orchestrates the run.',
    providerFieldName: 'targetProviderCustomerZoningAgent',
    modelFieldName: 'targetModelCustomerZoningAgent',
    baseUrlFieldName: 'targetBaseUrlCustomerZoningAgent',
  },
  {
    id: 'parcel-data-agent',
    label: 'Parcel data agent',
    description: 'Controls the member that fetches and summarizes Gridics parcel context.',
    providerFieldName: 'targetProviderParcelDataAgent',
    modelFieldName: 'targetModelParcelDataAgent',
    baseUrlFieldName: 'targetBaseUrlParcelDataAgent',
  },
  {
    id: 'code-researcher-agent',
    label: 'Code researcher agent',
    description: 'Controls the member that queries the zoning knowledge base for citations.',
    providerFieldName: 'targetProviderCodeResearcherAgent',
    modelFieldName: 'targetModelCodeResearcherAgent',
    baseUrlFieldName: 'targetBaseUrlCodeResearcherAgent',
  },
] as const

const initialExperienceSettingsState: CustomerExperienceSettingsState = {
  error: null,
  success: null,
  settings: null,
}

const initialZoningKnowledgeMutationState: CustomerZoningKnowledgeMutationState = {
  error: null,
  success: null,
}

export function CustomerAssistantSetupPanel({
  customer,
  experienceSettings,
  zoningKnowledgeStatus,
}: {
  customer: SelectedCustomer
  experienceSettings: CustomerExperienceSettings
  zoningKnowledgeStatus: CustomerZoningKnowledgeStatus
}) {
  const router = useRouter()
  const [liveZoningKnowledgeStatus, setLiveZoningKnowledgeStatus] =
    useState<CustomerZoningKnowledgeStatus>(zoningKnowledgeStatus)
  const [experienceState, setExperienceState] =
    useState<CustomerExperienceSettingsState>(initialExperienceSettingsState)
  const [experiencePending, setExperiencePending] = useState(false)
  const [ingestState, ingestAction, ingestPending] = useActionState(
    ingestCustomerZoningKnowledgeAction,
    initialZoningKnowledgeMutationState,
  )
  const [reindexState, reindexAction, reindexPending] = useActionState(
    reindexCustomerZoningKnowledgeAction,
    initialZoningKnowledgeMutationState,
  )
  const [showProviderKeys, setShowProviderKeys] = useState(false)
  const latestRun = liveZoningKnowledgeStatus.latest_run
  const zoningRunActive = latestRun?.status === 'queued' || latestRun?.status === 'running'
  const providerKeys = experienceSettings.assistant_provider_keys || {}
  const modelTargets = experienceSettings.assistant_model_targets || {}

  useEffect(() => {
    setLiveZoningKnowledgeStatus(zoningKnowledgeStatus)
  }, [zoningKnowledgeStatus])

  useEffect(() => {
    if (!experienceState.success) {
      return
    }
    router.refresh()
  }, [experienceState.success, router])

  useEffect(() => {
    let cancelled = false
    let intervalId: ReturnType<typeof setInterval> | null = null

    const loadStatus = async () => {
      try {
        const response = await fetch(
          buildApiUrl(`/api/admin/clients/${customer.id}/zoning-knowledge`),
          { cache: 'no-store' },
        )
        if (!response.ok) {
          return
        }

        const payload = (await response.json()) as CustomerZoningKnowledgeStatus
        if (!cancelled) {
          setLiveZoningKnowledgeStatus(payload)
        }
      } catch {
        // Keep the last known status if polling fails.
      }
    }

    loadStatus()
    if (zoningRunActive) {
      intervalId = setInterval(loadStatus, 3000)
    }

    return () => {
      cancelled = true
      if (intervalId) {
        clearInterval(intervalId)
      }
    }
  }, [customer.id, zoningRunActive])

  const handleExperienceSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setExperiencePending(true)
    setExperienceState(initialExperienceSettingsState)

    const formData = new FormData(event.currentTarget)
    const organizationId = String(formData.get('organizationId') || '').trim()
    const zoningCodeUrl = String(formData.get('zoningCodeUrl') || '').trim()
    const payload = {
      zoning_code_url: zoningCodeUrl || null,
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
    }

    try {
      const response = await fetch(
        buildApiUrl(`/api/admin/clients/${organizationId}/experience-settings`),
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
          credentials: 'include',
        },
      )

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null)
        throw new Error(
          typeof errorPayload?.detail === 'string'
            ? errorPayload.detail
            : 'Unable to save jurisdiction assistant settings.',
        )
      }

      const savedSettings = (await response.json()) as CustomerExperienceSettings
      setExperienceState({
        error: null,
        success: 'Jurisdiction assistant settings saved.',
        settings: savedSettings,
      })
    } catch (error) {
      setExperienceState({
        error:
          error instanceof Error && error.message
            ? error.message
            : 'Unable to save jurisdiction assistant settings.',
        success: null,
        settings: null,
      })
    } finally {
      setExperiencePending(false)
    }
  }

  return (
    <div className="panel-stack">
      <div className="admin-list">
        <div className="admin-list-heading">Assistant setup</div>
        <form onSubmit={(event) => void handleExperienceSubmit(event)} className="admin-form">
          <input type="hidden" name="organizationId" value={customer.id} />
          <label className="field">
            <span>Zoning code URL</span>
            <input
              name="zoningCodeUrl"
              type="url"
              placeholder="https://library.municode.com/.../zoning"
              defaultValue={experienceSettings.zoning_code_url || ''}
            />
          </label>
          <div style={{ color: 'var(--muted)' }}>
            Save the public zoning code source for {customer.name}. Ingestion uses this URL to build
            the tenant-specific knowledge base.
          </div>
          <label className="field">
            <span>Assistant disclaimer</span>
            <textarea
              name="assistantDisclaimerText"
              rows={5}
              placeholder="Explain that the assistant can make mistakes and that users should verify important information."
              defaultValue={experienceSettings.assistant_disclaimer_text}
            />
          </label>
          <div style={{ color: 'var(--muted)' }}>
            This text appears as a first-visit acknowledgement when someone opens the public
            assistant for this jurisdiction.
          </div>
          <div className="panel-stack">
            <div className="admin-list-heading">Provider API keys</div>
            <div style={{ color: 'var(--muted)' }}>
              These keys are saved for this jurisdiction only and are used when a model target below
              points at that provider. Leave any field blank to keep using the server environment for
              that provider.
            </div>
            <label className="field" style={{ gap: 8 }}>
              <span>Show saved key values</span>
              <input
                type="checkbox"
                checked={showProviderKeys}
                onChange={(event) => setShowProviderKeys(event.target.checked)}
              />
            </label>
            <div className="panel-stack">
              {providerFields.map((provider) => (
                <label key={provider.id} className="field">
                  <span>{provider.label}</span>
                  <input
                    name={provider.fieldName}
                    type={showProviderKeys ? 'text' : 'password'}
                    autoComplete="off"
                    placeholder={`Optional ${provider.id} key for ${customer.name}`}
                    defaultValue={providerKeys[provider.id] || ''}
                  />
                </label>
              ))}
            </div>
          </div>
          <div className="panel-stack">
            <div className="admin-list-heading">Assistant model targets</div>
            <div style={{ color: 'var(--muted)' }}>
              Configure each team or member independently. Leave a target blank to keep the model
              defined in code. Set a provider and model together to override that target for this
              customer.
            </div>
            <div className="panel-stack">
              {modelTargetFields.map((target) => {
                const targetSettings = modelTargets[target.id] || {
                  provider: null,
                  model_id: null,
                  base_url: null,
                }

                return (
                  <div key={target.id} className="assistant-target-card">
                    <div className="assistant-target-card-header">
                      <strong>{target.label}</strong>
                      <span>{target.description}</span>
                    </div>
                    <div className="assistant-target-card-fields">
                      <label className="field">
                        <span>Provider</span>
                        <select
                          name={target.providerFieldName}
                          defaultValue={targetSettings.provider || ''}
                        >
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
          </div>
          <button className="button button-fit" type="submit" disabled={experiencePending}>
            {experiencePending ? 'Saving…' : 'Save'}
          </button>
          {experienceState.error ? (
            <div className="status-banner status-banner-error">{experienceState.error}</div>
          ) : null}
          {experienceState.success ? (
            <div className="status-banner status-banner-success">{experienceState.success}</div>
          ) : null}
          <div className="assistant-settings-debug">
            <strong>Loaded settings from backend</strong>
            <pre>{JSON.stringify(experienceSettings, null, 2)}</pre>
          </div>
          {experienceState.settings ? (
            <div className="assistant-settings-debug">
              <strong>Save response from backend</strong>
              <pre>{JSON.stringify(experienceState.settings, null, 2)}</pre>
            </div>
          ) : null}
        </form>
      </div>

      <div className="admin-list">
        <div className="admin-list-heading">Zoning knowledge</div>
        <div className="panel-stack">
          <div className="assistant-setup-stats">
            <div className="assistant-setup-stat">
              <span>Documents</span>
              <strong>{liveZoningKnowledgeStatus.documents}</strong>
            </div>
            <div className="assistant-setup-stat">
              <span>Sections</span>
              <strong>{liveZoningKnowledgeStatus.sections}</strong>
            </div>
            <div className="assistant-setup-stat">
              <span>Chunks</span>
              <strong>{liveZoningKnowledgeStatus.chunks}</strong>
            </div>
          </div>

          <div className="assistant-setup-meta">
            <div>
              <strong>Source URL</strong>
              <div>{liveZoningKnowledgeStatus.zoning_code_url || 'No zoning code URL configured.'}</div>
            </div>
            <div>
              <strong>Client binding</strong>
              <div>{liveZoningKnowledgeStatus.client_id}</div>
            </div>
          </div>

          {liveZoningKnowledgeStatus.latest_run ? (
            <div className="assistant-setup-run">
              <strong>{zoningRunActive ? 'Current run' : 'Last run'}</strong>
              <div>
                {liveZoningKnowledgeStatus.latest_run.mode} · {liveZoningKnowledgeStatus.latest_run.status}
              </div>
              <div>
                Crawled {liveZoningKnowledgeStatus.latest_run.pages_crawled} pages, extracted{' '}
                {liveZoningKnowledgeStatus.latest_run.documents_extracted} documents,{' '}
                {liveZoningKnowledgeStatus.latest_run.sections_extracted} sections, and upserted{' '}
                {liveZoningKnowledgeStatus.latest_run.chunks_upserted} chunks.
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--muted)' }}>No zoning knowledge ingestion has run yet.</div>
          )}

          {latestRun?.status === 'failed' && latestRun.error_message ? (
            <div className="status-banner status-banner-error">{latestRun.error_message}</div>
          ) : null}

          {zoningRunActive ? (
            <div className="status-banner status-banner-success">
              {latestRun?.status === 'queued' ? 'Ingestion is queued.' : 'Ingestion is running.'} This page refreshes
              automatically every few seconds.
            </div>
          ) : null}

          <div className="button-row">
            <form action={ingestAction}>
              <input type="hidden" name="organizationId" value={customer.id} />
              <button className="button" type="submit" disabled={ingestPending || zoningRunActive}>
                {ingestPending ? 'Starting…' : zoningRunActive ? 'Ingest Running…' : 'Ingest'}
              </button>
            </form>

            <form action={reindexAction}>
              <input type="hidden" name="organizationId" value={customer.id} />
              <button className="button secondary" type="submit" disabled={reindexPending || zoningRunActive}>
                {reindexPending ? 'Starting…' : zoningRunActive ? 'Run In Progress…' : 'Reindex'}
              </button>
            </form>
          </div>

          {ingestState.error ? (
            <div className="status-banner status-banner-error">{ingestState.error}</div>
          ) : null}
          {ingestState.success ? (
            <div className="status-banner status-banner-success">{ingestState.success}</div>
          ) : null}
          {reindexState.error ? (
            <div className="status-banner status-banner-error">{reindexState.error}</div>
          ) : null}
          {reindexState.success ? (
            <div className="status-banner status-banner-success">{reindexState.success}</div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
