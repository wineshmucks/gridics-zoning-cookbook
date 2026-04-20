import { fetchAdminFeeStructureAction } from '../app/admin/actions'
import { AdminFeeStructureClient } from './AdminFeeStructureClient'

export async function AdminFeeStructurePage() {
  const payload = await fetchAdminFeeStructureAction()
  return <AdminFeeStructureClient initialPayload={payload} />
}
