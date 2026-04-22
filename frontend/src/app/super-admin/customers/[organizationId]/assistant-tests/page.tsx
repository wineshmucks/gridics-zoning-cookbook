import { redirect } from 'next/navigation'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerAssistantTestsRedirectPage({ params }: PageProps) {
  const { organizationId } = await params
  redirect(`/super-admin/${organizationId}/assistant-tests`)
}
