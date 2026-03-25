'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'

import { getServerBackendOrigin } from '../../lib/backend'
import { DEFAULT_ASSISTANT_DISCLAIMER_TEXT } from '../../lib/assistant-disclaimer'
import { getCurrentOrgId } from '../../lib/org-context'
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
  redirectPath?: string | null
}

export type CustomerRecord = {
  id: string
  client_id: string
  clerk_organization_id: string | null
  jurisdiction_id: string | null
  city_name: string
  department_name: string
  is_active: boolean
  settings_json?: {
    header_logo_path?: string | null
    [key: string]: unknown
  } | null
}

export type CustomerExperienceSettingsState = {
  error: string | null
  success: string | null
  settings: CustomerExperienceSettings | null
}

export type CustomerExperienceSettings = {
  zoning_code_url: string | null
  assistant_disclaimer_text: string
  assistant_provider_keys: Record<string, string | null>
  assistant_model_targets: Record<
    string,
    {
      provider: string | null
      model_id: string | null
      base_url: string | null
    }
  >
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

export type SuperAdminGridicsDebugState = {
  error: string | null
  success: string | null
  request: {
    inputAddress: string
    normalizedAddress: string | null
    stateEnv: string | null
    zipCode: string | null
  } | null
  response: unknown | null
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
  redirectPath: null,
}

const initialCustomerExperienceSettingsState: CustomerExperienceSettingsState = {
  error: null,
  success: null,
  settings: null,
}

const initialCustomerZoningKnowledgeMutationState: CustomerZoningKnowledgeMutationState = {
  error: null,
  success: null,
}

const initialSuperAdminGridicsDebugState: SuperAdminGridicsDebugState = {
  error: null,
  success: null,
  request: null,
  response: null,
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
    assistant_disclaimer_text: DEFAULT_ASSISTANT_DISCLAIMER_TEXT,
    assistant_provider_keys: {
      gemini: null,
      openrouter: null,
      openai: null,
      groq: null,
    },
    assistant_model_targets: {},
  }
}

function normalizeCustomerExperienceSettings(payload: unknown): CustomerExperienceSettings {
  const fallback = buildEmptyCustomerExperienceSettings()
  if (!payload || typeof payload !== 'object') {
    return fallback
  }

  const record = payload as Record<string, unknown>
  const providerKeysInput =
    record.assistant_provider_keys && typeof record.assistant_provider_keys === 'object'
      ? (record.assistant_provider_keys as Record<string, unknown>)
      : {}
  const modelTargetsInput =
    record.assistant_model_targets && typeof record.assistant_model_targets === 'object'
      ? (record.assistant_model_targets as Record<string, unknown>)
      : {}

  const assistant_provider_keys: CustomerExperienceSettings['assistant_provider_keys'] = {
    gemini: typeof providerKeysInput.gemini === 'string' ? providerKeysInput.gemini : null,
    openrouter: typeof providerKeysInput.openrouter === 'string' ? providerKeysInput.openrouter : null,
    openai: typeof providerKeysInput.openai === 'string' ? providerKeysInput.openai : null,
    groq: typeof providerKeysInput.groq === 'string' ? providerKeysInput.groq : null,
  }

  const assistant_model_targets: CustomerExperienceSettings['assistant_model_targets'] = {}
  for (const [targetId, rawTarget] of Object.entries(modelTargetsInput)) {
    if (!rawTarget || typeof rawTarget !== 'object') {
      continue
    }

    const target = rawTarget as Record<string, unknown>
    assistant_model_targets[targetId] = {
      provider: typeof target.provider === 'string' ? target.provider : null,
      model_id: typeof target.model_id === 'string' ? target.model_id : null,
      base_url: typeof target.base_url === 'string' ? target.base_url : null,
    }
  }

  return {
    zoning_code_url: typeof record.zoning_code_url === 'string' ? record.zoning_code_url : null,
    assistant_disclaimer_text:
      typeof record.assistant_disclaimer_text === 'string' && record.assistant_disclaimer_text.trim()
        ? record.assistant_disclaimer_text.trim()
        : fallback.assistant_disclaimer_text,
    assistant_provider_keys,
    assistant_model_targets,
  }
}

