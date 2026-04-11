import { redirect } from 'next/navigation'

export default async function AdminNewCustomerPage() {
  redirect('/super-admin/customers/new')
}
