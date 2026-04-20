import { fetchAdminEmailTemplatesAction } from '../app/admin/actions'
import { AdminEmailTemplatesClient } from './AdminEmailTemplatesClient'

export async function AdminEmailTemplatesPage() {
  const payload = await fetchAdminEmailTemplatesAction()
  return <AdminEmailTemplatesClient initialPayload={payload} />
}
