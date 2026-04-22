'use client'

import Link from 'next/link'
import { useActionState, useEffect, useState, type FormEvent } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import {
  ingestCustomerZoningKnowledgeAction,
  saveCustomerEmbedSettingsAction,
  reindexCustomerZoningKnowledgeAction,
  type CustomerEmbedSettings,
  type CustomerEmbedSettingsState,
  type CustomerExperienceSettings,
  type CustomerExperienceSettingsState,
  type CustomerZoningKnowledgeMutationState,
  type CustomerZoningKnowledgeStatus,
} from '../app/admin/actions'
import { buildApiUrl } from '../lib/api'
import { buildSuperAdminCustomerAssistantEmbedPath } from '../lib/org-url'
import { CompactSummaryHeader, FormSection } from './AdminSurfacePrimitives'
import { CustomerAssistantEmbedPreview } from './CustomerAssistantEmbedPreview'
import {
  assistantProviderKeyFields,
} from './agenticSetupConfig'
import { getClientBackendOrigin } from '../lib/backend'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

type AgenticSection =
  | 'general'
  | 'api-keys'
  | 'knowledge'
  | 'integrations'

const initialExperienceSettingsState: CustomerExperienceSettingsState = {
  error: null,
  success: null,
  settings: null,
}

const initialEmbedSettingsState: CustomerEmbedSettingsState = {
  error: null,
  success: null,
  secret: null,
  settings: null,
}

const initialZoningKnowledgeMutationState: CustomerZoningKnowledgeMutationState = {
  error: null,
  success: null,
}

