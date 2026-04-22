import { redirect } from 'next/navigation'

import { PublicAssistantPageContent } from '../../../components/PublicAssistantPageContent'
import { getCurrentOrgId } from '../../../lib/org-context'

type PageProps = {
  params: Promise<{
    scope?: string[]
  }>
}

export default async function PublicAssistantPage({ params }: PageProps) {
  const { scope } = await params
  const orgId = await getCurrentOrgId()

  if (!orgId || !scope?.length) {
    redirect('/select-jurisdiction')
  }

  return <PublicAssistantPageContent />
}
