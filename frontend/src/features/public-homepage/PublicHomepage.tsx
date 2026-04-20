import type { TenantConfig } from '../../lib/tenant'
import { AssistantHomepage } from '../assistant/homepage/AssistantHomepage'
import { LettersHomepage } from '../letters/homepage/LettersHomepage'

export function PublicHomepage({
  tenant,
  currentScopePath,
  currentHost,
}: {
  tenant: TenantConfig
  currentScopePath: string | null
  currentHost: string | null
}) {
  if (tenant.current_product === 'assistant') {
    return <AssistantHomepage tenant={tenant} currentScopePath={currentScopePath} currentHost={currentHost} />
  }

  return <LettersHomepage tenant={tenant} currentScopePath={currentScopePath} currentHost={currentHost} />
}