export function CustomerAssistantSetupPanel({
  customer,
  experienceSettings,
  embedSettings,
  zoningKnowledgeStatus,
  baselineSettings,
}: {
  customer: SelectedCustomer
  experienceSettings: CustomerExperienceSettings
  embedSettings: CustomerEmbedSettings
  zoningKnowledgeStatus: CustomerZoningKnowledgeStatus
  baselineSettings?: CustomerExperienceSettings | null
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
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
  const [embedState, embedAction, embedPending] = useActionState(
    saveCustomerEmbedSettingsAction,
    initialEmbedSettingsState,
  )
  const [showProviderKeys, setShowProviderKeys] = useState(false)
  const [copiedEmbedSnippet, setCopiedEmbedSnippet] = useState(false)
  const [frontendOrigin, setFrontendOrigin] = useState('https://your-uzone-domain')
  const backendBase = getClientBackendOrigin()
  const sectionParam = searchParams.get('section')
  const activeSection: AgenticSection =
    sectionParam === 'llm'
        ? 'api-keys'
    : sectionParam === 'api-keys' ||
          sectionParam === 'knowledge' ||
          sectionParam === 'integrations'
      ? sectionParam
      : 'general'
  const latestRun = liveZoningKnowledgeStatus.latest_run
  const zoningRunActive = latestRun?.status === 'queued' || latestRun?.status === 'running'
  const zoningKnowledgeJobActive = ingestPending || reindexPending || zoningRunActive
  const progressPercent = Math.max(0, Math.min(100, liveZoningKnowledgeStatus.progress_percent || 0))
  const progressLabel =
    liveZoningKnowledgeStatus.progress_message ||
    (latestRun?.status === 'completed'
      ? 'Ingestion complete.'
      : latestRun?.status === 'failed'
        ? 'Ingestion failed.'
        : 'Waiting for progress updates.')
  const providerKeys = experienceSettings.assistant_provider_keys || {}
  const currentExperienceSettings = experienceState.settings || experienceSettings
  const currentDisclaimer = currentExperienceSettings.assistant_disclaimer_text
  const currentZoningCodeUrl = currentExperienceSettings.zoning_code_url || ''
  const currentProviderKeys = currentExperienceSettings.assistant_provider_keys || providerKeys
  const baselineProviderKeys = baselineSettings?.assistant_provider_keys || {}
  const baselineDisclaimer = baselineSettings?.assistant_disclaimer_text?.trim() || ''
  const currentEmbedSettings = embedState.settings || embedSettings
  const previewOrigin = currentEmbedSettings.allowed_origins[0] || ''
  const previewUrl = `${buildSuperAdminCustomerAssistantEmbedPath(customer.id)}${
    embedState.secret
      ? `?secret=${encodeURIComponent(embedState.secret)}${previewOrigin ? `&origin=${encodeURIComponent(previewOrigin)}` : ''}`
      : previewOrigin
        ? `?origin=${encodeURIComponent(previewOrigin)}`
        : ''
  }`
  const iframeSnippet =
    `<iframe src="${frontendOrigin}/embed#token=TOKEN_FROM_YOUR_SERVER" ` +
    'style="position:fixed;right:20px;bottom:20px;width:420px;height:700px;border:0;z-index:2147483647;" ' +
    'allow="clipboard-read; clipboard-write"></iframe>'
  const sectionDetails: Record<
    AgenticSection,
    {
      title: string
      icon: 'jurisdiction-details' | 'assistant-setup' | 'assistant'
    }
  > = {
    general: { title: 'General', icon: 'jurisdiction-details' },
    'api-keys': { title: 'API Keys', icon: 'assistant-setup' },
    knowledge: { title: 'Knowledge', icon: 'assistant' },
    integrations: { title: 'Integrations', icon: 'assistant-setup' },
  }

  const hasBaselineDefaults =
    Boolean(baselineDisclaimer) ||
    Object.values(baselineProviderKeys).some(Boolean)

  useEffect(() => {
    setLiveZoningKnowledgeStatus(zoningKnowledgeStatus)
  }, [zoningKnowledgeStatus])

  useEffect(() => {
    if (embedState.settings) {
      setCopiedEmbedSnippet(false)
    }
  }, [embedState.settings])

  const copyTextToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text)
  }

  const triggerDownload = (filename: string, content: string, contentType: string) => {
    const blob = new Blob([content], { type: contentType })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  const escapeCsvValue = (value: unknown) => {
    const raw = value == null ? '' : String(value)
    const escaped = raw.replace(/"/g, '""')
    return `"${escaped}"`
  }

  useEffect(() => {
    setFrontendOrigin(window.location.origin)
  }, [])

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
    if (zoningKnowledgeJobActive) {
      intervalId = setInterval(loadStatus, 3000)
    }

    return () => {
      cancelled = true
      if (intervalId) {
        clearInterval(intervalId)
      }
    }
  }, [customer.id, zoningKnowledgeJobActive])

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
      },
      assistant_agent_prompts: {},
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

  const copyEmbedSnippet = async () => {
    await navigator.clipboard.writeText(iframeSnippet)
    setCopiedEmbedSnippet(true)
    window.setTimeout(() => setCopiedEmbedSnippet(false), 2000)
  }

  const renderExperienceHiddenFields = (options: {
    includeZoningCodeUrl?: boolean
    includeDisclaimer?: boolean
    includeProviderKeys?: boolean
  }) => (
    <>
      <input type="hidden" name="organizationId" value={customer.id} />
      {options.includeZoningCodeUrl ? (
        <input type="hidden" name="zoningCodeUrl" value={currentZoningCodeUrl} />
      ) : null}
      {options.includeDisclaimer ? (
        <input type="hidden" name="assistantDisclaimerText" value={currentDisclaimer} />
      ) : null}
      {options.includeProviderKeys
        ? assistantProviderKeyFields.map((provider) => (
            <input
              key={provider.id}
              type="hidden"
              name={provider.fieldName}
              value={currentProviderKeys[provider.id] || ''}
            />
          ))
        : null}
    </>
  )

  return (
    <div className="panel-stack super-admin-panel-stack">
      <section className="super-admin-summary-card">
        <CompactSummaryHeader
          title={sectionDetails[activeSection].title}
          icon={sectionDetails[activeSection].icon}
        />
      </section>

      <section className="super-admin-content-panel">
        {activeSection === 'general' ? (
          <FormSection title="Disclaimer" icon="jurisdiction-details" hideHeader>
            <form onSubmit={(event) => void handleExperienceSubmit(event)} className="admin-form admin-form-compact">
                {hasBaselineDefaults ? (
                  <div className="admin-form-note">
                    This jurisdiction can override the platform baseline. Leave fields blank to inherit the shared setup.
                  </div>
                ) : null}
                {renderExperienceHiddenFields({
                  includeZoningCodeUrl: true,
                  includeProviderKeys: true,
                })}
              <label className="field field-full">
                <span>Disclaimer</span>
                <textarea
                  name="assistantDisclaimerText"
                  rows={5}
                  placeholder={
                    baselineDisclaimer || 'Leave blank to inherit the platform disclaimer.'
                  }
                  defaultValue={currentDisclaimer}
                />
                {baselineDisclaimer ? (
                  <small>Baseline disclaimer: {baselineDisclaimer}</small>
                ) : (
                  <small>Leave blank to inherit the platform disclaimer.</small>
                )}
              </label>
              <div className="admin-form-actions">
                <button className="button button-fit" type="submit" disabled={experiencePending}>
                  {experiencePending ? 'Saving…' : 'Save disclaimer'}
                </button>
              </div>
              {experienceState.error ? (
                <div className="status-banner status-banner-error">{experienceState.error}</div>
              ) : null}
              {experienceState.success ? (
                <div className="status-banner status-banner-success">{experienceState.success}</div>
              ) : null}
            </form>
          </FormSection>
        ) : null}

        {activeSection === 'api-keys' ? (
          <>
            <FormSection title="Gemini Key" icon="assistant-setup" hideHeader>
              <form onSubmit={(event) => void handleExperienceSubmit(event)} className="admin-form admin-form-compact">
                {hasBaselineDefaults ? (
                  <div className="admin-form-note">
                    Jurisdiction API keys override the platform baseline only for this jurisdiction.
                  </div>
                ) : null}
                {renderExperienceHiddenFields({
                  includeZoningCodeUrl: true,
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
                        placeholder={
                          baselineProviderKeys[provider.id]
                            ? `Inherited from platform ${provider.id} key`
                            : `Optional ${provider.id} key for ${customer.name}`
                        }
                        defaultValue={currentProviderKeys[provider.id] || ''}
                      />
                      <small>
                        {baselineProviderKeys[provider.id]
                          ? 'Leave blank to keep the platform key.'
                          : 'Leave blank to use the code default Gemini wiring.'}
                      </small>
                    </label>
                  ))}
                </div>
                <div className="admin-form-actions">
                  <button className="button button-fit" type="submit" disabled={experiencePending}>
                    {experiencePending ? 'Saving…' : 'Save Gemini key'}
                  </button>
                </div>
                {experienceState.error ? <div className="status-banner status-banner-error">{experienceState.error}</div> : null}
                {experienceState.success ? (
                  <div className="status-banner status-banner-success">{experienceState.success}</div>
                ) : null}
              </form>
            </FormSection>
          </>
        ) : null}

        {activeSection === 'knowledge' ? (
          <>
            <FormSection title="Knowledge" icon="assistant" hideHeader>
              <form onSubmit={(event) => void handleExperienceSubmit(event)} className="admin-form admin-form-compact">
                {renderExperienceHiddenFields({
                  includeDisclaimer: true,
                  includeProviderKeys: true,
                })}
                <label className="field field-full">
                  <span>Zoning code URL</span>
                  <input
                    name="zoningCodeUrl"
                    type="url"
                    placeholder="https://library.municode.com/.../zoning"
                    defaultValue={currentZoningCodeUrl}
                  />
                </label>
                <div className="admin-form-actions">
                  <button className="button button-fit" type="submit" disabled={experiencePending}>
                    {experiencePending ? 'Saving…' : 'Save knowledge settings'}
                  </button>
                </div>
                {experienceState.error ? <div className="status-banner status-banner-error">{experienceState.error}</div> : null}
                {experienceState.success ? (
                  <div className="status-banner status-banner-success">{experienceState.success}</div>
                ) : null}
              </form>
            </FormSection>

            <FormSection title="Ingestion status" icon="jurisdiction-details">
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
                  <div>{liveZoningKnowledgeStatus.zoning_code_url || 'Not set.'}</div>
                </div>
                <div>
                  <strong>Embedding model</strong>
                  <div>
                    {liveZoningKnowledgeStatus.embedder_provider} /{' '}
                    {liveZoningKnowledgeStatus.embedder_model_id}
                  </div>
                </div>
                <div>
                  <strong>Embedding dimensions</strong>
                  <div>{liveZoningKnowledgeStatus.embedder_dimensions}</div>
                </div>
              </div>

              {liveZoningKnowledgeStatus.latest_run ? (
                <div className="assistant-setup-run">
                  <strong>{zoningRunActive ? 'Current run' : 'Last run'}</strong>
                  <div>
                    {liveZoningKnowledgeStatus.latest_run.mode} · {liveZoningKnowledgeStatus.latest_run.status}
                  </div>
                </div>
              ) : null}

              {liveZoningKnowledgeStatus.latest_run ? (
                <div className="assistant-setup-progress">
                  <div className="assistant-setup-progress-bar" aria-hidden="true">
                    <span style={{ width: `${progressPercent}%` }} />
                  </div>
                  <div className="assistant-setup-progress-meta">
                    <strong>{progressPercent.toFixed(1)}%</strong>
                    <span>{progressLabel}</span>
                  </div>
                </div>
              ) : null}

              {liveZoningKnowledgeStatus.latest_run ? (
                <div className="assistant-setup-meta assistant-setup-meta-progress">
                  <div>
                    <strong>Pages crawled</strong>
                    <div>{liveZoningKnowledgeStatus.latest_run.pages_crawled}</div>
                  </div>
                  <div>
                    <strong>Documents</strong>
                    <div>{liveZoningKnowledgeStatus.latest_run.documents_extracted}</div>
                  </div>
                  <div>
                    <strong>Sections</strong>
                    <div>{liveZoningKnowledgeStatus.latest_run.sections_extracted}</div>
                  </div>
                  <div>
                    <strong>Chunks</strong>
                    <div>{liveZoningKnowledgeStatus.latest_run.chunks_upserted}</div>
                  </div>
                </div>
              ) : null}

              {latestRun?.status === 'failed' && latestRun.error_message ? (
                <div className="status-banner status-banner-error">{latestRun.error_message}</div>
              ) : null}

              {latestRun?.status === 'completed' ? (
                <div className="status-banner status-banner-success">Ingestion complete.</div>
              ) : zoningRunActive ? (
                <div className="status-banner status-banner-success">
                  {latestRun?.status === 'queued' ? 'Queued.' : 'Running.'}
                </div>
              ) : null}

              <div className="button-row">
                <form action={ingestAction}>
                  <input type="hidden" name="organizationId" value={customer.id} />
                  <button className="button" type="submit" disabled={ingestPending || zoningKnowledgeJobActive}>
                    {ingestPending ? 'Starting…' : zoningKnowledgeJobActive ? 'Ingest Running…' : 'Ingest'}
                  </button>
                </form>

                <form action={reindexAction}>
                  <input type="hidden" name="organizationId" value={customer.id} />
                  <button className="button secondary" type="submit" disabled={reindexPending || zoningKnowledgeJobActive}>
                    {reindexPending ? 'Starting…' : zoningKnowledgeJobActive ? 'Run In Progress…' : 'Reindex'}
                  </button>
                </form>
              </div>

              {ingestState.error ? <div className="status-banner status-banner-error">{ingestState.error}</div> : null}
              {ingestState.success ? <div className="status-banner status-banner-success">{ingestState.success}</div> : null}
              {reindexState.error ? <div className="status-banner status-banner-error">{reindexState.error}</div> : null}
              {reindexState.success ? <div className="status-banner status-banner-success">{reindexState.success}</div> : null}
            </FormSection>
          </>
        ) : null}

        {activeSection === 'integrations' ? (
          <FormSection title="Integrations" icon="assistant-setup" hideHeader>
            <form action={embedAction} className="admin-form admin-form-compact">
              <input type="hidden" name="organizationId" value={customer.id} />
              <div className="admin-form-grid admin-form-grid-2">
                <label className="field field-full">
                  <span>Allowed origins</span>
                  <textarea
                    name="allowedOrigins"
                    rows={4}
                    placeholder="https://partner.example.com"
                    defaultValue={currentEmbedSettings.allowed_origins.join('\n')}
                  />
                </label>
                <label className="field">
                  <span>Widget title</span>
                  <input
                    name="widgetTitle"
                    type="text"
                    placeholder={`Ask ${customer.name}`}
                    defaultValue={currentEmbedSettings.widget_title || ''}
                  />
                </label>
                <label className="field">
                  <span>Launcher label</span>
                  <input
                    name="launcherLabel"
                    type="text"
                    placeholder="Have a question?"
                    defaultValue={currentEmbedSettings.launcher_label || ''}
                  />
                </label>
                <label className="field">
                  <span>Accent color</span>
                  <input
                    name="accentColor"
                    type="text"
                    placeholder="#0b67c2"
                    defaultValue={currentEmbedSettings.accent_color || ''}
                  />
                </label>
                <label className="field field-inline">
                  <span>Enable widget</span>
                  <input name="isActive" type="checkbox" defaultChecked={currentEmbedSettings.is_active} />
                </label>
              </div>
              <div className="admin-form-actions">
                <button className="button button-fit" type="submit" disabled={embedPending}>
                  {embedPending ? 'Saving…' : 'Save embed settings'}
                </button>
              </div>
            </form>

            {embedState.error ? <div className="status-banner status-banner-error">{embedState.error}</div> : null}
            {embedState.success ? <div className="status-banner status-banner-success">{embedState.success}</div> : null}
            {embedState.secret ? (
              <div className="assistant-settings-debug">
                <strong>Secret</strong>
                <pre>{embedState.secret}</pre>
              </div>
            ) : null}
            <div className="assistant-setup-inline-preview">
              <div className="admin-list-heading">Super Admin preview</div>
              <div className="assistant-setup-inline-preview-note">
                Preview the embedded assistant directly inside Super Admin.
              </div>
              <CustomerAssistantEmbedPreview
                backendBase={backendBase}
                customer={{
                  id: customer.id,
                  name: customer.name,
                }}
                embedSettings={currentEmbedSettings}
                initialOrigin={previewOrigin || null}
              />
            </div>
            <div className="assistant-settings-debug">
              <strong>Backend flow</strong>
              <pre>{`POST /api/public/embed/sessions\nHeaders: X-UZone-Embed-Secret: <your embed secret>\nBody: { "client_id": "${customer.id}", "origin": "${previewOrigin || 'https://partner.example.com'}" }`}</pre>
            </div>
            <div className="assistant-settings-debug">
              <strong>Iframe</strong>
              <pre>{iframeSnippet}</pre>
              <div className="button-row admin-form-actions">
                <button type="button" className="button secondary" onClick={() => void copyEmbedSnippet()}>
                  {copiedEmbedSnippet ? 'Copied' : 'Copy iframe snippet'}
                </button>
                <a className="button" href={previewUrl}>
                  Open embed preview
                </a>
              </div>
            </div>
          </FormSection>
        ) : null}

      </section>
    </div>
  )
}
