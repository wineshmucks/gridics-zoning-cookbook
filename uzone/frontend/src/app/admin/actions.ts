'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

import { getClerkManagementClient } from '../../lib/clerk'
import { getPermissionContext } from '../../lib/permissions'

export type ProvisionClientState = {
  error: string | null
  success: string | null
  organizationId: string | null
}

export type InviteAdminState = {
  error: string | null
  success: string | null
}

export type RemoveAdminState = {
  error: string | null
  success: string | null
}

export type CustomerMutationState = {
  error: string | null
  success: string | null
}

export type CustomerRecord = {
  id: string
  client_id: string
  clerk_organization_id: string | null
  jurisdiction_id: string | null
  city_name: string
  department_name: string
  is_active: boolean
}

export type CustomerExperienceSettingsState = {
  error: string | null
  success: string | null
}

export type CustomerExperienceSettings = {
  zoning_code_url: string | null
}

export type CustomerZoningKnowledgeLatestRun = {
  id: string
  mode: string
  status: string
  source_url: string
  pages_crawled: number
  documents_extracted: number
  sections_extracted: number
  chunks_upserted: number
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export type CustomerZoningKnowledgeStatus = {
  client_id: string
  zoning_code_url: string | null
  documents: number
  sections: number
  chunks: number
  latest_run: CustomerZoningKnowledgeLatestRun | null
}

export type CustomerZoningKnowledgeMutationState = {
  error: string | null
  success: string | null
}

export type CustomerZoningKnowledgeQueryResult = {
  content: string
  name: string | null
  meta_data: Record<string, string | number | boolean | null> | null
}

export type CustomerZoningKnowledgeQueryState = {
  error: string | null
  success: string | null
  results: CustomerZoningKnowledgeQueryResult[]
}

export type AdminEmailTemplate = {
  id: string
  code: string
  trigger_state: string
  name: string
  description: string | null
  category: string
  subject_template: string
  body_template: string
  status: 'draft' | 'active' | 'inactive'
  version: number
  owner_organization_id: string | null
  default_template_id: string
  override_template_id: string | null
  is_override: boolean
  updated_at: string
}

export type AdminEmailTemplatesPayload = {
  client: {
    id: string
    client_id: string
    clerk_organization_id: string | null
    city_name: string
    department_name: string
  }
  templates: AdminEmailTemplate[]
}

export type AdminFeeStructureItem = {
  id: string
  fee_schedule_id: string
  code: string
  name: string
  category: 'base_fees' | 'expedited_fees' | 'additional_services' | 'general'
  fee_type: string
  description: string | null
  amount_cents: number
  currency: string
  applies_to_letter_type: string | null
  applies_to_processing_type: string | null
  applies_to_delivery_method: string | null
  tax_mode: string | null
  charge_unit: string | null
  display_order: number
  is_active: boolean
  metadata_json: Record<string, string | number | boolean | null> | null
  created_at: string
  updated_at: string
}

export type AdminFeeStructurePayload = {
  client: {
    id: string
    client_id: string
    clerk_organization_id: string | null
    city_name: string
    department_name: string
    jurisdiction_id: string
  }
  schedule: {
    id: string
    jurisdiction_id: string
    name: string
    status: string
    effective_start_at: string | null
    effective_end_at: string | null
    created_by_user_id: string | null
    created_at: string
    updated_at: string
  }
  items: AdminFeeStructureItem[]
}

export type AdminHomePageHeroStat = {
  label: string
  value: string
  icon: string
}

export type AdminHomePageServiceItem = {
  id: string
  title: string
  description: string
  processing_time: string
  fee: string
}

export type AdminHomePageFaqItem = {
  id: string
  question: string
  answer: string
}

export type AdminHomePagePayload = {
  client: {
    id: string
    client_id: string
    clerk_organization_id: string | null
    city_name: string
    department_name: string
    jurisdiction_id: string
  }
  content: {
    hero: {
      badge: string
      title: string
      subtitle: string
      primary_button_text: string
      secondary_button_text: string
      learn_more_text: string
      stats: AdminHomePageHeroStat[]
    }
    services: AdminHomePageServiceItem[]
    about: {
      title: string
      body: string
    }
    faq: AdminHomePageFaqItem[]
    contact: {
      title: string
      body: string
      email: string | null
      phone: string | null
      address: string | null
    }
  }
}

const initialProvisionState: ProvisionClientState = {
  error: null,
  success: null,
  organizationId: null,
}

const initialMutationState: InviteAdminState = {
  error: null,
  success: null,
}

const initialCustomerMutationState: CustomerMutationState = {
  error: null,
  success: null,
}

const initialCustomerExperienceSettingsState: CustomerExperienceSettingsState = {
  error: null,
  success: null,
}

const initialCustomerZoningKnowledgeMutationState: CustomerZoningKnowledgeMutationState = {
  error: null,
  success: null,
}

function buildEmptyCustomerZoningKnowledgeStatus(
  organizationId: string,
): CustomerZoningKnowledgeStatus {
  return {
    client_id: organizationId,
    zoning_code_url: null,
    documents: 0,
    sections: 0,
    chunks: 0,
    latest_run: null,
  }
}

function buildEmptyCustomerExperienceSettings(): CustomerExperienceSettings {
  return {
    zoning_code_url: null,
  }
}

function normalizeBackendOrigin(value: string | undefined): string {
  if (value === undefined) {
    return 'http://localhost:8000'
  }

  const trimmed = value.trim().replace(/\/+$/, '')
  if (!trimmed || trimmed === '/api') {
    return ''
  }

  return trimmed.endsWith('/api') ? trimmed.slice(0, -4) : trimmed
}

const backendOrigin = normalizeBackendOrigin(
  process.env.UZONE_API_BASE || process.env.NEXT_PUBLIC_UZONE_API_BASE,
)

function buildBackendApiUrl(path: string): string {
  return `${backendOrigin}${path}`
}

function getErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message && error.message !== 'Forbidden') {
    return error.message
  }

  if (typeof error === 'object' && error !== null) {
    const maybeErrors = (error as { errors?: Array<{ longMessage?: string; message?: string }> }).errors
    const detailedMessage = maybeErrors
      ?.map((item) => item.longMessage || item.message)
      .filter(Boolean)
      .join(' ')

    if (detailedMessage) {
      return detailedMessage
    }

    const maybeMessage = (error as { message?: string }).message
    if (maybeMessage) {
      return maybeMessage
    }
  }

  return fallback
}

