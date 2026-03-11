import { AgentChatPanel } from '../../components/AgentChatPanel'
import { getTenantConfig } from '../../lib/tenant'

export default async function AssistantPage() {
  const tenant = await getTenantConfig()
  const backendBase =
    process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || 'http://localhost:8000'

  return (
    <section className="assistant-chat-page">
      <aside className="assistant-chat-sidebar card">
        <div className="eyebrow">Customer Assistant</div>
        <h1 className="section-title" style={{ marginBottom: 8 }}>
          {tenant.city_name} Zoning Assistant
        </h1>
        <p className="admin-copy">
          Ask zoning questions in natural language. The chat stays scoped to this deployment&apos;s
          customer knowledge base.
        </p>
        <div className="assistant-chat-sidebar-meta">
          <div>
            <span>City</span>
            <strong>{tenant.city_name}</strong>
          </div>
          <div>
            <span>Department</span>
            <strong>{tenant.department_name}</strong>
          </div>
          <div>
            <span>Zoning source</span>
            <strong>{tenant.zoning_code_url || 'Not configured'}</strong>
          </div>
        </div>
        <div className="button-row">
          <a className="button" href={`${backendBase}/config`} target="_blank" rel="noreferrer">
            View Agent Service
          </a>
          {tenant.zoning_code_url ? (
            <a className="button secondary" href={tenant.zoning_code_url} target="_blank" rel="noreferrer">
              Open Zoning Code
            </a>
          ) : null}
        </div>
      </aside>

      <div className="assistant-chat-main">
        <AgentChatPanel
          agentId="customer-zoning-agent"
          backendBase={backendBase}
          customerName={tenant.city_name}
          clientId={tenant.client_id}
          surface="public-assistant"
          title="Assistant"
          description="Zoning questions, customer-scoped answers, markdown-friendly responses."
          variant="chatgpt"
        />
      </div>
    </section>
  )
}
