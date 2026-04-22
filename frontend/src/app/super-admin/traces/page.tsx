import { SuperAdminTracesClient } from '../../../components/SuperAdminTracesClient'
import { SuperAdminWorkspaceShell } from '../../../components/SuperAdminWorkspaceShell'
import { fetchAgnoTrace, fetchAgnoTraces } from '../../admin/actions'
import { getPermissionContext } from '../../../lib/permissions'

type PageProps = {
  searchParams?: Promise<{
    traceId?: string | string[]
    sessionId?: string | string[]
    traceStatus?: string | string[]
    page?: string | string[]
  }>
}

function firstParam(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] || null
  }
  return value || null
}

export default async function SuperAdminTracesPage({ searchParams }: PageProps) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin || !clerkEnabled) {
    return (
      <section className="card">
        <h1 className="section-title">Super Admin Access Required</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Only Gridics super admins can inspect Agno traces.</p>
      </section>
    )
  }

  const resolvedSearchParams = searchParams ? await searchParams : {}
  const traceId = firstParam(resolvedSearchParams.traceId)
  const sessionId = firstParam(resolvedSearchParams.sessionId)
  const traceStatus = firstParam(resolvedSearchParams.traceStatus)
  const pageValue = Number.parseInt(firstParam(resolvedSearchParams.page) || '1', 10)
  const page = Number.isFinite(pageValue) && pageValue > 0 ? pageValue : 1
  const limit = 25

  let loadError: string | null = null
  const traces = await fetchAgnoTraces({ sessionId, traceStatus, page, limit })
  const selectedTraceId = traceId || traces.items[0]?.trace_id || null
  const selectedTrace = selectedTraceId ? await fetchAgnoTrace(selectedTraceId) : null

  if (!selectedTraceId) {
    loadError = traces.total_count === 0 ? 'No traces are available yet.' : 'No traces matched the current page or filters.'
  } else if (selectedTraceId && !selectedTrace) {
    loadError = 'Unable to load the selected trace.'
  }

  return (
    <SuperAdminWorkspaceShell>
      <SuperAdminTracesClient
        traces={traces}
        selectedTrace={selectedTrace}
        selectedTraceId={selectedTraceId}
        sessionId={sessionId}
        traceStatus={traceStatus}
        page={page}
        limit={limit}
        loadError={loadError}
      />
    </SuperAdminWorkspaceShell>
  )
}
