import { EmbedAssistantWidget } from '../../components/EmbedAssistantWidget'

export default function EmbedPage() {
  const backendBase =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

  return <EmbedAssistantWidget backendBase={backendBase} />
}
