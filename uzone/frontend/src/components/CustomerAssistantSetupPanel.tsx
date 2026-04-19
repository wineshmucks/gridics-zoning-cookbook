'use client'

import Link from 'next/link'
import { useActionState, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

import {
  type AssistantConversationReviewResponse,
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
import { CompactSummaryHeader, FormSection } from './AdminSurfacePrimitives'
import { CustomerAssistantEmbedPreview } from './CustomerAssistantEmbedPreview'
import {
  assistantModelProviderOptions,
  assistantProviderKeyFields,
  describeAssistantModelTarget,
  hasAssistantModelTarget,
  modelTargetFields,
} from './agenticSetupConfig'
import { CUSTOMER_ZONING_ASSISTANT_TARGET_ID } from './assistantTargetIds'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

type AgenticSection =
  | 'general'
  | 'api-keys'
  | 'models'
  | 'agents'
  | 'knowledge'
  | 'integrations'
  | 'review'

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
  conversationReview,
}: {
  customer: SelectedCustomer
  experienceSettings: CustomerExperienceSettings
  embedSettings: CustomerEmbedSettings
  zoningKnowledgeStatus: CustomerZoningKnowledgeStatus
  baselineSettings?: CustomerExperienceSettings | null
  conversationReview: AssistantConversationReviewResponse
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
  const [reviewPage, setReviewPage] = useState(conversationReview.pagination.page || 1)
  const [reviewSearchInput, setReviewSearchInput] = useState(conversationReview.pagination.search || '')
  const [reviewSearch, setReviewSearch] = useState(conversationReview.pagination.search || '')
  const [reviewConversationId, setReviewConversationId] = useState(
    conversationReview.pagination.conversation_id || searchParams.get('conversation_id') || '',
  )
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [reviewActionError, setReviewActionError] = useState<string | null>(null)
  const [liveConversationReview, setLiveConversationReview] =
    useState<AssistantConversationReviewResponse>(conversationReview)
  const backendBase =
    process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || ''
  const sectionParam = searchParams.get('section')
  const activeSection: AgenticSection =
    sectionParam === 'llm'
        ? 'agents'
    : sectionParam === 'telemetry'
      ? 'review'
    : sectionParam === 'api-keys' ||
        sectionParam === 'models' ||
          sectionParam === 'agents' ||
          sectionParam === 'knowledge' ||
          sectionParam === 'integrations' ||
          sectionParam === 'review'
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
  const modelTargets = experienceSettings.assistant_model_targets || {}
  const currentExperienceSettings = experienceState.settings || experienceSettings
  const currentDisclaimer = currentExperienceSettings.assistant_disclaimer_text
  const currentZoningCodeUrl = currentExperienceSettings.zoning_code_url || ''
  const currentProviderKeys = currentExperienceSettings.assistant_provider_keys || providerKeys
  const currentAgentPrompts = currentExperienceSettings.assistant_agent_prompts || {}
  const currentModelTargets = currentExperienceSettings.assistant_model_targets || modelTargets
  const codeDefaultModelTargets = currentExperienceSettings.code_default_assistant_model_targets || {}
  const baselineProviderKeys = baselineSettings?.assistant_provider_keys || {}
  const baselineModelTargets = baselineSettings?.assistant_model_targets || {}
  const baselineDisclaimer = baselineSettings?.assistant_disclaimer_text?.trim() || ''
  const currentEmbedSettings = embedState.settings || embedSettings
  const reviewPagination = liveConversationReview.pagination
  const reviewedConversations = useMemo(() => {
    const parseTimestamp = (value: string | null | undefined) => {
      if (!value) {
        return null
      }
      const timestamp = Date.parse(value)
      return Number.isNaN(timestamp) ? null : timestamp
    }

    const formatDuration = (durationMs: number | null) => {
      if (durationMs == null || durationMs < 0) {
        return '—'
      }

      const totalSeconds = Math.round(durationMs / 1000)
      const hours = Math.floor(totalSeconds / 3600)
      const minutes = Math.floor((totalSeconds % 3600) / 60)
      const seconds = totalSeconds % 60

      if (hours > 0) {
        return `${hours}h ${minutes}m ${seconds}s`
      }
      if (minutes > 0) {
        return `${minutes}m ${seconds}s`
      }
      return `${seconds}s`
    }

    return [...liveConversationReview.conversations]
      .map((conversation) => {
        const timestamps = [
          ...conversation.turns.map((turn) => parseTimestamp(turn.created_at)),
          ...conversation.runs.map((run) => parseTimestamp(run.created_at)),
          ...conversation.feedback.map((feedback) => parseTimestamp(feedback.created_at)),
        ].filter((value): value is number => value != null)

        const startMs = timestamps.length > 0 ? Math.min(...timestamps) : parseTimestamp(conversation.latest_at)
        const endMs = timestamps.length > 0 ? Math.max(...timestamps) : parseTimestamp(conversation.latest_at)
        const sortMs = startMs ?? endMs ?? 0

        return {
          ...conversation,
          sortMs,
          startedAtLabel: startMs != null ? new Date(startMs).toLocaleString() : '—',
          durationLabel:
            startMs != null && endMs != null ? formatDuration(Math.max(0, endMs - startMs)) : '—',
        }
      })
      .sort((left, right) => right.sortMs - left.sortMs)
  }, [liveConversationReview.conversations])
  const reviewPageConversationCount = reviewedConversations.length

  const previewOrigin = currentEmbedSettings.allowed_origins[0] || ''
  const previewUrl = `/super-admin/customers/${customer.id}/assistant-embed${
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
    models: { title: 'Models', icon: 'assistant' },
    agents: { title: 'Agents', icon: 'assistant' },
    knowledge: { title: 'Knowledge', icon: 'assistant' },
    review: { title: 'Review', icon: 'assistant' },
    integrations: { title: 'Integrations', icon: 'assistant-setup' },
  }

  const hasBaselineDefaults =
    Boolean(baselineDisclaimer) ||
    Object.values(baselineProviderKeys).some(Boolean) ||
    Object.keys(baselineModelTargets).length > 0

  useEffect(() => {
    setLiveZoningKnowledgeStatus(zoningKnowledgeStatus)
  }, [zoningKnowledgeStatus])

  useEffect(() => {
    if (embedState.settings) {
      setCopiedEmbedSnippet(false)
    }
  }, [embedState.settings])

  useEffect(() => {
    setReviewPage(conversationReview.pagination.page || 1)
    setReviewSearchInput(conversationReview.pagination.search || '')
    setReviewSearch(conversationReview.pagination.search || '')
    setReviewConversationId(conversationReview.pagination.conversation_id || searchParams.get('conversation_id') || '')
  }, [conversationReview.pagination.page, conversationReview.pagination.search, conversationReview.pagination.conversation_id, searchParams])

  useEffect(() => {
    setLiveConversationReview(conversationReview)
  }, [conversationReview, customer.id])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setReviewSearch(reviewSearchInput.trim())
    }, 250)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [reviewSearchInput])

  useEffect(() => {
    let cancelled = false

    const loadConversationReview = async () => {
      setReviewLoading(true)
      setReviewError(null)

      try {
        const searchParams = new URLSearchParams()
        if (reviewPage > 1) {
          searchParams.set('page', String(reviewPage))
        }
        if (reviewSearch.trim()) {
          searchParams.set('search', reviewSearch.trim())
        }
        if (reviewConversationId.trim()) {
          searchParams.set('conversation_id', reviewConversationId.trim())
        }

        const queryString = searchParams.toString()
        const response = await fetch(
          buildApiUrl(
            `/api/admin/clients/${customer.id}/assistant-conversations${queryString ? `?${queryString}` : ''}`,
          ),
          {
            cache: 'no-store',
            credentials: 'include',
          },
        )

        if (!response.ok) {
          throw new Error('Unable to load conversation review.')
        }

        const payload = (await response.json()) as AssistantConversationReviewResponse
        if (!cancelled) {
          setLiveConversationReview(payload)
        }
      } catch (error) {
        if (!cancelled) {
          setReviewError(
            error instanceof Error && error.message ? error.message : 'Unable to load conversation review.',
          )
        }
      } finally {
        if (!cancelled) {
          setReviewLoading(false)
        }
      }
    }

    loadConversationReview()

    return () => {
      cancelled = true
    }
  }, [customer.id, reviewConversationId, reviewPage, reviewSearch])

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

  const buildConversationCsv = (conversation: AssistantConversationReviewResponse['conversations'][number]) => {
    const headers = [
      'row_type',
      'timestamp',
      'conversation_id',
      'entity_id',
      'agent_id',
      'message_id',
      'run_id',
      'intent_type',
      'jurisdiction_status',
      'policy_decision',
      'reason_code',
      'model_id',
      'input_tokens',
      'output_tokens',
      'total_tokens',
      'cost',
      'feedback_value',
      'message_excerpt',
      'payload_json',
    ]
    const rows: unknown[][] = [headers]
    for (const turn of conversation.turns) {
      rows.push([
        'turn',
        turn.created_at,
        conversation.conversation_id,
        turn.id,
        turn.agent_id || '',
        turn.message_id || '',
        turn.run_id || '',
        turn.intent_type || '',
        turn.jurisdiction_status || '',
        turn.policy_decision || '',
        turn.reason_code || '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        JSON.stringify(turn.payload_json || {}),
      ])
    }
    for (const run of conversation.runs) {
      rows.push([
        'run',
        run.created_at,
        conversation.conversation_id,
        run.id,
        run.agent_id || '',
        run.message_id || '',
        run.run_id || '',
        '',
        '',
        '',
        '',
        run.model_id || run.model_name || '',
        run.input_tokens,
        run.output_tokens,
        run.total_tokens,
        run.cost ?? '',
        '',
        '',
        JSON.stringify(run.metrics_json || {}),
      ])
    }
    for (const feedback of conversation.feedback) {
      rows.push([
        'feedback',
        feedback.created_at,
        conversation.conversation_id,
        feedback.id,
        feedback.agent_id || '',
        feedback.message_id || '',
        feedback.run_id || '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        feedback.feedback_value,
        feedback.message_excerpt || '',
        JSON.stringify(feedback.metadata_json || {}),
      ])
    }
    return rows.map((row) => row.map(escapeCsvValue).join(',')).join('\n')
  }

  const handleCopyConversationJson = async (conversation: AssistantConversationReviewResponse['conversations'][number]) => {
    try {
      setReviewActionError(null)
      await copyTextToClipboard(JSON.stringify(conversation, null, 2))
    } catch {
      setReviewActionError('Unable to copy the conversation JSON. Your browser may be blocking clipboard access.')
    }
  }

  const handleExportConversationJson = (conversation: AssistantConversationReviewResponse['conversations'][number]) => {
    triggerDownload(
      `${conversation.conversation_id}.json`,
      `${JSON.stringify(conversation, null, 2)}\n`,
      'application/json;charset=utf-8',
    )
  }

  const handleExportConversationCsv = (conversation: AssistantConversationReviewResponse['conversations'][number]) => {
    triggerDownload(
      `${conversation.conversation_id}.csv`,
      `${buildConversationCsv(conversation)}\n`,
      'text/csv;charset=utf-8',
    )
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
        openrouter: String(formData.get('providerKeyOpenrouter') || '').trim() || null,
        openai: String(formData.get('providerKeyOpenai') || '').trim() || null,
        groq: String(formData.get('providerKeyGroq') || '').trim() || null,
      },
      assistant_model_targets: {
        [CUSTOMER_ZONING_ASSISTANT_TARGET_ID]: {
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
        [CUSTOMER_ZONING_ASSISTANT_TARGET_ID]:
          currentAgentPrompts[CUSTOMER_ZONING_ASSISTANT_TARGET_ID] || null,
        'parcel-data-agent': currentAgentPrompts['parcel-data-agent'] || null,
        'code-researcher-agent': currentAgentPrompts['code-researcher-agent'] || null,
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

  const copyEmbedSnippet = async () => {
    await navigator.clipboard.writeText(iframeSnippet)
    setCopiedEmbedSnippet(true)
    window.setTimeout(() => setCopiedEmbedSnippet(false), 2000)
  }

  const renderExperienceHiddenFields = (options: {
    includeZoningCodeUrl?: boolean
    includeDisclaimer?: boolean
    includeProviderKeys?: boolean
    includeModelTargets?: boolean
    includeAgentPrompts?: boolean
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
      {options.includeModelTargets
        ? modelTargetFields.map((target) => {
            const targetSettings = currentModelTargets[target.id] || {
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
        ? Object.entries(currentAgentPrompts).map(([targetId, prompt]) => (
            <input
              key={targetId}
              type="hidden"
              name={(() => {
                switch (targetId) {
                  case CUSTOMER_ZONING_ASSISTANT_TARGET_ID:
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
                  includeModelTargets: true,
                  includeAgentPrompts: true,
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
                  includeModelTargets: true,
                  includeAgentPrompts: true,
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

        {activeSection === 'models' ? (
          <>
            <FormSection title="Models" icon="assistant" hideHeader>
              <form onSubmit={(event) => void handleExperienceSubmit(event)} className="admin-form admin-form-compact">
                {hasBaselineDefaults ? (
                  <div className="admin-form-note">
                    Jurisdiction model settings override the platform baseline only for this jurisdiction.
                  </div>
                ) : null}
                {renderExperienceHiddenFields({
                  includeZoningCodeUrl: true,
                  includeDisclaimer: true,
                  includeProviderKeys: true,
                  includeAgentPrompts: true,
                })}
                <div className="admin-form-grid admin-form-grid-single">
                  {modelTargetFields.map((target) => {
                    const targetSettings = currentModelTargets[target.id] || {
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
                              {assistantModelProviderOptions.map((option) => (
                                <option key={option.value || 'default'} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                            <small>
                              {baselineModelTargets[target.id]?.provider
                                ? `Platform default: ${baselineModelTargets[target.id]?.provider || 'Not set'}`
                                : 'Leave blank to use the code default.'}
                            </small>
                          </label>
                          <label className="field">
                            <span>Model ID</span>
                            <input
                              name={target.modelFieldName}
                              type="text"
                              placeholder={
                                baselineModelTargets[target.id]?.model_id || 'Use code default'
                              }
                              defaultValue={targetSettings.model_id || ''}
                            />
                            <small>
                              {baselineModelTargets[target.id]?.model_id
                                ? `Platform default: ${baselineModelTargets[target.id]?.model_id}`
                                : 'Leave blank to use the code default.'}
                            </small>
                          </label>
                          <label className="field">
                            <span>Base URL</span>
                            <input
                              name={target.baseUrlFieldName}
                              type="text"
                              placeholder={
                                baselineModelTargets[target.id]?.base_url || 'Optional custom base URL'
                              }
                              defaultValue={targetSettings.base_url || ''}
                            />
                            <small>
                              {baselineModelTargets[target.id]?.base_url
                                ? `Platform default: ${baselineModelTargets[target.id]?.base_url}`
                                : 'Leave blank to keep the inherited or code default base URL.'}
                            </small>
                          </label>
                        </div>
                      </div>
                    )
                  })}
                </div>
                <div className="admin-form-actions">
                  <button className="button button-fit" type="submit" disabled={experiencePending}>
                    {experiencePending ? 'Saving…' : 'Save models'}
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

        {activeSection === 'agents' ? (
          <>
            <FormSection title="Agents" icon="assistant" hideHeader>
              <form onSubmit={(event) => void handleExperienceSubmit(event)} className="admin-form admin-form-compact">
                {hasBaselineDefaults ? (
                  <div className="admin-form-note">
                    Jurisdiction values override the platform baseline only for this jurisdiction.
                  </div>
                ) : null}
                {renderExperienceHiddenFields({
                  includeZoningCodeUrl: true,
                  includeDisclaimer: true,
                  includeProviderKeys: true,
                  includeModelTargets: true,
                })}
                <div className="admin-form-note">
                  Agent prompt editing is temporarily disabled. This jurisdiction currently uses the
                  checked-in assistant instructions from the codebase.
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
                  includeModelTargets: true,
                  includeAgentPrompts: true,
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

        {activeSection === 'review' ? (
          <FormSection title="Conversation Review" icon="assistant" hideHeader>
            <div className="admin-form-note">
              Review raw assistant turn events, run metrics, and feedback in one place. Conversations are sorted
              by start time descending, and each row shows when the conversation happened plus the total captured
              elapsed time.
            </div>

            <div className="assistant-setup-stats">
              <div className="assistant-setup-stat">
                <span>Conversations</span>
                <strong>{liveConversationReview.summary.total_conversations}</strong>
              </div>
              <div className="assistant-setup-stat">
                <span>Turns</span>
                <strong>{liveConversationReview.summary.total_turns.toLocaleString()}</strong>
              </div>
              <div className="assistant-setup-stat">
                <span>Runs</span>
                <strong>{liveConversationReview.summary.total_runs.toLocaleString()}</strong>
              </div>
              <div className="assistant-setup-stat">
                <span>Feedback</span>
                <strong>{liveConversationReview.summary.total_feedback.toLocaleString()}</strong>
              </div>
            </div>

            <div className="assistant-telemetry-controls">
              <label className="field">
                <span>Search conversations</span>
                <input
                  type="search"
                  value={reviewSearchInput}
                  placeholder="Conversation, message, run, agent, reason, model, or feedback"
                  onChange={(event) => {
                    setReviewSearchInput(event.target.value)
                    setReviewPage(1)
                  }}
                />
              </label>
              <div className="assistant-telemetry-control-row">
                <button
                  type="button"
                  className="button secondary"
                  disabled={reviewPage <= 1 || reviewLoading}
                  onClick={() => setReviewPage((current) => Math.max(1, current - 1))}
                >
                  Previous
                </button>
                <span className="assistant-telemetry-page-meta">
                  Page {reviewPagination.page || 1} of {reviewPagination.total_pages || 1}
                </span>
                <button
                  type="button"
                  className="button secondary"
                  disabled={!reviewPagination.has_next || reviewLoading}
                  onClick={() => setReviewPage((current) => current + 1)}
                >
                  Next
                </button>
              </div>
            </div>

            <div className="assistant-telemetry-page-summary">
              {reviewLoading ? (
                <span>Loading conversation review…</span>
              ) : (
                <span>
                  Showing {reviewPageConversationCount} conversation
                  {reviewPageConversationCount === 1 ? '' : 's'}
                  {' '}
                  on this page
                  {reviewPagination.search ? (
                    <>
                      {' '}
                      for “{reviewPagination.search}”
                    </>
                  ) : null}
                </span>
              )}
              {reviewError ? <span className="status-banner status-banner-error">{reviewError}</span> : null}
              {reviewActionError ? <span className="status-banner status-banner-error">{reviewActionError}</span> : null}
            </div>

            {reviewConversationId ? (
              <div className="admin-form-note">
                Viewing conversation <strong>{reviewConversationId}</strong>{' '}
                <Link
                  href={`/super-admin/customers/${customer.id}/assistant-setup?section=review`}
                  style={{ marginLeft: 8 }}
                >
                  Clear filter
                </Link>
              </div>
            ) : null}

            {reviewedConversations.length > 0 ? (
              <div className="assistant-telemetry-group-list">
                {reviewedConversations.map((conversation) => (
                  <details
                    key={conversation.conversation_id}
                    className="card assistant-telemetry-group"
                    open={reviewedConversations.length === 1}
                  >
                    <summary className="assistant-telemetry-group-summary">
                      <span className="assistant-telemetry-group-title">{conversation.conversation_id}</span>
                      <span className="assistant-telemetry-group-chip">Conversation</span>
                      <span className="assistant-telemetry-group-meta">
                        {conversation.startedAtLabel}
                        {' · '}
                        {conversation.durationLabel}
                        {' · '}
                        {conversation.turn_count} turn{conversation.turn_count === 1 ? '' : 's'}
                        {' · '}
                        {conversation.run_count} run{conversation.run_count === 1 ? '' : 's'}
                        {' · '}
                        {conversation.feedback_count} feedback
                        {' · '}
                        In {conversation.input_tokens.toLocaleString()}
                        {' · '}
                        Out {conversation.output_tokens.toLocaleString()}
                        {' · '}
                        Cost{' '}
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(
                          conversation.cost,
                        )}
                      </span>
                    </summary>
                    <div className="assistant-telemetry-group-body">
                      <div className="assistant-telemetry-control-row" style={{ justifyContent: 'flex-start' }}>
                        <button
                          type="button"
                          className="button secondary"
                          onClick={() => void handleCopyConversationJson(conversation)}
                        >
                          Copy Compact JSON
                        </button>
                        <button
                          type="button"
                          className="button secondary"
                          onClick={() => handleExportConversationJson(conversation)}
                        >
                          Export Compact JSON
                        </button>
                        <button
                          type="button"
                          className="button secondary"
                          onClick={() => handleExportConversationCsv(conversation)}
                        >
                          Export CSV
                        </button>
                        {conversation.conversation_id ? (
                          <Link
                            className="button secondary"
                            href={`/super-admin/customers/${customer.id}/assistant-setup?section=review&conversation_id=${encodeURIComponent(
                              conversation.conversation_id,
                            )}`}
                          >
                            Permalink
                          </Link>
                        ) : null}
                      </div>
                      <div className="assistant-settings-debug">
                        <strong>Turns</strong>
                        {conversation.turns.length > 0 ? (
                          <table className="table super-admin-table">
                            <thead>
                              <tr>
                                <th>Time</th>
                                <th>Agent</th>
                                <th>Intent</th>
                                <th>Decision</th>
                                <th>Reason</th>
                                <th>Message / Run</th>
                                <th>Payload</th>
                              </tr>
                            </thead>
                            <tbody>
                              {conversation.turns.map((turn) => (
                                <tr key={turn.id}>
                                  <td>{turn.created_at ? new Date(turn.created_at).toLocaleString() : '—'}</td>
                                  <td>{turn.agent_id || 'Unknown'}</td>
                                  <td>{turn.intent_type || '—'}</td>
                                  <td>{turn.policy_decision || turn.jurisdiction_status || '—'}</td>
                                  <td>{turn.reason_code || '—'}</td>
                                  <td>
                                    <div>{turn.message_id || '—'}</div>
                                    <small style={{ color: 'var(--muted)' }}>{turn.run_id || 'No run id'}</small>
                                  </td>
                                  <td>
                                    <details>
                                      <summary>View payload</summary>
                                      <pre style={{ margin: '10px 0 0', whiteSpace: 'pre-wrap' }}>
                                        {JSON.stringify(turn.payload_json || {}, null, 2)}
                                      </pre>
                                    </details>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <div className="admin-form-note">No turn events were recorded for this conversation.</div>
                        )}
                      </div>

                      <div className="assistant-settings-debug">
                        <strong>Telemetry</strong>
                        {conversation.runs.length > 0 ? (
                          <table className="table super-admin-table">
                            <thead>
                              <tr>
                                <th>Time</th>
                                <th>Model</th>
                                <th>Agent</th>
                                <th className="is-numeric">In</th>
                                <th className="is-numeric">Out</th>
                                <th className="is-numeric">Cost</th>
                                <th>Duration</th>
                              </tr>
                            </thead>
                            <tbody>
                              {conversation.runs.map((run) => (
                                <tr key={run.id}>
                                  <td>{run.created_at ? new Date(run.created_at).toLocaleString() : '—'}</td>
                                  <td>
                                    <div>{run.model_id || run.model_name || 'Unknown'}</div>
                                    <small style={{ color: 'var(--muted)' }}>
                                      {run.model_provider ? `${run.model_provider}${run.model_name ? ` · ${run.model_name}` : ''}` : 'Model not captured'}
                                    </small>
                                  </td>
                                  <td>
                                    <div>{run.agent_id || 'Unknown'}</div>
                                    <small style={{ color: 'var(--muted)' }}>
                                      {run.run_id || run.session_id || run.conversation_id || 'Conversation not captured'}
                                    </small>
                                  </td>
                                  <td className="is-numeric">{run.input_tokens.toLocaleString()}</td>
                                  <td className="is-numeric">{run.output_tokens.toLocaleString()}</td>
                                  <td className="is-numeric">
                                    {run.cost == null
                                      ? '—'
                                      : new Intl.NumberFormat('en-US', {
                                          style: 'currency',
                                          currency: 'USD',
                                        }).format(run.cost)}
                                  </td>
                                  <td>{run.duration_seconds == null ? '—' : `${run.duration_seconds.toFixed(1)}s`}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <div className="admin-form-note">No telemetry was recorded for this conversation.</div>
                        )}
                      </div>

                      <div className="assistant-settings-debug">
                        <strong>Feedback</strong>
                        {conversation.feedback.length > 0 ? (
                          <table className="table super-admin-table">
                            <thead>
                              <tr>
                                <th>Time</th>
                                <th>Value</th>
                                <th>Message</th>
                                <th>Excerpt</th>
                              </tr>
                            </thead>
                            <tbody>
                              {conversation.feedback.map((feedback) => (
                                <tr key={feedback.id}>
                                  <td>{feedback.created_at ? new Date(feedback.created_at).toLocaleString() : '—'}</td>
                                  <td>{feedback.feedback_value}</td>
                                  <td>{feedback.message_id}</td>
                                  <td>
                                    <div>{feedback.message_excerpt || '—'}</div>
                                    {feedback.run_id ? (
                                      <small style={{ color: 'var(--muted)' }}>Run {feedback.run_id}</small>
                                    ) : null}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <div className="admin-form-note">No feedback has been recorded for this conversation.</div>
                        )}
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            ) : (
              <div className="admin-form-note">
                {reviewLoading
                  ? 'Loading conversation review…'
                  : reviewPagination.search
                    ? 'No conversations matched your search.'
                    : 'No assistant conversations have been recorded yet.'}
              </div>
            )}
          </FormSection>
        ) : null}
      </section>
    </div>
  )
}
