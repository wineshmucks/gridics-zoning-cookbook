import { JurisdictionPickerPage } from '../components/JurisdictionPickerPage'
import { PublicHomepage } from '../features/public-homepage/PublicHomepage'
import { getCurrentHost, getCurrentProduct, getCurrentScopePath } from '../lib/org-context'
import { getTenantConfig } from '../lib/tenant'

type PageProps = {
  searchParams?: Promise<{
    returnTo?: string | string[]
  }>
}

export default async function HomePage({ searchParams }: PageProps) {
  const currentProduct = await getCurrentProduct()

  if (currentProduct === 'assistant') {
    return <JurisdictionPickerPage searchParams={searchParams} />
  }

  const [tenant, currentScopePath, currentHost] = await Promise.all([
    getTenantConfig(),
    getCurrentScopePath(),
    getCurrentHost(),
  ])

  if (!tenant) {
    return <JurisdictionPickerPage searchParams={searchParams} />
  }

  return <PublicHomepage tenant={tenant} currentScopePath={currentScopePath} currentHost={currentHost} />
}
