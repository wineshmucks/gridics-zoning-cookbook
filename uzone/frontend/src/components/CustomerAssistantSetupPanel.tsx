'use client'

import { useActionState, useEffect, useState } from 'react'

import {
  ingestCustomerZoningKnowledgeAction,
  reindexCustomerZoningKnowledgeAction,
  saveCustomerExperienceSettingsAction,
  type CustomerExperienceSettings,
  type CustomerExperienceSettingsState,
  type CustomerZoningKnowledgeMutationState,
  type CustomerZoningKnowledgeStatus,
} from '../app/admin/actions'

const backendApiBase = process.env.NEXT_PUBLIC_UZONE_API_BASE || 'http://localhost:8000'

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

const initialExperienceSettingsState: CustomerExperienceSettingsState = {
  error: null,
  success: null,
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
  const [liveZoningKnowledgeStatus, setLiveZoningKnowledgeStatus] =
    useState<CustomerZoningKnowledgeStatus>(zoningKnowledgeStatus)
  const [experienceState, experienceAction, experiencePending] = useActionState(
    saveCustomerExperienceSettingsAction,
    initialExperienceSettingsState,
  )
  const [ingestState, ingestAction, ingestPending] = useActionState(
    ingestCustomerZoningKnowledgeAction,
    initialZoningKnowledgeMutationState,
  )
  const [reindexState, reindexAction, reindexPending] = useActionState(
    reindexCustomerZoningKnowledgeAction,
    initialZoningKnowledgeMutationState,
  )
  const latestRun = liveZoningKnowledgeStatus.latest_run
  const zoningRunActive = latestRun?.status === 'queued' || latestRun?.status === 'running'

  useEffect(() => {
    setLiveZoningKnowledgeStatus(zoningKnowledgeStatus)
  }, [zoningKnowledgeStatus])

  useEffect(() => {
    let cancelled = false
    let intervalId: ReturnType<typeof setInterval> | null = null

    const loadStatus = async () => {
      try {
        const response = await fetch(
          `${backendApiBase}/api/admin/clients/${customer.id}/zoning-knowledge`,
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

  return (
    <div className="panel-stack">
      <div className="admin-list">
        <div className="admin-list-heading">Assistant setup</div>
        <form action={experienceAction} className="admin-form">
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
          <button className="button button-fit" type="submit" disabled={experiencePending}>
            {experiencePending ? 'Saving…' : 'Save Setup'}
          </button>
          {experienceState.error ? (
            <div className="status-banner status-banner-error">{experienceState.error}</div>
          ) : null}
          {experienceState.success ? (
            <div className="status-banner status-banner-success">{experienceState.success}</div>
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
