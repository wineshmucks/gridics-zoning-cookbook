'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useActionState, useEffect, useState } from 'react'

import { AgentChatPanel } from './AgentChatPanel'
import {
  deleteCustomerAction,
  ingestCustomerZoningKnowledgeAction,
  inviteClientAdminAction,
  queryCustomerZoningKnowledgeAction,
  reindexCustomerZoningKnowledgeAction,
  removeClientAdminAction,
  saveCustomerExperienceSettingsAction,
  setCustomerInactiveAction,
  type CustomerExperienceSettings,
  type CustomerExperienceSettingsState,
  type CustomerZoningKnowledgeMutationState,
  type CustomerZoningKnowledgeQueryState,
  type CustomerZoningKnowledgeStatus,
  type CustomerMutationState,
  type InviteAdminState,
  type RemoveAdminState,
} from '../app/admin/actions'

const backendApiBase = process.env.NEXT_PUBLIC_UZONE_API_BASE || 'http://localhost:8000'

type AdminMember = {
  userId: string
  identifier: string
  name: string
  role: string
}

type PendingInvite = {
  id: string
  emailAddress: string
  role: string
  status: string
}

type SelectedCustomer = {
  id: string
  name: string
  slug: string | null
  customerId: string | null
}

type SuperAdminSectionId = 'general' | 'admin-users' | 'customer-assistant'

const initialInviteState: InviteAdminState = {
  error: null,
  success: null,
}

const initialRemoveState: RemoveAdminState = {
  error: null,
  success: null,
}

const initialCustomerMutationState: CustomerMutationState = {
  error: null,
  success: null,
}

const initialExperienceSettingsState: CustomerExperienceSettingsState = {
  error: null,
  success: null,
}

const initialZoningKnowledgeMutationState: CustomerZoningKnowledgeMutationState = {
  error: null,
  success: null,
}

const initialZoningKnowledgeQueryState: CustomerZoningKnowledgeQueryState = {
  error: null,
  success: null,
  results: [],
}

const superAdminSections: Array<{
  id: SuperAdminSectionId
  label: string
  description: string
}> = [
  {
    id: 'general',
    label: 'General',
    description: 'Overview and customer controls.',
  },
  {
    id: 'admin-users',
    label: 'Admin Users',
    description: 'Invites, assignments, and pending access.',
  },
  {
    id: 'customer-assistant',
    label: 'Assistant',
    description: 'Assistant settings and zoning knowledge.',
  },
]

