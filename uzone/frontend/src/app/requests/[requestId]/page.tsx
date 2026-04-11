import { RequestDetailClient } from '../../../components/RequestDetailClient'

export default async function RequestDetailPage({
  params,
}: {
  params: Promise<{ requestId: string }>
}) {
  const { requestId } = await params
  return <RequestDetailClient requestId={requestId} />
}
