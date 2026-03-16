import { AgentChatPanel } from '../../components/AgentChatPanel'
import { getTenantConfig } from '../../lib/tenant'

export default async function AssistantPage() {
  const tenant = await getTenantConfig()
  const backendBase =
    process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || 'http://localhost:8000'
  const defaultModelId = process.env.UZONE_ZONING_AGENT_LLM_MODEL_ID || ''

  return (
    <section className="assistant-chat-page">
      <div className="assistant-chat-main">
        <AgentChatPanel
          agentId="customer-zoning-agent"
          backendBase={backendBase}
          customerName={tenant.city_name}
          clientId={tenant.client_id}
          defaultModelId={defaultModelId}
          surface="public-assistant"
          title=""
          description=""
          variant="chatgpt"
        />
      </div>
    </section>
  )
}
