import { fetchCustomerRecords } from '../app/admin/actions'
import { getClerkManagementClient } from '../lib/clerk'
import { SuperAdminCustomerList } from './SuperAdminCustomerList'

type ClientSummary = {
  id: string
  name: string
  membersCount: number | null
  customerId: string | null
  isActive: boolean | null
}

export async function SuperAdminPanel({
  flashMessage,
  flashTone,
}: {
  flashMessage?: string | null
  flashTone?: 'success' | 'error' | null
}) {
  const client = await getClerkManagementClient()
  const [organizations, tenantRecords] = await Promise.all([
    client.organizations.getOrganizationList({
      includeMembersCount: true,
      orderBy: 'name',
      limit: 100,
    }),
    fetchCustomerRecords(),
  ])

  const tenantRecordMap = new Map(tenantRecords.map((record) => [record.clerk_organization_id, record]))

  const activeCustomers: ClientSummary[] = organizations.data.map((organization) => ({
    id: organization.id,
    name: organization.name,
    membersCount: organization.membersCount ?? null,
    customerId: organization.id,
    isActive: tenantRecordMap.get(organization.id)?.is_active ?? null,
  }))

  const inactiveCustomers: ClientSummary[] = tenantRecords
    .filter((record) => record.is_active === false)
    .map((record) => ({
      id: record.id,
      name: record.city_name,
      membersCount: null,
      customerId: record.clerk_organization_id,
      isActive: record.is_active,
    }))

  return (
    <SuperAdminCustomerList
      flashMessage={flashMessage || null}
      flashTone={flashTone || null}
      customers={activeCustomers}
      inactiveCustomers={inactiveCustomers}
    />
  )
}
