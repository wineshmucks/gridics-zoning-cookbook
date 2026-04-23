export const CUSTOMER_ZONING_ASSISTANT_TARGET_ID = 'customer-zoning-agent'
export const LEGACY_CUSTOMER_ZONING_ASSISTANT_TARGET_ID = 'customer_zoning_team'
export const PUBLIC_CUSTOMER_ZONING_ASSISTANT_TARGET_ID = 'customer-zoning-team'
export const DEFAULT_ASSISTANT_TARGET_ID =
  process.env.NEXT_PUBLIC_ASSISTANT_TARGET_ID?.trim() || CUSTOMER_ZONING_ASSISTANT_TARGET_ID

export const ASSISTANT_TARGET_ID_ALIASES: Record<string, string> = {
  [LEGACY_CUSTOMER_ZONING_ASSISTANT_TARGET_ID]: CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
  [PUBLIC_CUSTOMER_ZONING_ASSISTANT_TARGET_ID]: CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
}

export const ASSISTANT_MODEL_PROVIDER_OPTIONS = [
  { value: '', label: 'Use code default' },
  { value: 'gemini', label: 'Gemini' },
] as const

export function normalizeAssistantTargetId(targetId: string) {
  return ASSISTANT_TARGET_ID_ALIASES[targetId] || targetId
}

export function getAssistantTargetRouteKind(targetId: string) {
  const normalized = normalizeAssistantTargetId(targetId)
  return normalized.endsWith('_team') ? 'teams' : 'agents'
}

export function normalizeAssistantModelProvider(provider: string | null | undefined) {
  const normalized = provider?.trim().toLowerCase() || ''
  return normalized === 'gemini' ? 'gemini' : null
}