export function SuperAdminCustomerManageClient({
  customer,
  adminMembers,
  pendingInvites,
  experienceSettings,
  zoningKnowledgeStatus,
}: {
  customer: SelectedCustomer
  adminMembers: AdminMember[]
  pendingInvites: PendingInvite[]
  experienceSettings: CustomerExperienceSettings
  zoningKnowledgeStatus: CustomerZoningKnowledgeStatus
}) {
  const [activeSection, setActiveSection] = useState<SuperAdminSectionId>('general')
  const [liveZoningKnowledgeStatus, setLiveZoningKnowledgeStatus] =
    useState<CustomerZoningKnowledgeStatus>(zoningKnowledgeStatus)
  const [inviteState, inviteAction, invitePending] = useActionState(
    inviteClientAdminAction,
    initialInviteState,
  )
  const [removeState, removeAction, removePending] = useActionState(
    removeClientAdminAction,
    initialRemoveState,
  )
  const [inactiveState, inactiveAction, inactivePending] = useActionState(
    setCustomerInactiveAction,
    initialCustomerMutationState,
  )
  const [deleteState, deleteAction, deletePending] = useActionState(
    deleteCustomerAction,
    initialCustomerMutationState,
  )
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
  const [queryState, queryAction, queryPending] = useActionState(
    queryCustomerZoningKnowledgeAction,
    initialZoningKnowledgeQueryState,
  )
  const router = useRouter()
  const latestRun = liveZoningKnowledgeStatus.latest_run
  const zoningRunActive = latestRun?.status === 'queued' || latestRun?.status === 'running'

  useEffect(() => {
    if (
      !inviteState.success &&
      !removeState.success &&
      !inactiveState.success &&
      !experienceState.success &&
      !ingestState.success &&
      !reindexState.success
    ) {
      return
    }

    router.refresh()
  }, [
    experienceState.success,
    inactiveState.success,
    ingestState.success,
    inviteState.success,
    reindexState.success,
    removeState.success,
    router,
  ])

  useEffect(() => {
    if (!deleteState.success) {
      return
    }

    router.push('/super-admin')
    router.refresh()
  }, [deleteState.success, router])

  useEffect(() => {
    setLiveZoningKnowledgeStatus(zoningKnowledgeStatus)
  }, [zoningKnowledgeStatus])

  useEffect(() => {
    if (activeSection !== 'customer-assistant') {
      return
    }

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
  }, [activeSection, customer.id, zoningRunActive])

  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="super-admin-toolbar">
        <Link href="/super-admin" className="button secondary">
          Back to Customers
        </Link>
      </div>

      <div className="super-admin-layout">
        <aside className="super-admin-sidebar">
          <div className="admin-list super-admin-customer-card">
            <div className="admin-list-heading">{customer.name}</div>
            <div className="super-admin-meta">
              {customer.customerId || 'Organization ID unavailable'}
            </div>
            <div className="super-admin-meta">{customer.slug || 'no-slug'}</div>
          </div>

          <nav className="super-admin-nav" aria-label="Customer management sections">
            {superAdminSections.map((section) => {
              const isActive = activeSection === section.id

              return (
                <button
                  key={section.id}
                  type="button"
                  className={`super-admin-nav-item${isActive ? ' is-active' : ''}`}
                  onClick={() => setActiveSection(section.id)}
                  aria-pressed={isActive}
                >
                  <span className="super-admin-nav-label">{section.label}</span>
                  <span className="super-admin-nav-description">{section.description}</span>
                </button>
              )
            })}
          </nav>
        </aside>

        <div className="super-admin-content">
          {activeSection === 'general' ? (
            <div className="panel-stack">
              <div className="admin-list">
                <div className="admin-list-heading">General</div>
                <div style={{ color: 'var(--muted)' }}>
                  Customer record details and lifecycle controls for {customer.name}.
                </div>
                <dl className="detail-list">
                  <div>
                    <dt>Customer name</dt>
                    <dd>{customer.name}</dd>
                  </div>
                  <div>
                    <dt>Organization ID</dt>
                    <dd>{customer.customerId || 'Organization ID unavailable'}</dd>
                  </div>
                  <div>
                    <dt>Slug</dt>
                    <dd>{customer.slug || 'No slug configured'}</dd>
                  </div>
                  <div>
                    <dt>Admin users</dt>
                    <dd>{adminMembers.length}</dd>
                  </div>
                  <div>
                    <dt>Pending invites</dt>
                    <dd>{pendingInvites.length}</dd>
                  </div>
                </dl>
              </div>

              <div className="admin-list">
                <div className="admin-list-heading">Customer controls</div>
                <div className="panel-stack">
                  <form action={inactiveAction} className="admin-action-row">
                    <input type="hidden" name="organizationId" value={customer.id} />
                    <input type="hidden" name="customerName" value={customer.name} />
                    <div>
                      <div style={{ fontWeight: 700 }}>Set customer inactive</div>
                      <div style={{ color: 'var(--muted)' }}>
                        Disable tenant resolution for this customer without removing the Clerk organization.
                      </div>
                    </div>
                    <button className="button secondary" type="submit" disabled={inactivePending}>
                      {inactivePending ? 'Updating…' : 'Set Inactive'}
                    </button>
                  </form>

                  <form action={deleteAction} className="admin-action-row">
                    <input type="hidden" name="organizationId" value={customer.id} />
                    <input type="hidden" name="customerName" value={customer.name} />
                    <div>
                      <div style={{ fontWeight: 700 }}>Delete customer</div>
                      <div style={{ color: 'var(--muted)' }}>
                        Remove the Clerk organization and delete its tenant mapping.
                      </div>
                    </div>
                    <button className="button secondary" type="submit" disabled={deletePending}>
                      {deletePending ? 'Deleting…' : 'Delete'}
                    </button>
                  </form>
                </div>
                {inactiveState.error ? (
                  <div className="status-banner status-banner-error">{inactiveState.error}</div>
                ) : null}
                {inactiveState.success ? (
                  <div className="status-banner status-banner-success">{inactiveState.success}</div>
                ) : null}
                {deleteState.error ? (
                  <div className="status-banner status-banner-error">{deleteState.error}</div>
                ) : null}
                {deleteState.success ? (
                  <div className="status-banner status-banner-success">{deleteState.success}</div>
                ) : null}
              </div>
            </div>
          ) : null}

          {activeSection === 'admin-users' ? (
            <div className="panel-stack">
              <div className="admin-list">
                <div className="admin-list-heading">Invite admin user</div>
                <form action={inviteAction} className="admin-form">
                  <input type="hidden" name="organizationId" value={customer.id} />
                  <label className="field">
                    <span>Email address</span>
                    <input
                      name="emailAddress"
                      type="email"
                      placeholder="planning-admin@example.gov"
                      required
                    />
                  </label>
                  <button className="button" type="submit" disabled={invitePending}>
                    {invitePending ? 'Sending…' : 'Send Admin Invite'}
                  </button>
                  {inviteState.error ? (
                    <div className="status-banner status-banner-error">{inviteState.error}</div>
                  ) : null}
                  {inviteState.success ? (
                    <div className="status-banner status-banner-success">{inviteState.success}</div>
                  ) : null}
                </form>
              </div>

              <div className="admin-list">
                <div className="admin-list-heading">Admin users</div>
                {adminMembers.length ? (
                  <div className="panel-stack">
                    {adminMembers.map((member) => (
                      <div key={member.userId} className="admin-list-item admin-action-row">
                        <div>
                          <div style={{ fontWeight: 700 }}>{member.name}</div>
                          <div style={{ color: 'var(--muted)' }}>
                            {member.identifier} · {member.role}
                          </div>
                        </div>
                        <form action={removeAction}>
                          <input type="hidden" name="organizationId" value={customer.id} />
                          <input type="hidden" name="userId" value={member.userId} />
                          <button className="button secondary" type="submit" disabled={removePending}>
                            Remove Admin
                          </button>
                        </form>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: 'var(--muted)' }}>No admin users are assigned yet.</div>
                )}
                {removeState.error ? (
                  <div className="status-banner status-banner-error">{removeState.error}</div>
                ) : null}
                {removeState.success ? (
                  <div className="status-banner status-banner-success">{removeState.success}</div>
                ) : null}
              </div>

              <div className="admin-list">
                <div className="admin-list-heading">Pending admin invites</div>
                {pendingInvites.length ? (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pendingInvites.map((invite) => (
                        <tr key={invite.id}>
                          <td>{invite.emailAddress}</td>
                          <td>{invite.role}</td>
                          <td>{invite.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ color: 'var(--muted)' }}>No pending admin invites.</div>
                )}
              </div>
            </div>
          ) : null}

          {activeSection === 'customer-assistant' ? (
            <div className="panel-stack">
              <div className="admin-list">
                <div className="admin-list-heading">Customer assistant</div>
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
                    The public <code>/assistant</code> page uses this deployment&apos;s backend AgentOS
                    service automatically. Only the zoning code URL is customer-specific.
                  </div>
                  <button className="button button-fit" type="submit" disabled={experiencePending}>
                    {experiencePending ? 'Saving…' : 'Save Assistant Settings'}
                  </button>
                  {experienceState.error ? (
                    <div className="status-banner status-banner-error">{experienceState.error}</div>
                  ) : null}
                  {experienceState.success ? (
                    <div className="status-banner status-banner-success">{experienceState.success}</div>
                  ) : null}
                </form>
              </div>

              <AgentChatPanel
                agentId="customer-zoning-agent"
                backendBase={backendApiBase}
                customerName={customer.name}
                clientId={liveZoningKnowledgeStatus.client_id}
                surface="super-admin-customer-assistant"
                title="Assistant chat"
                description={`Chat directly with the Agno AgentOS customer zoning agent for ${customer.name}. The run is bound to client_id ${liveZoningKnowledgeStatus.client_id}.`}
              />

              <div className="admin-list">
                <div className="admin-list-heading">Zoning knowledge</div>
                <div className="panel-stack">
                  <div className="admin-action-row">
                    <div>
                      <div style={{ fontWeight: 700 }}>Corpus status</div>
                      <div style={{ color: 'var(--muted)' }}>
                        {liveZoningKnowledgeStatus.documents} documents · {liveZoningKnowledgeStatus.sections}{' '}
                        sections · {liveZoningKnowledgeStatus.chunks} chunks
                      </div>
                      <div style={{ color: 'var(--muted)' }}>
                        Source: {liveZoningKnowledgeStatus.zoning_code_url || 'No zoning code URL configured'}
                      </div>
                    </div>
                  </div>

                  {liveZoningKnowledgeStatus.latest_run ? (
                    <div style={{ color: 'var(--muted)' }}>
                      {zoningRunActive ? 'Current run' : 'Last run'}:{' '}
                      {liveZoningKnowledgeStatus.latest_run.mode} ·{' '}
                      {liveZoningKnowledgeStatus.latest_run.status} · crawled{' '}
                      {liveZoningKnowledgeStatus.latest_run.pages_crawled} pages · processed{' '}
                      {liveZoningKnowledgeStatus.latest_run.documents_extracted} documents · extracted{' '}
                      {liveZoningKnowledgeStatus.latest_run.sections_extracted} sections · upserted{' '}
                      {liveZoningKnowledgeStatus.latest_run.chunks_upserted} chunks
                    </div>
                  ) : (
                    <div style={{ color: 'var(--muted)' }}>No zoning knowledge ingestion has run yet.</div>
                  )}

                  {zoningRunActive ? (
                    <div className="status-banner status-banner-success">
                      {latestRun?.status === 'queued' ? 'Ingestion is queued.' : 'Ingestion is running.'} This panel
                      refreshes automatically every few seconds.
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
                      <button
                        className="button secondary"
                        type="submit"
                        disabled={reindexPending || zoningRunActive}
                      >
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

                  <form action={queryAction} className="admin-form">
                    <input type="hidden" name="organizationId" value={customer.id} />
                    <label className="field">
                      <span>Query the knowledge base</span>
                      <textarea
                        name="query"
                        placeholder="What does the zoning code say about accessory dwelling units?"
                        rows={4}
                        required
                      />
                    </label>
                    <button className="button button-fit" type="submit" disabled={queryPending}>
                      {queryPending ? 'Querying…' : 'Query'}
                    </button>
                    {queryState.error ? (
                      <div className="status-banner status-banner-error">{queryState.error}</div>
                    ) : null}
                    {queryState.success ? (
                      <div className="status-banner status-banner-success">{queryState.success}</div>
                    ) : null}
                  </form>

                  {queryState.results.length ? (
                    <div className="panel-stack">
                      {queryState.results.map((result, index) => (
                        <div key={`${result.name || 'result'}-${index}`} className="admin-list-item">
                          <div style={{ fontWeight: 700 }}>
                            {result.meta_data?.section_title || result.name || `Result ${index + 1}`}
                          </div>
                          <div style={{ color: 'var(--muted)', marginBottom: 8 }}>
                            {result.meta_data?.source_url || 'Unknown source'}
                          </div>
                          <div>{result.content}</div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}
