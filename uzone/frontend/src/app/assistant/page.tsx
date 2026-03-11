import { AgentChatPanel } from '../../components/AgentChatPanel'
import { getTenantConfig } from '../../lib/tenant'

export default async function AssistantPage() {
  const tenant = await getTenantConfig()
  const backendBase =
    process.env.UZONE_API_BASE || process.env.NEXT_PUBLIC_UZONE_API_BASE || 'http://localhost:8000'

  return (
    <section className="assistant-shell">
      <div className="assistant-header">
        <div>
          <div className="eyebrow">Customer Assistant</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            {tenant.city_name} Zoning Assistant
          </h1>
          <p className="admin-copy">
            This assistant is powered by the built-in backend AgentOS service for this deployment.
            Keep the official zoning code open alongside the conversation.
          </p>
        </div>
        <div className="button-row">
          <a className="button" href={`${backendBase}/config`} target="_blank" rel="noreferrer">
            View Agent Service
          </a>
          {tenant.zoning_code_url ? (
            <a
              className="button secondary"
              href={tenant.zoning_code_url}
              target="_blank"
              rel="noreferrer"
            >
              Open Zoning Code
            </a>
          ) : null}
        </div>
      </div>

      <div className="card">
        <AgentChatPanel
          agentId="customer-zoning-agent"
          backendBase={backendBase}
          customerName={tenant.city_name}
          clientId={tenant.client_id}
          surface="public-assistant"
          title="Backend-hosted assistant"
          description="This chat runs against the local Agno AgentOS deployment for the current tenant and keeps the conversation scoped to this customer."
        />
      </div>
    </section>
  )
}