function normalizeEmail(value: string) {
  return value.trim().toLowerCase()
}

async function getAdminScopedTarget() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.canAccessAdminScreens) {
    throw new Error('You need admin access for the selected jurisdiction organization.')
  }

  const organizationId =
    permissions.selectedAdminMembership?.organizationId ||
    permissions.currentClientMembership?.organizationId ||
    null
  const clientId =
    permissions.selectedAdminMembership?.clientId ||
    permissions.currentClientId ||
    null

  if (!organizationId && !clientId) {
    throw new Error('Unable to resolve the current jurisdiction context.')
  }

  return { organizationId, clientId }
}

async function createTenantClientRecord(clientName: string, organizationId: string) {
  const response = await fetch(buildBackendApiUrl('/api/admin/clients'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: organizationId,
      clerk_organization_id: organizationId,
      city_name: clientName,
      department_name: `${clientName} Planning & Zoning Department`,
    }),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to create tenant client record.',
    )
  }
}

async function ensureTenantClientRecord(organizationId: string) {
  const client = await getClerkManagementClient()
  const organization = await client.organizations.getOrganization({ organizationId })

  try {
    await createTenantClientRecord(organization.name, organization.id)
  } catch (error) {
    const message = getErrorMessage(error, '')
    if (message !== 'Client ID already exists' && message !== 'Clerk organization is already linked to a tenant client') {
      throw error
    }
  }
}

async function updateTenantClientStatus(organizationId: string, isActive: boolean) {
  const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}`), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      is_active: isActive,
    }),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to update jurisdiction status.',
    )
  }
}

export async function fetchCustomerRecord(
  organizationId: string,
): Promise<CustomerRecord | null> {
  try {
    const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}`), {
      cache: 'no-store',
    })

    if (response.status === 404) {
      return null
    }

    if (!response.ok) {
      throw new Error('Unable to load jurisdiction status.')
    }

    return (await response.json()) as CustomerRecord
  } catch {
    return null
  }
}

