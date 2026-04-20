import { StaffRequestsClient } from '../../../components/StaffRequestsClient'

export default function StaffRequestsPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  return <StaffRequestsClient clerkEnabled={clerkEnabled} />
}
