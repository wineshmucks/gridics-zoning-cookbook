import { EmbedAssistantWidget } from '../../components/EmbedAssistantWidget'

export default function EmbedPage() {
  const backendBase =
    process.env.NEXT_PUBLIC_UZONE_API_BASE || process.env.UZONE_API_BASE || 'http://localhost:8000'

  return <EmbedAssistantWidget backendBase={backendBase} />
}
