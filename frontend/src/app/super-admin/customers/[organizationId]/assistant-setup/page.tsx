import { redirect } from 'next/navigation'

type PageProps = {
  params: Promise<{
    organizationId: string
  }>
}

export default async function SuperAdminCustomerAssistantSetupRedirectPage({ params }: PageProps) {
  const { organizationId } = await params
  redirect(`/super-admin/${organizationId}/assistant-setup`)
}
