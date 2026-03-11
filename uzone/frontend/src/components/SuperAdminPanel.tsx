import { getClerkManagementClient } from '../lib/clerk'
import { SuperAdminCustomerList } from './SuperAdminCustomerList'

type ClientSummary = {
  id: string
  name: string
  membersCount: number | null
}

export async function SuperAdminPanel({ flashMessage }: { flashMessage?: string | null }) {
  const client = await getClerkManagementClient()
  const organizations = await client.organizations.getOrganizationList({
    includeMembersCount: true,
    orderBy: 'name',
    limit: 100,
  })

  const clients: ClientSummary[] = organizations.data.map((organization) => ({
    id: organization.id,
    name: organization.name,
    membersCount: organization.membersCount ?? null,
  }))

  return (
    <SuperAdminCustomerList
      flashMessage={flashMessage || null}
      customers={clients.map((customer) => ({
        ...customer,
        customerId: customer.id,
      }))}
    />
  )
}
