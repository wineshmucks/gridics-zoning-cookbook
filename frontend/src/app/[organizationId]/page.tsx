import { redirect } from 'next/navigation'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}

export default async function LegacyOrganizationRedirectPage({ params, searchParams }: PageProps) {
  const { organizationId } = await params
  const resolvedSearchParams = searchParams ? await searchParams : null
  const query = new URLSearchParams()

  if (resolvedSearchParams) {
    for (const [key, value] of Object.entries(resolvedSearchParams)) {
      if (Array.isArray(value)) {
        value.forEach((entry) => {
          query.append(key, entry)
        })
      } else if (typeof value === 'string') {
        query.set(key, value)
      }
    }
  }

  const searchSuffix = query.toString() ? `?${query.toString()}` : ''
  redirect(`/${encodeURIComponent(organizationId)}/assistant${searchSuffix}`)
}
