import Link from 'next/link'
import type { ReactNode } from 'react'

import type { AgnoSpan, AgnoTrace, AgnoTraceDetail, AgnoTracesResponse } from '../app/admin/actions'
import { SuperAdminCustomerHeader } from './SuperAdminCustomerIcons'

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

function buildSearchParams(params: Record<string, string | number | null | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') {
      continue
    }
    query.set(key, String(value))
  }
  return query.toString()
}

function traceListHref(basePath: string, params: Record<string, string | number | null | undefined>): string {
  const query = buildSearchParams(params)
  return query ? `${basePath}?${query}` : basePath
}

function renderTraceBadge(label: string, value: ReactNode) {
  return (
    <div className="super-admin-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function buildSpanChildren(spans: AgnoSpan[]): Map<string | null, AgnoSpan[]> {
  const children = new Map<string | null, AgnoSpan[]>()
  for (const span of spans) {
    const parentKey = span.parent_span_id || null
    const current = children.get(parentKey) || []
    current.push(span)
    children.set(parentKey, current)
  }

  for (const spanList of children.values()) {
    spanList.sort((left, right) => left.start_time.localeCompare(right.start_time) || left.span_id.localeCompare(right.span_id))
  }

  return children
}

function SpanNode({
  span,
  childrenMap,
  depth,
}: {
  span: AgnoSpan
  childrenMap: Map<string | null, AgnoSpan[]>
  depth: number
}) {
  const childSpans = childrenMap.get(span.span_id) || []
  const hasAttributes = Object.keys(span.attributes || {}).length > 0

  return (
    <article
      className="card"
      style={{
        margin: 0,
        padding: 14,
        marginLeft: depth * 18,
        borderLeft: depth > 0 ? '3px solid var(--line)' : undefined,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' }}>
        <div style={{ minWidth: 0 }}>
          <strong style={{ display: 'block', marginBottom: 4 }}>{span.name}</strong>
          <div style={{ color: 'var(--muted)', fontSize: 12, lineHeight: 1.5 }}>
            <span>{span.span_kind}</span>
            <span> • </span>
            <span>{span.status_code}</span>
            <span> • </span>
            <span>{span.duration_ms} ms</span>
          </div>
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 12, whiteSpace: 'nowrap' }}>
          {formatDate(span.start_time)}
        </div>
      </div>
      <div style={{ display: 'grid', gap: 6, marginTop: 10, fontSize: 12, color: 'var(--text-secondary)' }}>
        <span>Span ID: {span.span_id}</span>
        <span>Parent Span ID: {span.parent_span_id || 'Root'}</span>
        {span.status_message ? <span>Status message: {span.status_message}</span> : null}
      </div>
      {hasAttributes ? (
        <details style={{ marginTop: 12 }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Attributes</summary>
          <pre
            style={{
              margin: '10px 0 0',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'inherit',
              fontSize: 12,
              color: 'var(--text-primary)',
              lineHeight: 1.6,
            }}
          >
            {JSON.stringify(span.attributes, null, 2)}
          </pre>
        </details>
      ) : null}
      {childSpans.length ? (
        <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
          {childSpans.map((childSpan) => (
            <SpanNode key={childSpan.span_id} span={childSpan} childrenMap={childrenMap} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </article>
  )
}

export function SuperAdminTracesClient({
  traces,
  selectedTrace,
  selectedTraceId,
  sessionId,
  traceStatus,
  page,
  limit,
  loadError,
}: {
  traces: AgnoTracesResponse
  selectedTrace: AgnoTraceDetail | null
  selectedTraceId: string | null
  sessionId: string | null
  traceStatus: string | null
  page: number
  limit: number
  loadError: string | null
}) {
  const basePath = '/super-admin/traces'
  const totalPages = Math.max(1, Math.ceil((traces.total_count || 0) / Math.max(1, limit)))
  const resolvedPage = Math.min(Math.max(page, 1), totalPages)
  const hasPrev = resolvedPage > 1
  const hasNext = resolvedPage < totalPages
  const childrenMap = selectedTrace ? buildSpanChildren(selectedTrace.spans) : new Map<string | null, AgnoSpan[]>()
  const rootSpans = selectedTrace ? (childrenMap.get(null) || []).concat(childrenMap.get('') || []) : []

  return (
    <section className="card admin-stack super-admin-traces-page" style={{ marginBottom: 18 }}>
      <div className="admin-header super-admin-traces-header">
        <div className="super-admin-page-header-copy super-admin-traces-header-copy">
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Agno Traces
          </h1>
          <p className="admin-copy">
            Inspect the trace records that Agno writes for assistant runs, including the trace summary and nested spans.
          </p>
        </div>
        <form method="get" className="super-admin-traces-filters">
          <div className="super-admin-traces-filter-fields">
            <label className="field" style={{ display: 'grid', gap: 6 }}>
              <span>Session ID</span>
              <input name="sessionId" defaultValue={sessionId || ''} placeholder="Filter by session ID" />
            </label>
            <label className="field" style={{ display: 'grid', gap: 6 }}>
              <span>Status</span>
              <input name="traceStatus" defaultValue={traceStatus || ''} placeholder="OK, ERROR, or UNSET" />
            </label>
            <input type="hidden" name="page" value="1" />
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
            <Link className="button secondary" href={basePath}>
              Clear
            </Link>
            <button className="button secondary" type="submit">
              Apply Filters
            </button>
          </div>
        </form>
      </div>

      {loadError ? <div className="status-banner status-banner-error">{loadError}</div> : null}

      <div className="super-admin-metrics-row" aria-label="Trace summary">
        {renderTraceBadge('Total traces', traces.total_count.toLocaleString())}
        {renderTraceBadge('Page', `${resolvedPage} / ${totalPages}`)}
        {renderTraceBadge('Session filter', sessionId || 'All sessions')}
        {renderTraceBadge('Status filter', traceStatus || 'All statuses')}
      </div>

      <div className="super-admin-traces-grid">
        <section className="super-admin-section-shell super-admin-traces-panel">
          <div className="super-admin-section-head">
            <div className="admin-list-heading super-admin-section-heading">Recent traces</div>
            <div className="super-admin-section-meta">{traces.items.length} shown</div>
          </div>

          {traces.items.length ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {traces.items.map((trace: AgnoTrace) => {
                const active = trace.trace_id === selectedTraceId
                return (
                  <Link
                    key={trace.trace_id}
                    href={traceListHref(basePath, {
                      sessionId,
                      traceStatus,
                      page: resolvedPage,
                      traceId: trace.trace_id,
                    })}
                    style={{
                      display: 'block',
                      padding: 14,
                      borderRadius: 16,
                      border: `1px solid ${active ? 'var(--border-strong)' : 'var(--border-subtle)'}`,
                      background: active ? 'var(--surface-muted)' : 'var(--surface)',
                      boxShadow: active ? 'var(--card-shadow-hover)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'start' }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontWeight: 700, marginBottom: 4 }}>{trace.name}</div>
                        <div style={{ color: 'var(--muted)', fontSize: 13, lineHeight: 1.4, overflowWrap: 'anywhere' }}>
                          {trace.trace_id}
                        </div>
                      </div>
                      <div style={{ color: 'var(--muted)', fontSize: 12, whiteSpace: 'nowrap' }}>
                        {formatDate(trace.created_at)}
                      </div>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
                      <span>{trace.status}</span>
                      <span>{trace.duration_ms} ms</span>
                      <span>{trace.total_spans} spans</span>
                    </div>
                  </Link>
                )
              })}
            </div>
          ) : (
            <div className="super-admin-empty-inline">
              <strong>No traces found.</strong>
              <span>Try a broader filter or wait for new assistant activity.</span>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 16 }}>
            <Link
              className="button secondary"
              aria-disabled={!hasPrev}
              href={hasPrev ? traceListHref(basePath, { sessionId, traceStatus, page: resolvedPage - 1 }) : basePath}
              tabIndex={hasPrev ? undefined : -1}
              style={!hasPrev ? { opacity: 0.5, pointerEvents: 'none' } : undefined}
            >
              Previous
            </Link>
            <Link
              className="button secondary"
              aria-disabled={!hasNext}
              href={hasNext ? traceListHref(basePath, { sessionId, traceStatus, page: resolvedPage + 1 }) : basePath}
              tabIndex={hasNext ? undefined : -1}
              style={!hasNext ? { opacity: 0.5, pointerEvents: 'none' } : undefined}
            >
              Next
            </Link>
          </div>
        </section>

        <section className="super-admin-section-shell super-admin-traces-panel super-admin-traces-detail-panel">
          <div className="super-admin-section-head">
            <div className="admin-list-heading super-admin-section-heading">Trace detail</div>
            <div className="super-admin-section-meta">
              {selectedTrace?.trace.trace_id || 'Select a trace'}
            </div>
          </div>

          {selectedTrace ? (
            <div style={{ display: 'grid', gap: 16 }}>
              <div>
                <div className="admin-inline-title" style={{ marginBottom: 8 }}>
                  {selectedTrace.trace.name}
                </div>
                <div className="admin-copy super-admin-trace-copy" style={{ display: 'grid', gap: 4 }}>
                  <span>Trace ID: {selectedTrace.trace.trace_id}</span>
                  <span>Session ID: {selectedTrace.trace.session_id || 'Unavailable'}</span>
                  <span>Run ID: {selectedTrace.trace.run_id || 'Unavailable'}</span>
                  <span>Status: {selectedTrace.trace.status}</span>
                  <span>Started: {formatDate(selectedTrace.trace.start_time)}</span>
                  <span>Ended: {formatDate(selectedTrace.trace.end_time)}</span>
                </div>
              </div>

              <div className="super-admin-metrics-row" aria-label="Trace metrics">
                {renderTraceBadge('Duration', `${selectedTrace.trace.duration_ms} ms`)}
                {renderTraceBadge('Spans', selectedTrace.trace.total_spans)}
                {renderTraceBadge('Errors', selectedTrace.trace.error_count)}
                {renderTraceBadge('Agent', selectedTrace.trace.agent_id || 'Unknown')}
                {renderTraceBadge('Team', selectedTrace.trace.team_id || 'Unknown')}
              </div>

              <div style={{ display: 'grid', gap: 10 }}>
                <div className="admin-inline-title">Span tree</div>
                {rootSpans.length ? (
                  <div style={{ display: 'grid', gap: 10 }}>
                    {rootSpans.map((span) => (
                      <SpanNode key={span.span_id} span={span} childrenMap={childrenMap} depth={0} />
                    ))}
                  </div>
                ) : (
                  <div className="super-admin-empty-inline">
                    <strong>No spans found.</strong>
                    <span>This trace did not include any span rows.</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="super-admin-empty-inline">
              <strong>No trace selected.</strong>
              <span>Pick a trace from the list to inspect its spans and metadata.</span>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
