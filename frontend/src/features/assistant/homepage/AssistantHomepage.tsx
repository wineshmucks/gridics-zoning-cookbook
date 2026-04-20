import type { TenantConfig } from '../../../lib/tenant'
import { SurfaceHomepage } from '../../public-homepage/SurfaceHomepage'
import { buildAssistantHomepageConfig } from './assistant-homepage'

export function AssistantHomepage({
  tenant,
  currentScopePath,
  currentHost,
}: {
  tenant: TenantConfig
  currentScopePath: string | null
  currentHost: string | null
}) {
  return (
    <SurfaceHomepage
      tenant={tenant}
      currentScopePath={currentScopePath}
      currentHost={currentHost}
      surface={buildAssistantHomepageConfig(tenant)}
      currentSurface="assistant"
    />
  )
}
