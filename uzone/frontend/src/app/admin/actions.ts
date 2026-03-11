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

const backendApiBase =
  process.env.UZONE_API_BASE || process.env.NEXT_PUBLIC_UZONE_API_BASE || 'http://localhost:8000'

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

async function getAdminEmailTemplateTarget() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.canAccessAdminScreens) {
    throw new Error('You need admin access for the selected customer organization.')
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
    throw new Error('Unable to resolve the current customer context.')
  }

  return { organizationId, clientId }
}

async function createTenantClientRecord(clientName: string, organizationId: string) {
  const response = await fetch(`${backendApiBase}/api/admin/clients`, {
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

async function updateTenantClientStatus(organizationId: string, isActive: boolean) {
  const response = await fetch(`${backendApiBase}/api/admin/clients/${organizationId}`, {
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
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to update customer status.',
    )
  }
}

async function deleteTenantClientRecord(organizationId: string) {
  const response = await fetch(`${backendApiBase}/api/admin/clients/${organizationId}`, {
    method: 'DELETE',
  })

  if (response.status === 404) {
    return
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to delete customer record.',
    )
  }
}

export async function fetchCustomerExperienceSettings(
  organizationId: string,
): Promise<CustomerExperienceSettings> {
  const response = await fetch(
    `${backendApiBase}/api/admin/clients/${organizationId}/experience-settings`,
    {
      cache: 'no-store',
    },
  )

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string'
        ? payload.detail
        : 'Unable to load customer assistant settings.',
    )
  }

  return (await response.json()) as CustomerExperienceSettings
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
    const response = await fetch(
      `${backendApiBase}/api/admin/clients/${organizationId}/experience-settings`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          zoning_code_url: zoningCodeUrl || null,
        }),
      },
    )

    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(
        typeof payload?.detail === 'string'
          ? payload.detail
          : 'Unable to save customer assistant settings.',
      )
    }

    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    revalidatePath('/assistant')
    revalidatePath('/')

    return {
      error: null,
      success: 'Customer assistant settings saved.',
    }
  } catch (error) {
    return {
      ...initialCustomerExperienceSettingsState,
      error: getErrorMessage(error, 'Unable to save customer assistant settings.'),
    }
  }
}

export async function fetchCustomerZoningKnowledgeStatus(
  organizationId: string,
): Promise<CustomerZoningKnowledgeStatus> {
  try {
    const response = await fetch(`${backendApiBase}/api/admin/clients/${organizationId}/zoning-knowledge`, {
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
    `${backendApiBase}/api/admin/clients/${organizationId}/zoning-knowledge/ingest`,
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
      `${backendApiBase}/api/admin/clients/${organizationId}/zoning-knowledge/query`,
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
    return { ...initialProvisionState, error: 'Customer name is required.' }
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

export async function setCustomerInactiveAction(
  _previousState: CustomerMutationState,
  formData: FormData,
): Promise<CustomerMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const { role } = await getPermissionContext(clerkEnabled)

  if (role !== 'super_admin') {
    return { error: 'Only super admins can set customers inactive.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const customerName = String(formData.get('customerName') || '').trim()

  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  try {
    await updateTenantClientStatus(organizationId, false)
    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)

    return {
      error: null,
      success: `${customerName || 'Customer'} was set inactive.`,
    }
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to set the customer inactive.'),
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
    return { error: 'Only super admins can delete customers.', success: null }
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
    redirect(`/super-admin?status=customer-deleted&customerName=${encodeURIComponent(customerName || 'Customer')}`)
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to delete the customer.'),
      success: null,
    }
  }
}

export async function fetchAdminEmailTemplatesAction(): Promise<AdminEmailTemplatesPayload> {
  const target = await getAdminEmailTemplateTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(`${backendApiBase}/api/admin/email-templates?${params.toString()}`, {
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

export async function saveAdminEmailTemplateOverrideAction(input: {
  code: string
  name: string
  description: string
  category: string
  subject_template: string
  body_template: string
  status: 'draft' | 'active' | 'inactive'
}): Promise<{ success: string; template: AdminEmailTemplate }> {
  const target = await getAdminEmailTemplateTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(
    `${backendApiBase}/api/admin/email-templates/${encodeURIComponent(input.code)}?${params.toString()}`,
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
  const target = await getAdminEmailTemplateTarget()
  const params = new URLSearchParams()

  if (target.organizationId) {
    params.set('organization_id', target.organizationId)
  }
  if (target.clientId) {
    params.set('client_id', target.clientId)
  }

  const response = await fetch(
    `${backendApiBase}/api/admin/email-templates/${encodeURIComponent(code)}/override?${params.toString()}`,
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

  return { success: 'Customer override removed. Gridics default restored.' }
}
