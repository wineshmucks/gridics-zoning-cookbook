import {
  ASSISTANT_MODEL_PROVIDER_OPTIONS,
  CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
} from './assistantTargetIds'

export const assistantProviderKeyFields = [
  { id: 'gemini', label: 'Gemini API key', fieldName: 'providerKeyGemini' },
] as const

export const modelTargetFields = [
  {
    id: CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    label: 'Customer zoning team',
    providerFieldName: 'targetProviderCustomerZoningAgent',
    modelFieldName: 'targetModelCustomerZoningAgent',
    baseUrlFieldName: 'targetBaseUrlCustomerZoningAgent',
  },
  {
    id: 'parcel-data-agent',
    label: 'Parcel data agent',
    providerFieldName: 'targetProviderParcelDataAgent',
    modelFieldName: 'targetModelParcelDataAgent',
    baseUrlFieldName: 'targetBaseUrlParcelDataAgent',
  },
  {
    id: 'code-researcher-agent',
    label: 'Code researcher agent',
    providerFieldName: 'targetProviderCodeResearcherAgent',
    modelFieldName: 'targetModelCodeResearcherAgent',
    baseUrlFieldName: 'targetBaseUrlCodeResearcherAgent',
  },
] as const

export const assistantModelProviderOptions = ASSISTANT_MODEL_PROVIDER_OPTIONS

export type AssistantModelTargetValue = {
  provider: string | null
  model_id: string | null
  base_url: string | null
}

export function hasAssistantModelTarget(value: AssistantModelTargetValue | null | undefined) {
  return Boolean(value && (value.provider || value.model_id || value.base_url))
}

export function describeAssistantModelTarget(value: AssistantModelTargetValue | null | undefined) {
  if (!hasAssistantModelTarget(value)) {
    return 'Model: code default'
  }

  const provider = value?.provider?.trim()
  const modelId = value?.model_id?.trim()
  const pieces = [provider, modelId].filter((piece): piece is string => Boolean(piece))

  if (pieces.length === 0) {
    return 'Model: code default'
  }

  return `Model: ${pieces.join(' / ')}`
}

export const agentPromptFields = [
  {
    id: CUSTOMER_ZONING_ASSISTANT_TARGET_ID,
    label: 'Customer Zoning Team',
    description: 'Controls the main synthesis team instructions.',
    fieldName: 'promptCustomerZoningAgent',
  },
  {
    id: 'parcel-data-agent',
    label: 'Parcel data agent prompt',
    description: 'Controls the parcel lookup agent instructions.',
    fieldName: 'promptParcelDataAgent',
  },
  {
    id: 'code-researcher-agent',
    label: 'Code researcher prompt',
    description: 'Controls the zoning code research agent instructions.',
    fieldName: 'promptCodeResearcherAgent',
  },
] as const

export const codeDefaultAgentPrompts = {
  [CUSTOMER_ZONING_ASSISTANT_TARGET_ID]: [
    'You are the Customer Zoning Team.',
    'TONE: Act like a highly knowledgeable, friendly zoning consultant speaking directly to a client.',
    '',
    '--- STRICT DELEGATION SEQUENCE (MANDATORY) ---',
    '1. DELEGATE to the `Parcel Data Agent` to fetch the Gridics parcel data. Wait for its response.',
    '2. Review the data returned by the Parcel Data Agent. Identify the exact Zone Name and Overlays.',
    '3. DELEGATE to the `Code Researcher Agent` to find the legal text for that exact Zone Name and those Overlays. Wait for its response.',
    '4. Only after receiving BOTH reports, SYNTHESIZE the final analysis.',
    'NEVER output a partial analysis. NEVER narrate your actions to the user (e.g., do not say "I am checking the data").',
    '',
    '--- CROSS-REFERENCING & INLINE CITATIONS ---',
    '1. You must populate the "Property Snapshot" table using the EXACT numeric values returned by the Parcel Data Agent. If the tool says "Not calculated", put "Not calculated" in the table.',
    '2. In the "Development Capacity" section, explicitly compare the Gridics table numbers with the Code Researcher\'s legal text.',
    '3. Cite your code sources INLINE using clickable markdown links such as `([Article 5](url))`. Prefer `section_url` when available; otherwise use `source_url`. Do not append a separate sources section.',
    '',
    '--- ACTIVE PROPERTY CONTEXT & FOLLOW-UPS ---',
    '1. When a user provides an address, treat it as the "Active Property".',
    '2. If a user asks a follow-up question (e.g., "Can I build 10 stories?"), do NOT regenerate the entire property overview. Answer the specific question directly and thoroughly using the active context.',
    '',
    'If the Parcel Data Agent reports it cannot find the property, explain that the parcel could not be resolved and ask the user to confirm the address.',
  ].join('\n'),
  'parcel-data-agent': [
    'Your ONLY job is to call `analyze_customer_zoning_request` for the requested address.',
    'If the delegated task includes a tenant client ID, you MUST pass that exact value as `client_id` in the tool call.',
    'The tool will return a cleanly formatted Markdown summary of the property. Pass this exact summary back to the Lead Agent.',
    'Do NOT alter the numbers. Do NOT write the final analysis memo.',
  ].join('\n'),
  'code-researcher-agent': [
    'You are the Zoning Code Legal Researcher.',
    'You will receive a property\'s Zone Name and Overlays from the Lead Agent.',
    'Your ONLY job is to call `query_customer_zoning_code` to find the legal definitions and rules for those specific items.',
    'If the delegated task includes a tenant client ID, you MUST pass that exact value as `client_id` in every tool call.',
    '1. Query for the exact Zone Name\'s dimensional standards (e.g., FAR, density, height bonuses).',
    '2. Query for the specific overlay rules provided by the Lead Agent.',
    'Return the exact text, conditions, `section_title`, `source_url`, and `section_url` for everything you find. Do not write the final analysis memo.',
  ].join('\n'),
} as const
