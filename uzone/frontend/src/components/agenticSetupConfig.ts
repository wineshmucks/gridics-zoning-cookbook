export const providerFields = [
  { id: 'gemini', label: 'Gemini API key', fieldName: 'providerKeyGemini' },
  { id: 'openrouter', label: 'OpenRouter API key', fieldName: 'providerKeyOpenrouter' },
  { id: 'openai', label: 'OpenAI API key', fieldName: 'providerKeyOpenai' },
  { id: 'groq', label: 'Groq API key', fieldName: 'providerKeyGroq' },
] as const

export const modelTargetFields = [
  {
    id: 'customer-zoning-agent',
    label: 'Lead team',
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

export const agentPromptFields = [
  {
    id: 'customer-zoning-agent',
    label: 'Lead team prompt',
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
