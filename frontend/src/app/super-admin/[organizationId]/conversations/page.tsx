import Link from 'next/link'
import { notFound } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import {
  fetchCustomerConversations,
  fetchCustomerConversation,
} from '../../../admin/actions'
import { SuperAdminCustomerHeader } from '../../../../components/SuperAdminCustomerIcons'
import { buildSuperAdminCustomerConversationsPath } from '../../../../lib/org-url'
import { getClerkManagementClient } from '../../../../lib/clerk'
import { getPermissionContext } from '../../../../lib/permissions'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
  searchParams?: Promise<{
    sessionId?: string | string[]
    session_id?: string | string[]
  }>
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown'
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(parsed)
}

function formatMessageDate(value: number | string | null | undefined): string {
  if (typeof value === 'number') {
    return formatDate(new Date(value * 1000).toISOString())
  }

  return formatDate(typeof value === 'string' ? value : null)
}

export default async function SuperAdminCustomerConversationsPage({ params, searchParams }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="super-admin-empty-state">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Only super admins can review jurisdiction conversations.</p>
      </section>
    )
  }

  const { organizationId } = await params
  const resolvedSearchParams = searchParams ? await searchParams : {}
  const selectedSessionId =
    (Array.isArray(resolvedSearchParams.sessionId)
      ? resolvedSearchParams.sessionId[0]
      : resolvedSearchParams.sessionId) ||
    (Array.isArray(resolvedSearchParams.session_id)
      ? resolvedSearchParams.session_id[0]
      : resolvedSearchParams.session_id) ||
    ''

  const client = await getClerkManagementClient()
  const organization = await client.organizations.getOrganization({ organizationId }).catch(() => null)
  if (!organization) {
    notFound()
  }

  const displayName = organization.name
  const conversations = await fetchCustomerConversations(organizationId)
  const selectedSummary =
    conversations.items.find((item) => item.session_id === selectedSessionId) || conversations.items[0] || null
  const selectedConversation = selectedSummary
    ? await fetchCustomerConversation(organizationId, selectedSummary.session_id)
    : null
  const selectedConversationId = selectedConversation?.session_id || selectedSummary?.session_id || null

  return (
    <div className="panel-stack">
      <section className="card">
        <SuperAdminCustomerHeader
          icon="conversations"
          eyebrow="Conversations"
          title="Jurisdiction Conversations"
          description="Review assistant threads for this jurisdiction. Only sessions tagged to this organization are shown here."
        />
      </section>

      {conversations.items.length === 0 ? (
        <section className="card super-admin-empty-state">
          <h2 className="section-title">No conversations yet</h2>
          <p style={{ color: 'var(--muted)', margin: 0 }}>
            Once someone chats with {displayName}, the threads will appear here.
          </p>
        </section>
      ) : (
        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'minmax(280px, 360px) minmax(0, 1fr)' }}>
          <section className="card">
            <div className="admin-inline-title" style={{ marginBottom: 12 }}>
              Conversations
            </div>
            <div className="admin-copy" style={{ marginBottom: 14 }}>
              {conversations.total_count.toLocaleString()} session{conversations.total_count === 1 ? '' : 's'} for{' '}
              {displayName}
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
              {conversations.items.map((session) => {
                const isActive = session.session_id === selectedConversationId
                return (
                  <Link
                    key={session.session_id}
                    href={`${buildSuperAdminCustomerConversationsPath(organizationId)}?sessionId=${encodeURIComponent(session.session_id)}`}
                    style={{
                      display: 'block',
                      padding: 14,
                      borderRadius: 16,
                      border: `1px solid ${isActive ? 'var(--border-strong)' : 'var(--border-subtle)'}`,
                      background: isActive ? 'var(--surface-muted)' : 'var(--surface)',
                      boxShadow: isActive ? 'var(--card-shadow-hover)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' }}>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 700, marginBottom: 4 }}>
                          {session.session_name || `Conversation ${session.session_id.slice(0, 8)}`}
                        </div>
                        <div style={{ color: 'var(--muted)', fontSize: 13, lineHeight: 1.4 }}>
                          {session.session_summary?.summary || 'No summary available yet.'}
                        </div>
                      </div>
                      <div style={{ color: 'var(--muted)', fontSize: 12, whiteSpace: 'nowrap' }}>
                        {formatDate(session.updated_at)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                      <span>{session.total_tokens ?? session.metrics?.total_tokens ?? 0} tokens</span>
                      <span>Team {session.team_id || 'unknown'}</span>
                    </div>
                  </Link>
                )
              })}
            </div>
          </section>

          <section className="card">
            {selectedConversation ? (
              <div style={{ display: 'grid', gap: 16 }}>
                <div>
                  <div className="admin-inline-title" style={{ marginBottom: 8 }}>
                    {selectedConversation.session_name || 'Conversation detail'}
                  </div>
                  <div className="admin-copy" style={{ display: 'grid', gap: 4 }}>
                    <span>Session ID: {selectedConversation.session_id}</span>
                    <span>Updated: {formatDate(selectedConversation.updated_at)}</span>
                    <span>Created: {formatDate(selectedConversation.created_at)}</span>
                    <span>Tenant scope: {displayName}</span>
                  </div>
                  {selectedConversation.session_summary?.summary ? (
                    <p className="admin-copy" style={{ marginTop: 12, marginBottom: 0 }}>
                      {selectedConversation.session_summary.summary}
                    </p>
                  ) : null}
                </div>

                <div style={{ display: 'grid', gap: 12 }}>
                  {selectedConversation.chat_history
                    .filter((message) => message.role !== 'system')
                    .map((message, index) => (
                      <article
                        key={`${selectedConversation.session_id}-${index}-${message.role || 'message'}`}
                        className="card"
                        style={{ padding: 14, margin: 0 }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
                          <strong style={{ textTransform: 'capitalize' }}>{message.role || 'message'}</strong>
                          <span style={{ color: 'var(--muted)', fontSize: 12 }}>
                            {formatMessageDate(message.created_at)}
                          </span>
                        </div>
                        {message.role === 'assistant' ? (
                          <div
                            style={{
                              margin: 0,
                              wordBreak: 'break-word',
                              color: 'var(--text-primary)',
                              lineHeight: 1.7,
                            }}
                          >
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || '(empty message)'}</ReactMarkdown>
                          </div>
                        ) : (
                          <pre
                            style={{
                              margin: 0,
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              fontFamily: 'inherit',
                              color: 'var(--text-primary)',
                              lineHeight: 1.6,
                            }}
                          >
                            {message.content || '(empty message)'}
                          </pre>
                        )}
                      </article>
                    ))}
                </div>
              </div>
            ) : (
              <div className="super-admin-empty-state">
                <h2 className="section-title">Select a conversation</h2>
                <p style={{ color: 'var(--muted)', margin: 0 }}>
                  Choose a thread from the list to inspect the transcript and run context.
                </p>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
