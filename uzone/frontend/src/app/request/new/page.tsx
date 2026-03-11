import { RequestIntakeClient } from '../../../components/RequestIntakeClient'

export default function NewRequestPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  return <RequestIntakeClient clerkEnabled={clerkEnabled} />
}
