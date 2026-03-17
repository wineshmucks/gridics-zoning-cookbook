import { getClerkManagementClient } from '../lib/clerk'
import { fetchCustomerRecord } from '../app/admin/actions'
import { SuperAdminCustomerList } from './SuperAdminCustomerList'

type ClientSummary = {
  id: string
  name: string
  membersCount: number | null
  isActive: boolean | null
}

export async function SuperAdminPanel({ flashMessage }: { flashMessage?: string | null }) {
  const client = await getClerkManagementClient()
  const organizations = await client.organizations.getOrganizationList({
    includeMembersCount: true,
    orderBy: 'name',
    limit: 100,
  })

  const tenantRecords = await Promise.all(
    organizations.data.map(async (organization) => ({
      organizationId: organization.id,
      record: await fetchCustomerRecord(organization.id),
    })),
  )
  const tenantRecordMap = new Map(
    tenantRecords.map(({ organizationId, record }) => [organizationId, record]),
  )

  const clients: ClientSummary[] = organizations.data.map((organization) => ({
    id: organization.id,
    name: organization.name,
    membersCount: organization.membersCount ?? null,
    isActive: tenantRecordMap.get(organization.id)?.is_active ?? null,
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
