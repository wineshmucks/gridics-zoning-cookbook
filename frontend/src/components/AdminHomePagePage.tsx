import { fetchAdminHomePageContentAction } from '../app/admin/actions'
import { AdminHomePageClient } from './AdminHomePageClient'

export async function AdminHomePagePage() {
  const payload = await fetchAdminHomePageContentAction()
  return <AdminHomePageClient initialPayload={payload} />
}
