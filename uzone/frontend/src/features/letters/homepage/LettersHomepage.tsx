import type { TenantConfig } from '../../../lib/tenant'
import { SurfaceHomepage } from '../../public-homepage/SurfaceHomepage'
import { buildLettersHomepageConfig } from './letters-homepage'

export function LettersHomepage({
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
      surface={buildLettersHomepageConfig(tenant)}
      currentSurface="letters"
    />
  )
}