const backendOrigin = getServerBackendOrigin()

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

function standardizePropertyAddress(address: string) {
  const withoutUnit = address.replace(
    /\b(?:apt|apartment|unit|suite|ste|#)\s*[\w-]+\b/gi,
    '',
  )
  return withoutUnit.replace(/\s*,\s*/g, ', ').replace(/\s+/g, ' ').trim().replace(/,$/, '')
}

function inferStateEnvFromAddress(address: string) {
  const match = address.match(/\b([A-Z]{2})\b(?:\s+\d{5}(?:-\d{4})?)?$/i)
  return match ? match[1].toLowerCase() : null
}

function inferZipFromAddress(address: string) {
  const match = address.match(/\b(\d{5})(?:-\d{4})?\b/)
  return match ? match[1] : null
}

function extractGridicsStreetAddress(address: string) {
  const parts = address
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)

  if (parts.length >= 2) {
    return parts[0]
  }

  return address
    .replace(/\b([A-Z]{2})\b(?:\s+\d{5}(?:-\d{4})?)?$/i, '')
    .replace(/,\s*$/, '')
    .trim()
}

async function getAdminScopedTarget() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.canAccessAdminScreens) {
    throw new Error('You need admin access for the selected jurisdiction organization.')
  }

  let organizationId =
    permissions.selectedAdminMembership?.organizationId ||
    permissions.currentClientMembership?.organizationId ||
    null
  let clientId =
    permissions.selectedAdminMembership?.clientId ||
    permissions.currentClientId ||
    null

  if (!organizationId) {
    organizationId = await getCurrentOrgId()
  }

  if (!clientId && organizationId) {
    const customerRecord = await fetchCustomerRecord(organizationId)
    clientId = customerRecord?.client_id || organizationId
  }

  if (!organizationId && !clientId) {
    throw new Error('Unable to resolve the current jurisdiction context.')
  }

  return { organizationId, clientId }
}

export async function runSuperAdminGridicsDebugAction(
  _previousState: SuperAdminGridicsDebugState,
  formData: FormData,
): Promise<SuperAdminGridicsDebugState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
    return {
      ...initialSuperAdminGridicsDebugState,
      error: 'Only super admins can use the Gridics debug tool.',
    }
  }

  const inputAddress = String(formData.get('address') || '').trim()
  if (!inputAddress) {
    return {
      ...initialSuperAdminGridicsDebugState,
      error: 'A full property address is required.',
    }
  }

  const normalizedAddress = standardizePropertyAddress(inputAddress)
  const stateEnv = inferStateEnvFromAddress(normalizedAddress)
  const zipCode = inferZipFromAddress(normalizedAddress)
  const address = extractGridicsStreetAddress(normalizedAddress)

  if (!stateEnv || !zipCode) {
    return {
      ...initialSuperAdminGridicsDebugState,
      error: 'Include a full US address with state abbreviation and 5-digit ZIP code.',
      request: {
        inputAddress,
        normalizedAddress,
        stateEnv,
        zipCode,
      },
    }
  }

  try {
    const params = new URLSearchParams({
      state_env: stateEnv,
      address,
      zipCode,
    })
    const response = await fetch(buildBackendApiUrl(`/api/gridics/property-record?${params.toString()}`), {
      cache: 'no-store',
    })
    const payload = await response.json().catch(() => null)

    if (!response.ok) {
      const detail =
        typeof payload?.detail === 'string'
          ? payload.detail
          : 'Unable to load the Gridics property record.'
      return {
        error: detail,
        success: null,
        request: {
          inputAddress,
          normalizedAddress: address,
          stateEnv,
          zipCode,
        },
        response: payload,
      }
    }

    return {
      error: null,
      success: 'Gridics response loaded.',
      request: {
        inputAddress,
        normalizedAddress: address,
        stateEnv,
        zipCode,
      },
      response: payload,
    }
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to load the Gridics property record.'),
      success: null,
      request: {
        inputAddress,
        normalizedAddress: address,
        stateEnv,
        zipCode,
      },
      response: null,
    }
  }
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
  const existingRecord = await fetchCustomerRecord(organizationId)
  if (existingRecord) {
    return
  }

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

