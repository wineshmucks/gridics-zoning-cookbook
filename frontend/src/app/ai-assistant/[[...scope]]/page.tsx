import { redirect } from 'next/navigation'

import { PublicAssistantExperience } from '../../../components/PublicAssistantExperience'
import { getClerkManagementClient } from '../../../lib/clerk'
import {
  buildAssistantDisclaimerScopeKey,
  hasAcceptedAssistantDisclaimer,
} from '../../../lib/assistant-disclaimer'
import { getCurrentOrgId } from '../../../lib/org-context'
import { getTenantConfig } from '../../../lib/tenant'
import { DEFAULT_ASSISTANT_DISCLAIMER_TEXT } from '../../../lib/assistant-disclaimer'

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

  const tenant = await getTenantConfig()
  const backendBase =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'
  const disclaimerScopeId = tenant?.path_alias || tenant?.clerk_organization_id || tenant?.client_id || orgId
  const normalizedDisclaimerScopeId = disclaimerScopeId
    ? buildAssistantDisclaimerScopeKey(disclaimerScopeId)
    : orgId
  let initialAccepted = false

  if (normalizedDisclaimerScopeId) {
    try {
      const clerkModule = await import('@clerk/nextjs/server')
      const authState = await clerkModule.auth()
      if (typeof authState?.userId === 'string' && authState.userId.trim()) {
        const client = await getClerkManagementClient()
        const user = await client.users.getUser(authState.userId)
        initialAccepted = hasAcceptedAssistantDisclaimer(user, normalizedDisclaimerScopeId)
      }
    } catch (error) {
      console.error('Unable to resolve assistant disclaimer acceptance.', error)
    }
  }

  return (
    <section className="assistant-chat-page">
      <div className="assistant-chat-main">
        <PublicAssistantExperience
          backendBase={backendBase}
          customerName={tenant?.city_name || orgId || 'Jurisdiction'}
          clientId={tenant?.client_id || orgId}
          disclaimerText={tenant?.assistant_disclaimer_text || DEFAULT_ASSISTANT_DISCLAIMER_TEXT}
          disclaimerScopeId={normalizedDisclaimerScopeId || tenant?.city_name || orgId || 'Jurisdiction'}
          initialAccepted={initialAccepted}
        />
      </div>
    </section>
  )
}
