import { notFound, redirect } from 'next/navigation'

import HomePage from '../page'
import { PublicAssistantPageContent } from '../../components/PublicAssistantPageContent'
import { getCurrentOrgId, getCurrentScopedPathname } from '../../lib/org-context'

type PageProps = {
  searchParams?: Promise<{
    returnTo?: string | string[]
  }>
}

export default async function ScopedAliasPage({ searchParams }: PageProps) {
  const [orgId, scopedPathname] = await Promise.all([getCurrentOrgId(), getCurrentScopedPathname()])

  if (!orgId) {
    notFound()
  }

  if (scopedPathname === '/' || scopedPathname === '') {
    return <HomePage searchParams={searchParams} />
  }

  if (scopedPathname === '/assistant' || scopedPathname.startsWith('/assistant/')) {
    return <PublicAssistantPageContent />
  }

  if (scopedPathname === '/select-jurisdiction') {
    redirect('/select-jurisdiction')
  }

  notFound()
}