async function deleteTenantClientRecord(organizationId: string) {
  const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}`), {
    method: 'DELETE',
  })

  if (response.status === 404) {
    return
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to delete jurisdiction record.',
    )
  }
}

export async function fetchCustomerExperienceSettings(
  organizationId: string,
): Promise<CustomerExperienceSettings> {
  try {
    const response = await fetch(
      buildBackendApiUrl(`/api/admin/clients/${organizationId}/experience-settings`),
      {
        cache: 'no-store',
      },
    )

    if (!response.ok) {
      return buildEmptyCustomerExperienceSettings()
    }

    return (await response.json()) as CustomerExperienceSettings
  } catch {
    return buildEmptyCustomerExperienceSettings()
  }
}

export async function saveCustomerExperienceSettingsAction(
  _previousState: CustomerExperienceSettingsState,
  formData: FormData,
): Promise<CustomerExperienceSettingsState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return {
      ...initialCustomerExperienceSettingsState,
      error: 'Only super admins can update assistant settings.',
    }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const zoningCodeUrl = String(formData.get('zoningCodeUrl') || '').trim()

  if (!organizationId) {
    return {
      ...initialCustomerExperienceSettingsState,
      error: 'Organization is required.',
    }
  }

  try {
    const saveSettings = async () =>
      fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}/experience-settings`), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          zoning_code_url: zoningCodeUrl || null,
        }),
      })

    let response = await saveSettings()

    if (response.status === 404) {
      await ensureTenantClientRecord(organizationId)
      response = await saveSettings()
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(
        typeof payload?.detail === 'string'
          ? payload.detail
          : 'Unable to save jurisdiction assistant settings.',
      )
    }

    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    revalidatePath('/assistant')
    revalidatePath('/')

    return {
      error: null,
      success: 'Jurisdiction assistant settings saved.',
    }
  } catch (error) {
    return {
      ...initialCustomerExperienceSettingsState,
      error: getErrorMessage(error, 'Unable to save jurisdiction assistant settings.'),
    }
  }
}