async function updateTenantClientGeneralDetails(
  organizationId: string,
  payload: {
    clientId: string
    cityName: string
    departmentName: string
    clerkOrganizationId: string
    pathAlias: string | null
  },
) {
  const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}`), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      client_id: payload.clientId,
      city_name: payload.cityName,
      department_name: payload.departmentName,
      clerk_organization_id: payload.clerkOrganizationId,
      path_alias: payload.pathAlias,
    }),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to update jurisdiction details.',
    )
  }
}

async function uploadTenantClientLogo(organizationId: string, logoFile: File) {
  const formData = new FormData()
  formData.set('file', logoFile)

  const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}/logo`), {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to upload jurisdiction logo.',
    )
  }
}

async function removeTenantClientLogo(organizationId: string) {
  const response = await fetch(buildBackendApiUrl(`/api/admin/clients/${organizationId}/logo`), {
    method: 'DELETE',
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(
      typeof payload?.detail === 'string' ? payload.detail : 'Unable to remove jurisdiction logo.',
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

    return normalizeCustomerExperienceSettings(await response.json())
  } catch {
    return buildEmptyCustomerExperienceSettings()
  }
}

export async function saveCustomerExperienceSettingsAction(
  _previousState: CustomerExperienceSettingsState,
  formData: FormData,
): Promise<CustomerExperienceSettingsState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
    return {
      ...initialCustomerExperienceSettingsState,
      error: 'Only super admins can update assistant settings.',
    }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const zoningCodeUrl = String(formData.get('zoningCodeUrl') || '').trim()
  const assistantDisclaimerText = String(formData.get('assistantDisclaimerText') || '').trim()
  const assistantProviderKeys = {
    gemini: String(formData.get('providerKeyGemini') || '').trim() || null,
    openrouter: String(formData.get('providerKeyOpenrouter') || '').trim() || null,
    openai: String(formData.get('providerKeyOpenai') || '').trim() || null,
    groq: String(formData.get('providerKeyGroq') || '').trim() || null,
  }
  const assistantModelTargets = {
    'customer-zoning-agent': {
      provider: String(formData.get('targetProviderCustomerZoningAgent') || '').trim() || null,
      model_id: String(formData.get('targetModelCustomerZoningAgent') || '').trim() || null,
      base_url: String(formData.get('targetBaseUrlCustomerZoningAgent') || '').trim() || null,
    },
    'parcel-data-agent': {
      provider: String(formData.get('targetProviderParcelDataAgent') || '').trim() || null,
      model_id: String(formData.get('targetModelParcelDataAgent') || '').trim() || null,
      base_url: String(formData.get('targetBaseUrlParcelDataAgent') || '').trim() || null,
    },
    'code-researcher-agent': {
      provider: String(formData.get('targetProviderCodeResearcherAgent') || '').trim() || null,
      model_id: String(formData.get('targetModelCodeResearcherAgent') || '').trim() || null,
      base_url: String(formData.get('targetBaseUrlCodeResearcherAgent') || '').trim() || null,
    },
  }

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
          assistant_disclaimer_text: assistantDisclaimerText || null,
          assistant_provider_keys: assistantProviderKeys,
          assistant_model_targets: assistantModelTargets,
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

    const savedSettings = normalizeCustomerExperienceSettings(await response.json())

    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    revalidatePath(`/super-admin/customers/${organizationId}/assistant-setup`)
    revalidatePath(`/super-admin/customers/${organizationId}/assistant`)
    revalidatePath('/assistant')
    revalidatePath('/')

    return {
      error: null,
      success: 'Jurisdiction assistant settings saved.',
      settings: savedSettings,
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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

export async function saveCustomerGeneralSettingsAction(
  _previousState: CustomerMutationState,
  formData: FormData,
): Promise<CustomerMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
    return { error: 'Only super admins can update jurisdiction details.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const clientId = String(formData.get('clientId') || '').trim()
  const cityName = String(formData.get('cityName') || '').trim()
  const departmentName = String(formData.get('departmentName') || '').trim()
  const clerkOrganizationId = String(formData.get('clerkOrganizationId') || '').trim()
  const pathAliasRaw = String(formData.get('pathAlias') || '').trim()
  const clerkSlugRaw = String(formData.get('clerkSlug') || '').trim()
  const clerkSlug = clerkSlugRaw || undefined
  const logoFile = formData.get('logoFile')

  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  if (!cityName) {
    return { error: 'Jurisdiction name is required.', success: null }
  }

  if (!clientId) {
    return { error: 'Organization ID is required.', success: null }
  }

  if (!departmentName) {
    return { error: 'Department name is required.', success: null }
  }

  if (!clerkOrganizationId) {
    return { error: 'Clerk organization ID is required.', success: null }
  }

  try {
    await ensureTenantClientRecord(organizationId)
    const client = await getClerkManagementClient()
    await client.organizations.getOrganization({ organizationId: clerkOrganizationId })
    await client.organizations.updateOrganization(clerkOrganizationId, {
      name: cityName,
      slug: clerkSlug,
    })
    await updateTenantClientGeneralDetails(organizationId, {
      clientId,
      cityName,
      departmentName,
      clerkOrganizationId,
      pathAlias: pathAliasRaw || null,
    })
    if (logoFile instanceof File && logoFile.size > 0) {
      await uploadTenantClientLogo(organizationId, logoFile)
    }
    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    revalidatePath(`/super-admin/customers/${clerkOrganizationId}`)
    revalidatePath(`/super-admin/customers/${organizationId}/assistant-setup`)
    revalidatePath(`/super-admin/customers/${organizationId}/assistant`)
    revalidatePath(`/super-admin/customers/${clerkOrganizationId}/assistant-setup`)
    revalidatePath(`/super-admin/customers/${clerkOrganizationId}/assistant`)

    return {
      error: null,
      success: `${cityName} details were saved.`,
      redirectPath:
        clientId !== organizationId
          ? `/super-admin/customers/${clientId}`
          : clerkOrganizationId !== organizationId
            ? `/super-admin/customers/${clerkOrganizationId}`
            : null,
    }
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to update jurisdiction details.'),
      success: null,
      redirectPath: null,
    }
  }
}

export async function removeCustomerLogoAction(
  _previousState: CustomerMutationState,
  formData: FormData,
): Promise<CustomerMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
    return { error: 'Only super admins can remove jurisdiction logos.', success: null }
  }

  const organizationId = String(formData.get('organizationId') || '').trim()
  const customerName = String(formData.get('customerName') || '').trim()

  if (!organizationId) {
    return { error: 'Organization is required.', success: null }
  }

  try {
    await removeTenantClientLogo(organizationId)
    revalidatePath('/super-admin')
    revalidatePath(`/super-admin/customers/${organizationId}`)
    revalidatePath(`/super-admin/customers/${organizationId}/assistant-setup`)
    revalidatePath(`/super-admin/customers/${organizationId}/assistant`)

    return {
      error: null,
      success: `${customerName || 'Jurisdiction'} logo was removed.`,
    }
  } catch (error) {
    return {
      error: getErrorMessage(error, 'Unable to remove jurisdiction logo.'),
      success: null,
    }
  }
}

export async function deleteCustomerAction(
  _previousState: CustomerMutationState,
  formData: FormData,
): Promise<CustomerMutationState> {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)
  const permissions = await getPermissionContext(clerkEnabled)

  if (!permissions.isSuperAdmin) {
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