export async function fetchCustomerZoningKnowledgeStatus(
  organizationId: string,
): Promise<CustomerZoningKnowledgeStatus> {
  try {
    const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}/zoning-knowledge`), {
      cache: 'no-store',
    })

    if (!response.ok) {
      return buildEmptyCustomerZoningKnowledgeStatus(organizationId)
    }

    return (await response.json()) as CustomerZoningKnowledgeStatus
  } catch {
    return buildEmptyCustomerZoningKnowledgeStatus(organizationId)
  }
}

async function mutateCustomerZoningKnowledge(
  organizationId: string,
  mode: 'ingest' | 'reindex',
): Promise<void> {
  const response = await fetch(
    buildBackendApiUrl(`/api/admin/clients/${organizationId}/zoning-knowledge/ingest`),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ mode }),
    },
  )

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : `Unable to ${mode} zoning knowledge.`,
    )
  }
}

export async function ingestCustomerZoningKnowledgeAction(
  _previousState: CustomerZoningKnowledgeMutationState,
  formData: FormData,
): Promise<CustomerZoningKnowledgeMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can ingest zoning knowledge.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  try {
    await mutateCustomerZoningKnowledge(organizationId, 'ingest')
    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    return { error: null, success: 'Zoning code ingestion started.' }
  } catch (error) {
    return { error: getErrorMessage(error, 'Unable to ingest zoning knowledge.'), success: null }
  }
}

export async function reindexCustomerZoningKnowledgeAction(
  _previousState: CustomerZoningKnowledgeMutationState,
  formData: FormData,
): Promise<CustomerZoningKnowledgeMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can reindex zoning knowledge.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  try {
    await mutateCustomerZoningKnowledge(organizationId, 'reindex')
    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    return { error: null, success: 'Zoning knowledge reindex started.' }
  } catch (error) {
    return { error: getErrorMessage(error, 'Unable to reindex zoning knowledge.'), success: null }
  }
}

export async function queryCustomerZoningKnowledgeAction(
  _previousState: CustomerZoningKnowledgeQueryState,
  formData: FormData,
): Promise<CustomerZoningKnowledgeQueryState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can query zoning knowledge.', success: null, results: [] }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const query = String(formData.get('query') || '').trim()

  if (!organizationId) {
    return { error: 'Organization is required.', success: null, results: [] }
  }

  if (!query) {
    return { error: 'Enter a query to search the zoning knowledge base.', success: null, results: [] }
  }

  try {
    const response = await fetch(
      buildBackendApiUrl(`/api/admin/clients/${organizationId}/zoning-knowledge/query`),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query, limit: 5 }),
      },
    )

    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(
        typeof payload?.detail === 'string'
          ? payload.detail
          : 'Unable to query zoning knowledge.',
      )
    }

    const payload = (await response.json()) as {
      query: string
      results: CustomerZoningKnowledgeQueryResult[]
    }

    return {
      error: null,
      success: `Found ${payload.results.length} zoning knowledge matches.`,
      results: payload.results,
    }
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to query zoning knowledge.'),
      success: null,
      results: [],
    }
  }
}

export async function provisionClientAction(
  _previousState: ProvisionClientState,
  formData: FormData,
): Promise<ProvisionClientState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { ...initialProvisionState, error: 'Only super admins can provision clients.' }
  }

  const clientName = String(formData.get('clientName') || '').trim()

  if (!clientName) {
    return { ...initialProvisionState, error: 'Jurisdiction name is required.' }
  }

  const client = await getClerkManagementClient()

  try {
    const organization = await client.organizations.createOrganization({
      name: clientName,
    })

    try {
      await createTenantClientRecord(clientName, organization.id)
    } catch (error) {
      await client.organizations.deleteOrganization(organization.id).catch(() => null)
      throw error
    }

    return {
      error: null,
      success: `${organization.name} was created with Clerk organization ID ${organization.id}.`,
      organizationId: organization.id,
    }
  } catch (error) {
    const message = getErrorMessage(error, 'Unable to provision the client in Clerk.')

    return {
      error: message,
      success: null,
      organizationId: null,
    }
  }
}

export async function inviteClientAdminAction(
  _previousState: InviteAdminState,
  formData: FormData,
): Promise<InviteAdminState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { ...initialMutationState, error: 'Only super admins can invite client admins.' }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const emailAddress = normalizeEmail(String(formData.get('emailAddress') || ''))

  if (!organizationId) {
    return { ...initialMutationState, error: 'Choose a client before sending an invite.' }
  }

  if (!emailAddress) {
    return { ...initialMutationState, error: 'Admin email is required.' }
  }

  const client = await getClerkManagementClient()

  try {
    const organization = await client.organizations.getOrganization({ organizationId })
    const existingUsers = await client.users.getUserList({
      emailAddress: [emailAddress],
      limit: 1,
    })
    const existingUser = existingUsers.data[0]

    if (existingUser) {
      const existingMemberships = await client.organizations.getOrganizationMembershipList({
        organizationId,
        userId: [existingUser.id],
        limit: 1,
      })
      const existingMembership = existingMemberships.data[0]

      if (existingMembership) {
        if (existingMembership.role !== 'org:admin') {
          await client.organizations.updateOrganizationMembership({
            organizationId,
            userId: existingUser.id,
            role: 'org:admin',
          })
        }

        revalidatePath('/super-admin')
        revalidatePath(`/super-admin/customers/${organizationId}`)

        return {
          error: null,
          success:
            existingMembership.role === 'org:admin'
              ? `${emailAddress} already has admin access for ${organization.name}.`
              : `${emailAddress} was promoted to admin for ${organization.name}.`,
        }
      }

      await client.organizations.createOrganizationMembership({
        organizationId,
        userId: existingUser.id,
        role: 'org:admin',
      })

      revalidatePath('/super-admin')
      revalidatePath(`/super-admin/customers/${organizationId}`)

      return {
        error: null,
        success: `${emailAddress} was added to ${organization.name} as an admin.`,
      }
    }

    await client.organizations.createOrganizationInvitation({
      organizationId,
      emailAddress,
      role: 'org:admin',
    })

    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)

    return {
      error: null,
      success: `Admin invitation sent to ${emailAddress} for ${organization.name}.`,
    }
  } catch (error) {
    const message = getErrorMessage(error, 'Unable to send the admin invitation.')

    return {
      error: message,
      success: null,
    }
  }
}

export async function removeClientAdminAction(
  _previousState: RemoveAdminState,
  formData: FormData,
): Promise<RemoveAdminState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can remove client admins.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const userId = String(formData.get('userId') || '').trim()

  if (!organizationId || !userId) {
    return { error: 'Organization and user are required.', success: null }
  }

  const client = await getClerkManagementClient()

  try {
    const organization = await client.organizations.getOrganization({ organizationId })

    await client.organizations.deleteOrganizationMembership({
      organizationId,
      userId,
    })

    revalidatePath('/super-admin')

    return {
      error: null,
      success: `Removed admin access from ${organization.name}.`,
    }
  } catch (error) {
    const message = getErrorMessage(error, 'Unable to remove the client admin.')

    return {
      error: message,
      success: null,
    }
  }
}

export async function setCustomerActiveStateAction(
  _previousState: CustomerMutationState,
  formData: FormData,
): Promise<CustomerMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can update jurisdiction status.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const customerName = String(formData.get('customerName') || '').trim()
  const isActive = String(formData.get('isActive') || '').trim() === 'true'

  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  try {
    await updateTenantClientStatus(organizationId, isActive)
    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)

    return {
      error: null,
      success: `${customerName || 'Jurisdiction'} was set ${isActive ? 'active' : 'inactive'}.`,
    }
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to update the jurisdiction status.'),
      success: null,
    }
  }
}

export async function deleteCustomerAction(
  _previousState: CustomerMutationState,
  formData: FormData,
): Promise<CustomerMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can delete jurisdictions.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const customerName = String(formData.get('customerName') || '').trim()

  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  const client = await getClerkManagementClient()

  try {
    await client.organizations.deleteOrganization(organizationId)
    await deleteTenantClientRecord(organizationId)
    revalidatePath('/super-admin')
    redirect(`/super-admin?status=customer-deleted&customerName=${encodeURIComponent(customerName || 'Jurisdiction')}`)
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to delete the jurisdiction.'),
      success: null,
    }
  }
}

export async function fetchAdminEmailTemplatesAction(): Promise<AdminEmailTemplatesPayload> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(buildBackendApiUrl(`/api/admin/email-templates?${params.toString()}`), {
    cache: 'no-store',
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to load customer email templates.',
    )
  }

  return (await response.json()) as AdminEmailTemplatesPayload
}

export async function fetchAdminFeeStructureAction(): Promise<AdminFeeStructurePayload> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(buildBackendApiUrl(`/api/admin/fees/structure?${params.toString()}`), {
    cache: 'no-store',
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to load the jurisdiction fee structure.',
    )
  }

  return (await response.json()) as AdminFeeStructurePayload
}

export async function fetchAdminHomePageContentAction(): Promise<AdminHomePagePayload> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(buildBackendApiUrl(`/api/admin/home-page-content?${params.toString()}`), {
    cache: 'no-store',
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to load the jurisdiction home page content.',
    )
  }

  return (await response.json()) as AdminHomePagePayload
}

export async function saveAdminFeeStructureAction(input: {
  name: string
  items: Array<{
    code: string
    name: string
    category: string
    fee_type: string
    description: string
    amount_cents: number
    currency: string
    applies_to_letter_type: string | null
    applies_to_processing_type: string | null
    applies_to_delivery_method: string | null
    tax_mode: string | null
    charge_unit: string | null
    display_order: number
    is_active: boolean
    metadata_json: Record<string, string | number | boolean | null>
  }>
}): Promise<{ success: string; payload: AdminFeeStructurePayload }> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(buildBackendApiUrl(`/api/admin/fees/structure?${params.toString()}`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to save the fee structure.',
    )
  }

  revalidatePath('/admin')
  revalidatePath('/admin/fee-structure')

  return {
    success: 'Fee structure saved.',
    payload: (await response.json()) as AdminFeeStructurePayload,
  }
}

export async function saveAdminHomePageContentAction(input: AdminHomePagePayload['content']): Promise<{
  success: string
  payload: AdminHomePagePayload
}> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(buildBackendApiUrl(`/api/admin/home-page-content?${params.toString()}`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(input),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to save the jurisdiction home page content.',
    )
  }

  revalidatePath('/admin')
  revalidatePath('/admin/home-page')
  revalidatePath('/')

  return {
    success: 'Home page content saved.',
    payload: (await response.json()) as AdminHomePagePayload,
  }
}

export async function saveAdminEmailTemplateOverrideAction(input: {
  code: string
  name: string
  description: string
  category: string
  subject_template: string
  body_template: string
  status: 'draft' | 'active' | 'inactive'
}): Promise<{ success: string; template: AdminEmailTemplate }> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(
    buildBackendApiUrl(
      `/api/admin/email-templates/${encodeURIComponent(input.code)}?${params.toString()}`,
    ),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(input),
    },
  )

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to save email template.',
    )
  }

  revalidatePath('/admin')
  revalidatePath('/admin/email-settings')

  return {
    success: 'Email template override saved.',
    template: (await response.json()) as AdminEmailTemplate,
  }
}

export async function resetAdminEmailTemplateOverrideAction(code: string): Promise<{ success: string }> {
  const target = await getAdminScopedTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(
    buildBackendApiUrl(
      `/api/admin/email-templates/${encodeURIComponent(code)}/override?${params.toString()}`,
    ),
    {
      method: 'DELETE',
    },
  )

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to reset the email template override.',
    )
  }

  revalidatePath('/admin')
  revalidatePath('/admin/email-settings')

  return { success: 'Jurisdiction override removed. Gridics default restored.' }
}
