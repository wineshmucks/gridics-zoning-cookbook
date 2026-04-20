'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getAssistantContent, getAssistantContentDebug, normalizeContent, sanitizeAssistantContent } from '../lib/agentRunContent'
import { buildAssistantApiUrl } from '../lib/assistant-api'

type AgentRunResponse = {
  session_id?: string
  run_id?: string
  content?: unknown
  response?: unknown
  run_response?: unknown
  data?: unknown
  debug?: unknown
  messages?: Array<{
    role?: string
    content?: unknown
  }>
}

type CompletedRunFetchResult = {
  payload: AgentRunResponse | null
  debug: string | null
}

type StreamStepStatus = 'running' | 'complete' | 'error'

type StreamStep = {
  id: string
  label: string
  detail?: string
  status: StreamStepStatus
}

type StreamToolCall = {
  id: string
  label: string
  toolName?: string
  detail?: string
  status: StreamStepStatus
  rawResult?: unknown
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  steps?: StreamStep[]
  toolCalls?: StreamToolCall[]
  runId?: string
  status?: 'streaming' | 'complete' | 'error'
  error?: string | null
}

type MessageFeedback = 'up' | 'down'

function CopyIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="5" y="3" width="8" height="10" rx="1.8" />
      <path d="M3.5 10.5H3A1.5 1.5 0 0 1 1.5 9V4A1.5 1.5 0 0 1 3 2.5h5" />
    </svg>
  )
}

function ThumbUpIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6.5 6 8.9 2.8c.3-.4.9-.3 1 .2l.2 2c.1.7.6 1.2 1.3 1.2h1.4c.9 0 1.6.8 1.4 1.7l-.8 4A1.8 1.8 0 0 1 11.6 13H6.5" />
      <path d="M2 6h2.5v7H2z" />
    </svg>
  )
}

function ThumbDownIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.5 10 7.1 13.2c-.3.4-.9.3-1-.2l-.2-2c-.1-.7-.6-1.2-1.3-1.2H3.2c-.9 0-1.6-.8-1.4-1.7l.8-4A1.8 1.8 0 0 1 4.4 3H9.5" />
      <path d="M12 3h2.5v7H12z" />
    </svg>
  )
}

function TimelineIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M3 3.5v9" />
      <path d="M8 3.5v9" />
      <path d="M13 3.5v9" />
      <path d="M1.5 6h3" />
      <path d="M6.5 10h3" />
      <path d="M11.5 5h3" />
    </svg>
  )
}

function ToolsIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6.5 3.5a2 2 0 1 0-2.8 1.8L8 9.6l1.6-1.6-4.2-4.2A2 2 0 0 0 6.5 3.5Z" />
      <path d="m9.5 6.5 2.8-2.8 1.5 1.5-2.8 2.8" />
      <path d="M8.4 9.6 5 13l-2-2 3.4-3.4" />
    </svg>
  )
}

const SUGGESTED_PROMPTS = [
  'What can I build on this lot?',
  'What are the setback requirements?',
  'Is an ADU allowed here?',
  'What parking is required?',
  'Explain this zoning district',
  'What overlays apply?',
]

type SSEEvent = {
  event: string
  data: Record<string, unknown>
}

type AssistantModelTraceEntry = {
  provider?: string | null
  model_id?: string | null
  api_key_source?: string | null
  api_key_suffix?: string | null
  reason?: string | null
}

type ConversationCopyContext = {
  agentId: string
  customerName: string
  defaultModelId: string
  modelId: string
  runId: string | null
  sessionId: string | null
  surface: string
}

type EmbedChatActions = {
  copyConversation: () => void
  newChat: () => void
}

type AssistantToolbarState = {
  title: string
  subtitle: string | null
  canCopy: boolean
  canNewChat: boolean
}

function summarizeToolResultForExport(rawResult: unknown): unknown {
  const parsed = unwrapToolResult(rawResult)
  if (!parsed || typeof parsed !== "object") {
    return parsed
  }

  const record = parsed as Record<string, unknown>
  return {
    ...record,
    rawResult: undefined,
  }
}

function buildConversationExport(messages: ChatMessage[], context: ConversationCopyContext): string {
  const timestamp = new Date().toISOString()
  const assistantCount = messages.filter((message) => message.role === "assistant").length

  const exportPayload = {
    metadata: {
      exported_at: timestamp,
      agent_id: context.agentId,
      customer_name: context.customerName,
      surface: context.surface,
      session_id: context.sessionId,
      run_id: context.runId,
      model_id: context.modelId || null,
      default_model_id: context.defaultModelId || null,
      model_override_active: Boolean(context.modelId && context.modelId.trim() && context.modelId.trim() !== context.defaultModelId.trim()),
      message_count: messages.length,
      assistant_message_count: assistantCount,
    },
    messages: messages.map((message, index) => ({
      index: index + 1,
      id: message.id,
      role: message.role,
      status: message.status || null,
      run_id: message.runId || null,
      content: message.content || "",
      steps: message.steps || [],
      tool_calls: (message.toolCalls || []).map((toolCall) => ({
        id: toolCall.id,
        label: toolCall.label,
        tool_name: toolCall.toolName || null,
        detail: toolCall.detail || null,
        status: toolCall.status,
        raw_result: summarizeToolResultForExport(toolCall.rawResult),
      })),
    })),
  }

  const lines: string[] = [
    "# UZone Conversation Export",
    "",
    "## Conversation Metadata",
    `- Exported at: ${timestamp}`,
    `- Agent: ${context.agentId}`,
    `- Customer: ${context.customerName}`,
    `- Surface: ${context.surface}`,
    `- Session ID: ${context.sessionId || "(none)"}`,
    `- Run ID: ${context.runId || "(none)"}`,
    `- Model: ${context.modelId || "(default)"}`,
    `- Default model: ${context.defaultModelId || "(none)"}`,
    `- Model override active: ${context.modelId.trim() && context.modelId.trim() !== context.defaultModelId.trim() ? "yes" : "no"}`,
    `- Messages: ${messages.length} total, ${assistantCount} assistant`,
    "",
  ]

  messages.forEach((message, index) => {
    const speaker = message.role === "user" ? "You" : `${context.customerName} Assistant`
    lines.push(`## Turn ${index + 1}: ${speaker}`)
    lines.push(`- Message ID: ${message.id}`)
    lines.push(`- Role: ${message.role}`)
    lines.push(`- Status: ${message.status || "unknown"}`)
    if (message.runId) {
      lines.push(`- Run ID: ${message.runId}`)
    }
    lines.push("")
    lines.push("### Content")
    lines.push(message.content || "(no visible message content)")

    if (message.toolCalls?.length) {
      lines.push("")
      lines.push("### Tool Activity")
      message.toolCalls.forEach((toolCall) => {
        lines.push(`- ${toolCall.label}${toolCall.detail ? `: ${toolCall.detail}` : ""} [${toolCall.status}]`)
      })
    }

    if (message.steps?.length) {
      lines.push("")
      lines.push("### Run Timeline")
      message.steps.forEach((step) => {
        lines.push(`- ${step.label}${step.detail ? `: ${step.detail}` : ""} [${step.status}]`)
      })
    }

    lines.push("")
  })

  lines.push("## Debug Bundle")
  lines.push("```json")
  lines.push(JSON.stringify(exportPayload, null, 2))
  lines.push("```")

  return lines.join("\n")
}

async function copyTextToClipboard(text: string): Promise<void> {
  if (
    typeof navigator !== "undefined" &&
    navigator.clipboard?.writeText &&
    typeof window !== "undefined" &&
    window.isSecureContext
  ) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Fall back to the legacy clipboard path when the browser blocks async clipboard writes.
    }
  }

  if (typeof document === "undefined") {
    throw new Error("Clipboard is not available in this environment.")
  }

  const textarea = document.createElement("textarea")
  textarea.value = text
  textarea.setAttribute("readonly", "true")
  textarea.style.position = "fixed"
  textarea.style.top = "-1000px"
  textarea.style.left = "-1000px"
  textarea.style.opacity = "0"
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()

  try {
    const successful = document.execCommand("copy")
    if (!successful) {
      throw new Error("Clipboard copy failed.")
    }
  } finally {
    document.body.removeChild(textarea)
  }
}

function parseSSEEvents(chunk: string): { events: SSEEvent[]; remainder: string } {
  const normalizedChunk = chunk.replace(/\r\n/g, "\n")
  const blocks = normalizedChunk.split("\n\n")
  const remainder = blocks.pop() ?? ""
  const events: SSEEvent[] = []

  for (const block of blocks) {
    const lines = block.split("\n")
    let event = "message"
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim()
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim())
      }
    }

    if (!dataLines.length) {
      continue
    }

    try {
      events.push({
        event,
        data: JSON.parse(dataLines.join("\n")) as Record<string, unknown>,
      })
    } catch {
      // Ignore malformed chunks rather than fail the whole run.
    }
  }

  return { events, remainder }
}

function eventMatches(eventName: string, expected: string): boolean {
  return eventName === expected || eventName === `Team${expected}`
}

function toStepLabel(toolName?: string): string {
  if (!toolName) {
    return "Working"
  }

  if (toolName === "query_customer_zoning_code") {
    return "Lookup knowledge"
  }

  return toolName
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function getAssistantModelTrace(payload: Record<string, unknown>): Record<string, AssistantModelTraceEntry> | null {
  const metadata = payload.metadata && typeof payload.metadata === "object"
    ? (payload.metadata as Record<string, unknown>)
    : null
  const rawTrace = metadata?.assistant_model_trace
  if (!rawTrace || typeof rawTrace !== "object") {
    return null
  }

  const entries: Record<string, AssistantModelTraceEntry> = {}
  for (const [targetId, rawEntry] of Object.entries(rawTrace as Record<string, unknown>)) {
    if (!rawEntry || typeof rawEntry !== "object") {
      continue
    }
    const entry = rawEntry as Record<string, unknown>
    entries[targetId] = {
      provider: typeof entry.provider === "string" ? entry.provider : null,
      model_id: typeof entry.model_id === "string" ? entry.model_id : null,
      api_key_source: typeof entry.api_key_source === "string" ? entry.api_key_source : null,
      api_key_suffix: typeof entry.api_key_suffix === "string" ? entry.api_key_suffix : null,
      reason: typeof entry.reason === "string" ? entry.reason : null,
    }
  }

  return Object.keys(entries).length ? entries : null
}

function formatAssistantModelTrace(payload: Record<string, unknown>): string | null {
  const trace = getAssistantModelTrace(payload)
  if (!trace) {
    return null
  }

  return Object.entries(trace)
    .map(([targetId, entry]) => {
      const parts = [
        targetId,
        entry.provider && entry.model_id ? `${entry.provider}/${entry.model_id}` : null,
        entry.api_key_source ? `key:${entry.api_key_source}` : null,
        entry.api_key_suffix ? `suffix:${entry.api_key_suffix}` : null,
        entry.reason ? `reason:${entry.reason}` : null,
      ].filter(Boolean)
      return parts.join(" | ")
    })
    .join(" || ")
}

function enrichRunStartedStepWithTrace(steps: StreamStep[], traceDetail: string | null): StreamStep[] {
  if (!traceDetail) {
    return steps
  }

  return steps.map((step) => {
    if (step.id !== "run-started") {
      return step
    }

    const detail = step.detail || ""
    if (detail.includes("key:") || detail.includes(traceDetail)) {
      return step
    }

    return {
      ...step,
      detail: detail ? `${detail} | ${traceDetail}` : traceDetail,
    }
  })
}

function buildTraceBanner(traceDetail: string | null): string {
  return traceDetail ? `Model trace: ${traceDetail}` : ""
}

function truncateMiddle(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value
  }

  const start = value.slice(0, Math.max(0, Math.floor((maxLength - 1) / 2))).trimEnd()
  const end = value.slice(-Math.max(0, Math.floor((maxLength - 2) / 2))).trimStart()
  return `${start}…${end}`
}

function humanizeAddress(value: string): string {
  return truncateMiddle(
    value
      .replace(/\s+/g, " ")
      .replace(/\bne\b/gi, "NE")
      .replace(/\bnw\b/gi, "NW")
      .replace(/\bse\b/gi, "SE")
      .replace(/\bsw\b/gi, "SW")
      .trim(),
    42,
  )
}

function summarizeQuery(value: string): string {
  return truncateMiddle(value.replace(/\s+/g, " ").trim(), 64)
}

function toStepDetail(tool: Record<string, unknown> | undefined): string | undefined {
  if (!tool) {
    return undefined
  }

  const toolName = typeof tool.tool_name === "string" ? tool.tool_name : ""
  const args = tool.tool_args
  if (!args || typeof args !== "object") {
    return undefined
  }

  const toolArgs = args as Record<string, unknown>
  const address = typeof toolArgs.address === "string" ? toolArgs.address.trim() : ""
  const query = typeof toolArgs.query === "string" ? toolArgs.query.trim() : ""
  const standardizedAddress =
    typeof toolArgs.standardized_address === "string" ? toolArgs.standardized_address.trim() : ""
  const zoneName = typeof toolArgs.zone_combination_name === "string" ? toolArgs.zone_combination_name.trim() : ""
  const typology = typeof toolArgs.typology === "string" ? toolArgs.typology.trim() : ""

  if (toolName === "analyze_customer_zoning_request" && address) {
    return `Resolving parcel for ${humanizeAddress(address)}`
  }

  if (toolName === "query_customer_zoning_code" && standardizedAddress) {
    return `Searching code for ${humanizeAddress(standardizedAddress)}`
  }

  if (toolName === "query_customer_zoning_code" && zoneName) {
    return typology ? `Searching ${zoneName} typology ${typology} standards` : `Searching ${zoneName} standards`
  }

  if (query) {
    if (toolName === "query_customer_zoning_code") {
      return `Searching knowledge: ${summarizeQuery(query)}`
    }
    return summarizeQuery(query)
  }

  const limit = typeof toolArgs.limit === "number" ? toolArgs.limit : null
  if (limit) {
    return `Searching top ${limit} matches`
  }

  return undefined
}

function summarizeToolResult(raw: unknown): string | undefined {
  try {
    const parsed = unwrapToolResult(raw) as {
      results?: unknown[]
      question_type?: string
      address_resolution?: { standardized_address?: string; lookup_ready?: boolean }
      gridics?: { zone_combination_name?: string; typology?: string }
    }
    if (parsed.question_type === "specific_address") {
      const address = parsed.address_resolution?.standardized_address
      const zone = parsed.gridics?.zone_combination_name
      if (address && zone) {
        return `${humanizeAddress(address)} matched ${zone}`
      }
      if (address) {
        return `${humanizeAddress(address)} resolved`
      }
    }

    if (Array.isArray(parsed.results)) {
      if (parsed.results.length === 0) {
        return "No matching zoning sources found"
      }
      return parsed.results.length === 1 ? "1 zoning source matched" : `${parsed.results.length} zoning sources matched`
    }
  } catch {
    return undefined
  }

  return undefined
}

function formatCitationLink(label: string, url: string): string {
  const cleanedLabel = label.trim() || "Section"
  const cleanedUrl = url.trim()
  return cleanedUrl ? `[${cleanedLabel}](${cleanedUrl})` : cleanedLabel
}

function extractCitationLinks(parsed: Record<string, unknown> | null | undefined): string[] {
  if (!parsed || typeof parsed !== "object") {
    return []
  }

  const links: string[] = []
  const sourceReferences = Array.isArray(parsed.source_references) ? parsed.source_references : []
  for (const item of sourceReferences) {
    if (!item || typeof item !== "object") {
      continue
    }
    const source = item as Record<string, unknown>
    const title = typeof source.section_title === "string" ? source.section_title : "Section"
    const citationMarkdown = typeof source.citation_markdown === "string" ? source.citation_markdown.trim() : ""
    if (citationMarkdown) {
      links.push(citationMarkdown)
      continue
    }
    const url =
      typeof source.section_url === "string"
        ? source.section_url
        : typeof source.page_url === "string"
          ? source.page_url
          : ""
    if (url) {
      links.push(formatCitationLink(title, url))
    }
  }

  const sourceCitations = Array.isArray(parsed.source_citations) ? parsed.source_citations : []
  for (const item of sourceCitations) {
    if (typeof item === "string" && item.trim()) {
      links.push(item.trim())
    }
  }

  return [...new Set(links)]
}

function unwrapToolResult(raw: unknown): unknown {
  const parsed = typeof raw === "string" ? JSON.parse(raw) : raw
  if (!parsed || typeof parsed !== "object") {
    return parsed
  }

  const record = parsed as Record<string, unknown>
  const nestedCandidates = [record.result, record.content, record.data, record.response]
  for (const candidate of nestedCandidates) {
    if (!candidate) {
      continue
    }

    const nested = typeof candidate === "string" ? (() => {
      try {
        return JSON.parse(candidate)
      } catch {
        return candidate
      }
    })() : candidate

    if (nested && typeof nested === "object") {
      const nestedRecord = nested as Record<string, unknown>
      if (
        "question_type" in nestedRecord ||
        "address_resolution" in nestedRecord ||
        "gridics" in nestedRecord ||
        "gridics_api" in nestedRecord ||
        "request_classification" in nestedRecord
      ) {
        return nested
      }
    }
  }

  return parsed
}

function buildToolResultFallback(toolCalls: StreamToolCall[]): string | null {
  const analyzeCall = [...toolCalls]
    .reverse()
    .find((toolCall) => (toolCall.toolName === "analyze_customer_zoning_request" || toolCall.label === "Analyze Customer Zoning Request") && toolCall.rawResult)

  if (!analyzeCall?.rawResult) {
    return null
  }

  try {
    const parsed = unwrapToolResult(analyzeCall.rawResult) as {
      question_type?: string
      request_classification?: { label?: string }
      address_resolution?: {
        standardized_address?: string
        resolved_state_env?: string
        resolved_zip_code?: string
      }
      gridics?: {
        zone_combination_name?: string
        typology?: string
        calculation_status?: string
        constraints?: {
          max_far?: number | null
          max_units?: number | null
          max_height_ft?: number | null
          front_setback_ft?: number | null
          side_setback_ft?: number | null
          rear_setback_ft?: number | null
        }
        notes?: string[]
      }
      story_equivalent?: number | null
      needs_address_clarification?: boolean
      clarification_prompt?: string
    }

    if (parsed.needs_address_clarification) {
      return parsed.clarification_prompt || "Please provide the full property address, including state and ZIP code."
    }

    const lines: string[] = []
    if (parsed.request_classification?.label) {
      lines.push(`This request was treated as a **${parsed.request_classification.label}** question.`)
    }

    const resolvedAddress = parsed.address_resolution?.standardized_address
    const stateEnv = parsed.address_resolution?.resolved_state_env?.toUpperCase()
    const resolvedZip = parsed.address_resolution?.resolved_zip_code
    if (resolvedAddress) {
      lines.push(`**Resolved Address:** ${resolvedAddress}${stateEnv || resolvedZip ? ` (${[stateEnv, resolvedZip].filter(Boolean).join(" ")})` : ""}`)
    }

    const zone = parsed.gridics?.zone_combination_name
    const typology = parsed.gridics?.typology
    if (zone || typology) {
      lines.push(`**Gridics Parcel Context:** ${[zone, typology].filter(Boolean).join(" - ")}`)
    }

    const constraints = parsed.gridics?.constraints
    if (constraints) {
      const constraintBits = [
        constraints.max_far != null ? `Max FAR ${constraints.max_far}` : null,
        constraints.max_units != null ? `Max units ${constraints.max_units}` : null,
        constraints.max_height_ft != null ? `Max height ${constraints.max_height_ft} ft` : null,
        constraints.front_setback_ft != null ? `Front setback ${constraints.front_setback_ft} ft` : null,
        constraints.side_setback_ft != null ? `Side setback ${constraints.side_setback_ft} ft` : null,
        constraints.rear_setback_ft != null ? `Rear setback ${constraints.rear_setback_ft} ft` : null,
      ].filter(Boolean)
      if (constraintBits.length) {
        lines.push(`**Observed Standards:** ${constraintBits.join(", ")}`)
      }
    }

    if (Array.isArray(parsed.gridics?.notes) && parsed.gridics?.notes.length) {
      lines.push(`**Notes:** ${parsed.gridics.notes[0]}`)
    }

    if (parsed.story_equivalent != null) {
      lines.push(`**Story Equivalent:** About ${parsed.story_equivalent} stories`)
    }

    const citationLinks = extractCitationLinks(parsed as Record<string, unknown>)
    if (citationLinks.length) {
      lines.push(`**Sources:** ${citationLinks.join(" · ")}`)
    }

    return lines.length ? lines.join("\n\n") : null
  } catch {
    return null
  }
}

function formatExpandableToolPayload(rawResult: unknown): { label: string; content: string } | null {
  try {
    const parsed = unwrapToolResult(rawResult)
    if (!parsed || typeof parsed !== "object") {
      return null
    }

    const record = parsed as Record<string, unknown>
    if (record.gridics_api && typeof record.gridics_api === "object") {
      return {
        label: "View Gridics API response",
        content: JSON.stringify(record.gridics_api, null, 2),
      }
    }

    const citationLinks = extractCitationLinks(record)
    if (citationLinks.length) {
      return {
        label: "View raw tool result",
        content: `${JSON.stringify(record, null, 2)}\n\nSources:\n${citationLinks.map((link) => `- ${link}`).join("\n")}`,
      }
    }

    return {
      label: "View raw tool result",
      content: JSON.stringify(record, null, 2),
    }
  } catch {
    if (typeof rawResult === "string" && rawResult.trim()) {
      return {
        label: "View raw tool result",
        content: rawResult,
      }
    }
    return null
  }
}

function upsertStep(steps: StreamStep[], next: StreamStep): StreamStep[] {
  const index = steps.findIndex((step) => step.id === next.id)
  if (index === -1) {
    return [...steps, next]
  }

  const updated = [...steps]
  updated[index] = {
    ...updated[index],
    ...next,
  }
  return updated
}

function buildEmptyAssistantResponse(debug: string | null) {
  return debug
    ? `The assistant completed the run but did not return displayable text.\n\nDebug: ${debug}`
    : "The assistant returned an empty response."
}

function appendDebugStep(steps: StreamStep[], debug: string | null) {
  if (!debug) {
    return steps
  }

  return upsertStep(steps, {
    id: "debug-run-fetch",
    label: "Debug",
    detail: debug,
    status: "error",
  })
}

function upsertToolCall(toolCalls: StreamToolCall[], next: StreamToolCall): StreamToolCall[] {
  const index = toolCalls.findIndex((toolCall) => toolCall.id === next.id)
  if (index === -1) {
    return [...toolCalls, next]
  }

  const updated = [...toolCalls]
  updated[index] = {
    ...updated[index],
    ...next,
  }
  return updated
}

async function fetchCompletedRun(
  agentId: string,
  runId: string,
  sessionId: string | null,
  isDebugEnabled: boolean,
  requestHeaders?: Record<string, string>,
): Promise<CompletedRunFetchResult> {
  if (!sessionId) {
    return {
      payload: null,
      debug: "Completed run lookup was skipped because no session_id was available.",
    }
  }

  try {
    const debugQuery = isDebugEnabled ? '&debug=1' : ''
    const response = await fetch(
      `${buildAssistantApiUrl(`/agents/${agentId}/runs/${runId}`)}?session_id=${encodeURIComponent(sessionId)}${debugQuery}`,
      {
        cache: "no-store",
        headers: requestHeaders,
      },
    )
    if (!response.ok) {
      if (response.status === 404) {
        return {
          payload: null,
          debug: null,
        }
      }
      const body = await response.text().catch(() => "")
      return {
        payload: null,
        debug: `Completed run lookup failed with HTTP ${response.status}${body ? `: ${body}` : ""}`,
      }
    }
    return {
      payload: (await response.json()) as AgentRunResponse,
      debug: null,
    }
  } catch (error) {
    return {
      payload: null,
      debug: error instanceof Error ? error.message : "Completed run lookup failed.",
    }
  }
}

async function fetchCompletedRunWithRetry(
  agentId: string,
  runId: string,
  sessionId: string | null,
  isDebugEnabled: boolean,
  requestHeaders?: Record<string, string>,
): Promise<CompletedRunFetchResult> {
  const attempts = 4
  let lastResult: CompletedRunFetchResult = {
    payload: null,
    debug: "Completed run lookup was never attempted.",
  }

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    lastResult = await fetchCompletedRun(agentId, runId, sessionId, isDebugEnabled, requestHeaders)
    if (lastResult.payload || lastResult.debug !== null) {
      return lastResult
    }

    if (attempt < attempts) {
      await new Promise((resolve) => window.setTimeout(resolve, attempt * 400))
    }
  }

  return lastResult
}

function RunSteps({ steps, status }: { steps?: StreamStep[]; status?: ChatMessage["status"] }) {
  const [isOpen, setIsOpen] = useState(false)

  if (!steps?.length) {
    return null
  }

  const isThinking = status === 'streaming'

  return (
    <div className="assistant-run-steps">
      <button
        className="assistant-run-toggle"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
      >
        <span className={`assistant-run-toggle-icon${isThinking ? ' is-thinking' : ''}`} aria-hidden="true">
          <TimelineIcon />
        </span>
        <span className="assistant-run-steps-label">{status === "complete" ? "Timeline" : "In progress"}</span>
        <span className="assistant-run-toggle-copy">
          {isThinking ? (
            <span className="assistant-run-thinking" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          ) : null}
          {steps.length} step{steps.length === 1 ? "" : "s"}
        </span>
        <span className="assistant-run-toggle-chevron" aria-hidden="true">
          {isOpen ? "−" : "+"}
        </span>
      </button>
      {isOpen ? (
        <div className="assistant-run-step-list">
          {steps.map((step) => (
            <div key={step.id} className={`assistant-run-step assistant-run-step-${step.status}`}>
              <span className="assistant-run-step-dot" aria-hidden="true" />
              <div className="assistant-run-step-copy">
                <strong>{step.label}</strong>
                {step.detail ? <span>{step.detail}</span> : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ToolCallList({ toolCalls }: { toolCalls?: StreamToolCall[] }) {
  const [isOpen, setIsOpen] = useState(false)

  if (!toolCalls?.length) {
    return null
  }

  const isThinking = toolCalls.some((toolCall) => toolCall.status === 'running')

  return (
    <div className="assistant-run-steps assistant-tool-calls">
      <button
        className="assistant-run-toggle"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
      >
        <span className={`assistant-run-toggle-icon${isThinking ? ' is-thinking' : ''}`} aria-hidden="true">
          <ToolsIcon />
        </span>
        <span className="assistant-run-steps-label">Tools</span>
        <span className="assistant-run-toggle-copy">
          {isThinking ? (
            <span className="assistant-run-thinking" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          ) : null}
          {toolCalls.length} tool{toolCalls.length === 1 ? "" : "s"}
        </span>
        <span className="assistant-run-toggle-chevron" aria-hidden="true">
          {isOpen ? "−" : "+"}
        </span>
      </button>
      <div className="assistant-tool-chip-row">
        {toolCalls.map((toolCall) => (
          <div
            key={`${toolCall.id}-chip`}
            className={`assistant-tool-chip assistant-tool-chip-${toolCall.status}`}
            title={toolCall.detail || toolCall.label}
          >
            <span className="assistant-tool-chip-dot" aria-hidden="true" />
            <span>{toolCall.label}</span>
          </div>
        ))}
      </div>
      {isOpen ? (
        <div className="assistant-run-step-list">
          {toolCalls.map((toolCall) => (
            <div key={toolCall.id} className={`assistant-run-step assistant-run-step-${toolCall.status}`}>
              <span className="assistant-run-step-dot" aria-hidden="true" />
              <div className="assistant-run-step-copy">
                <strong>{toolCall.label}</strong>
                {toolCall.detail ? <span>{toolCall.detail}</span> : null}
                {toolCall.rawResult ? (
                  (() => {
                    const payload = formatExpandableToolPayload(toolCall.rawResult)
                    if (!payload) {
                      return null
                    }
                    return (
                      <details className="assistant-tool-result-details">
                        <summary>{payload.label}</summary>
                        <pre>{payload.content}</pre>
                      </details>
                    )
                  })()
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function collectSourceChips(message: ChatMessage): string[] {
  const labels = [
    ...(message.toolCalls ?? []).map((toolCall) => toolCall.label),
    ...(message.steps ?? [])
      .map((step) => step.label)
      .filter((label) => label !== 'Preparing answer' && label !== 'Drafting response'),
  ]

  return [...new Set(labels)].slice(0, 3)
}

function AssistantMessageDetails({
  message,
  customerName,
  onCopyMessage,
  onFeedbackToggle,
  messageFeedbackValue,
}: {
  message: ChatMessage
  customerName: string
  onCopyMessage: (content: string) => void
  onFeedbackToggle: (message: ChatMessage, direction: MessageFeedback) => Promise<void>
  messageFeedbackValue?: MessageFeedback
}) {
  const hasDetails =
    Boolean(message.content) ||
    Boolean(message.toolCalls?.length) ||
    Boolean(message.steps?.length) ||
    Boolean(message.error) ||
    message.status === "complete"

  return (
    <details className="assistant-message-details">
      <summary className="assistant-message-details-summary">
        <span>Show run details</span>
        <span className="assistant-message-details-summary-meta">
          {message.toolCalls?.length ? `${message.toolCalls.length} tool${message.toolCalls.length === 1 ? "" : "s"}` : null}
          {message.toolCalls?.length && message.steps?.length ? " • " : null}
          {message.steps?.length ? `${message.steps.length} step${message.steps.length === 1 ? "" : "s"}` : null}
        </span>
      </summary>
      <div className="assistant-message-details-body">
        <div className="assistant-message-tools">
          <div className="assistant-message-tools-primary">
            <button
              className="assistant-message-tool-button"
              type="button"
              aria-label="Copy answer"
              title="Copy answer"
              onClick={() => onCopyMessage(message.content)}
            >
              <CopyIcon />
            </button>
            <button
              className={`assistant-message-tool-button${messageFeedbackValue === 'up' ? ' is-active' : ''}`}
              type="button"
              aria-label="Helpful response"
              title="Helpful response"
              onClick={() => void onFeedbackToggle(message, 'up')}
            >
              <ThumbUpIcon />
            </button>
            <button
              className={`assistant-message-tool-button${messageFeedbackValue === 'down' ? ' is-active is-negative' : ''}`}
              type="button"
              aria-label="Unhelpful response"
              title="Unhelpful response"
              onClick={() => void onFeedbackToggle(message, 'down')}
            >
              <ThumbDownIcon />
            </button>
          </div>
          {collectSourceChips(message).length ? (
            <div className="assistant-source-chip-row">
              {collectSourceChips(message).map((chip) => (
                <span key={chip} className="assistant-source-chip">
                  {chip}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {message.toolCalls ? <ToolCallList toolCalls={message.toolCalls} /> : null}
        {message.steps ? <RunSteps steps={message.steps} status={message.status} /> : null}

        {message.role === "assistant" && message.error ? (
          <div className="status-banner status-banner-error">{message.error}</div>
        ) : null}

        {!hasDetails ? <div className="assistant-message-details-empty">No run details were captured.</div> : null}
      </div>
    </details>
  )
}

function ChatEmptyState({
  customerName,
  onSelectPrompt,
}: {
  customerName: string
  onSelectPrompt: (prompt: string) => void
}) {
  return (
    <div className="assistant-chat-empty-state">
      <div className="assistant-chat-empty-intro">
        <h2 className="assistant-chat-empty-title">Ask anything about {customerName} zoning</h2>
        <p className="assistant-chat-empty-copy">
          Get quick guidance on districts, setbacks, parking, overlays, and related regulations before you
          move into a deeper review.
        </p>
      </div>
      <div className="assistant-chat-suggestion-grid" role="list" aria-label="Suggested prompts">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="assistant-chat-suggestion"
            onClick={() => onSelectPrompt(prompt)}
          >
            <span className="assistant-chat-suggestion-label">{prompt}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

export function AgentChatPanel({
  agentId,
  backendBase,
  customerName,
  clientId,
  defaultModelId = "",
  surface,
  title,
  description,
  variant = "default",
  requestHeaders,
  embedSessionToken,
  embeddedLayout = false,
  onEmbedChatActionsChange,
  showEmptyStateHint = true,
  showBrandingFooter = true,
  showModelControls = true,
  showToolbar = true,
}: {
  agentId: string
  backendBase: string
  customerName: string
  clientId: string | null
  defaultModelId?: string
  surface: string
  title: string
  description: string
  variant?: "default" | "chatgpt"
  requestHeaders?: Record<string, string>
  embedSessionToken?: string
  embeddedLayout?: boolean
  onEmbedChatActionsChange?: ((actions: EmbedChatActions | null) => void) | undefined
  showEmptyStateHint?: boolean
  showBrandingFooter?: boolean
  showModelControls?: boolean
  showToolbar?: boolean
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const [composerError, setComposerError] = useState<string | null>(null)
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle")
  const [copyMessage, setCopyMessage] = useState<string | null>(null)
  const [messageFeedback, setMessageFeedback] = useState<Record<string, MessageFeedback | undefined>>({})
  const [modelId, setModelId] = useState(defaultModelId)
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false)
  const searchParams = useSearchParams()
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement | null>(null)
  const modelPickerRef = useRef<HTMLDivElement | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const runIdRef = useRef<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const normalizedModelId = modelId.trim()
  const normalizedDefaultModelId = defaultModelId.trim()
  const isModelOverrideActive =
    Boolean(normalizedModelId) && normalizedModelId !== normalizedDefaultModelId
  const showPublicAssistantFooter = showBrandingFooter && surface === "public-assistant"
  const currentYear = new Date().getFullYear()
  const isPublicAssistantSurface = surface === "public-assistant"
  const isDebugEnabled = searchParams.get('debug') === '1'
  const chatTitle = variant === "chatgpt" ? 'Zoning Assistant' : title
  const chatSubtitle = variant === "chatgpt" ? 'Planning & zoning guidance' : description

  const assistantMessageCount = useMemo(
    () => messages.filter((message) => message.role === 'assistant').length,
    [messages],
  )

  useEffect(() => {
    setModelId((currentModelId) => {
      if (currentModelId.trim()) {
        return currentModelId
      }
      return defaultModelId
    })
  }, [defaultModelId])

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) {
      return
    }
    viewport.scrollTop = viewport.scrollHeight
  }, [messages])

  useEffect(() => {
    const textarea = composerRef.current
    if (!textarea) {
      return
    }

    textarea.style.height = '0px'
    const nextHeight = Math.min(Math.max(textarea.scrollHeight, 56), 180)
    textarea.style.height = `${nextHeight}px`
  }, [input])

  useEffect(() => {
    if (!isModelPickerOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (modelPickerRef.current?.contains(event.target as Node)) {
        return
      }
      setIsModelPickerOpen(false)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsModelPickerOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    window.addEventListener("keydown", handleKeyDown)

    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      window.removeEventListener("keydown", handleKeyDown)
    }
  }, [isModelPickerOpen])

  useEffect(() => {
    if (!embeddedLayout) {
      return
    }

    const handleEmbedAction = (event: Event) => {
      const detail = (event as CustomEvent<{ action?: string }>).detail
      if (!detail?.action) {
        return
      }

      if (detail.action === 'new-chat') {
        handleNewChat()
        return
      }

      if (detail.action === 'copy') {
        void handleCopyConversation()
      }
    }

    window.addEventListener('uzone-embed-chat-action', handleEmbedAction as EventListener)
    return () => {
      window.removeEventListener('uzone-embed-chat-action', handleEmbedAction as EventListener)
    }
  }, [embeddedLayout, messages, isStreaming])

  useEffect(() => {
    if (!embeddedLayout || !onEmbedChatActionsChange) {
      return
    }

    onEmbedChatActionsChange({
      copyConversation: () => {
        void handleCopyConversation()
      },
      newChat: handleNewChat,
    })

    return () => {
      onEmbedChatActionsChange(null)
    }
  }, [embeddedLayout, messages, isStreaming, onEmbedChatActionsChange])

  useEffect(() => {
    if (surface !== 'public-assistant' || variant !== 'chatgpt' || typeof window === 'undefined') {
      return
    }

    const publishToolbarState = () => {
      const detail: AssistantToolbarState = {
        title: chatTitle,
        subtitle: null,
        canCopy: messages.length > 0,
        canNewChat: !(isStreaming && !messages.length),
      }
      ;(window as Window & { __uzoneAssistantToolbarState?: AssistantToolbarState | null }).__uzoneAssistantToolbarState =
        detail
      window.dispatchEvent(new CustomEvent('uzone-assistant-toolbar-state', { detail }))
    }

    const handleToolbarAction = (event: Event) => {
      const detail = (event as CustomEvent<{ action?: string }>).detail
      if (!detail?.action) {
        return
      }

      if (detail.action === 'new-chat') {
        handleNewChat()
        return
      }

      if (detail.action === 'copy') {
        void handleCopyConversation()
      }
    }

    publishToolbarState()
    window.addEventListener('uzone-assistant-toolbar-action', handleToolbarAction as EventListener)

    return () => {
      window.removeEventListener('uzone-assistant-toolbar-action', handleToolbarAction as EventListener)
      ;(window as Window & { __uzoneAssistantToolbarState?: AssistantToolbarState | null }).__uzoneAssistantToolbarState =
        null
      window.dispatchEvent(new CustomEvent('uzone-assistant-toolbar-state', { detail: null }))
    }
  }, [surface, variant, chatTitle, messages, isStreaming])

  const updateAssistantMessage = (messageId: string, updater: (message: ChatMessage) => ChatMessage): void => {
    setMessages((prevMessages) =>
      prevMessages.map((message) => (message.id === messageId ? updater(message) : message)),
    )
  }

  const sendMessage = async (overrideMessage?: string) => {
    const trimmed = (overrideMessage ?? input).trim()
    if (!trimmed || isStreaming) {
      return
    }

    if (!clientId || !clientId.trim()) {
      setComposerError("Tenant client configuration is missing for this assistant. Reload the page after selecting a jurisdiction or fixing tenant config.")
      return
    }

    const userMessageId = `user-${Date.now()}`
    const assistantMessageId = `assistant-${Date.now() + 1}`
    const controller = new AbortController()
    abortControllerRef.current = controller
    setComposerError(null)
    setInput("")
    setIsStreaming(true)

    const initialSteps: StreamStep[] = [
      {
        id: "run-started",
        label: "Preparing answer",
        detail: "Opening an agent run for this tenant-scoped conversation",
        status: "running",
      },
    ]

    setMessages((prevMessages) => [
      ...prevMessages,
      {
        id: userMessageId,
        role: "user",
        content: trimmed,
        status: "complete",
      },
      {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        steps: initialSteps,
        status: "streaming",
      },
    ])

    const body = new FormData()
    body.set("message", trimmed)
    body.set("stream", "true")
    if (sessionIdRef.current) {
      body.set("session_id", sessionIdRef.current)
    }
    body.set(
      "dependencies",
      JSON.stringify({
        client_id: clientId,
        customer_name: customerName,
      }),
    )
    body.set(
      "metadata",
      JSON.stringify({
        surface,
        client_id: clientId,
        assistant_model_id: modelId.trim() || undefined,
        embed_token: embedSessionToken || undefined,
      }),
    )

    let textContent = ""
    let runSteps = initialSteps
    let toolCalls: StreamToolCall[] = []
    let provisionalContent = ""
    let lastVisibleContent = ""
    let sawToolCall = false
    let answerPhaseStarted = false
    let modelRequestCount = 0

    const handleStreamUpdate = (next: Partial<ChatMessage>) => {
      updateAssistantMessage(assistantMessageId, (message) => ({
        ...message,
        ...next,
      }))
    }

    const processEvent = async (event: SSEEvent): Promise<boolean> => {
      const payload = event.data
      const maybeSessionId = typeof payload.session_id === "string" ? payload.session_id : null
      const maybeRunId = typeof payload.run_id === "string" ? payload.run_id : null
      if (maybeSessionId) {
        sessionIdRef.current = maybeSessionId
      }
      if (maybeRunId) {
        runIdRef.current = maybeRunId
        updateAssistantMessage(assistantMessageId, (message) => ({
          ...message,
          runId: maybeRunId,
        }))
      }

      if (eventMatches(event.event, "RunStarted")) {
        const model = typeof payload.model === "string" ? payload.model : "configured model"
        const traceDetail = formatAssistantModelTrace(payload)
        runSteps = upsertStep(runSteps, {
          id: "run-started",
          label: "Preparing answer",
          detail: traceDetail ? `Connected to ${model} | ${traceDetail}` : `Connected to ${model}`,
          status: "complete",
        })
        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: "Drafting response",
          detail: "The assistant is planning the answer",
          status: "running",
        })
        handleStreamUpdate({ steps: runSteps })
        return false
      }

      if (eventMatches(event.event, "ModelRequestStarted")) {
        modelRequestCount += 1
        if (sawToolCall || modelRequestCount > 1) {
          answerPhaseStarted = true
        }
        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: answerPhaseStarted ? "Writing final answer" : "Drafting response",
          detail: answerPhaseStarted ? "Using tool results to write the answer" : "The assistant is planning the answer",
          status: "running",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (eventMatches(event.event, "ModelRequestCompleted")) {
        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: answerPhaseStarted ? "Writing final answer" : "Drafting response",
          detail: answerPhaseStarted ? "Final answer draft completed" : "Planning completed",
          status: "complete",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (eventMatches(event.event, "ToolCallStarted")) {
        const tool = payload.tool && typeof payload.tool === "object" ? (payload.tool as Record<string, unknown>) : undefined
        const toolId =
          typeof tool?.tool_call_id === "string"
            ? tool.tool_call_id
            : `tool-${typeof tool?.tool_name === "string" ? tool.tool_name : runSteps.length}`
        sawToolCall = true
        provisionalContent = ""
        runSteps = upsertStep(runSteps, {
          id: toolId,
          label: toStepLabel(typeof tool?.tool_name === "string" ? tool.tool_name : undefined),
          detail: toStepDetail(tool),
          status: "running",
        })
        toolCalls = upsertToolCall(toolCalls, {
          id: toolId,
          label: toStepLabel(typeof tool?.tool_name === "string" ? tool.tool_name : undefined),
          toolName: typeof tool?.tool_name === "string" ? tool.tool_name : undefined,
          detail: toStepDetail(tool),
          status: "running",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (eventMatches(event.event, "ToolCallCompleted")) {
        const tool = payload.tool && typeof payload.tool === "object" ? (payload.tool as Record<string, unknown>) : undefined
        const toolId =
          typeof tool?.tool_call_id === "string"
            ? tool.tool_call_id
            : `tool-${typeof tool?.tool_name === "string" ? tool.tool_name : runSteps.length}`
        runSteps = upsertStep(runSteps, {
          id: toolId,
          label: toStepLabel(typeof tool?.tool_name === "string" ? tool.tool_name : undefined),
          detail: summarizeToolResult(tool?.result) || toStepDetail(tool),
          status: "complete",
        })
        toolCalls = upsertToolCall(toolCalls, {
          id: toolId,
          label: toStepLabel(typeof tool?.tool_name === "string" ? tool.tool_name : undefined),
          toolName: typeof tool?.tool_name === "string" ? tool.tool_name : undefined,
          detail: summarizeToolResult(tool?.result) || toStepDetail(tool),
          status: "complete",
          rawResult: tool?.result,
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (eventMatches(event.event, "ToolCallError")) {
        const tool = payload.tool && typeof payload.tool === "object" ? (payload.tool as Record<string, unknown>) : undefined
        const toolId =
          typeof tool?.tool_call_id === "string"
            ? tool.tool_call_id
            : `tool-${typeof tool?.tool_name === "string" ? tool.tool_name : runSteps.length}`
        runSteps = upsertStep(runSteps, {
          id: toolId,
          label: toStepLabel(typeof tool?.tool_name === "string" ? tool.tool_name : undefined),
          detail: typeof payload.error === "string" ? payload.error : "Tool execution failed",
          status: "error",
        })
        toolCalls = upsertToolCall(toolCalls, {
          id: toolId,
          label: toStepLabel(typeof tool?.tool_name === "string" ? tool.tool_name : undefined),
          toolName: typeof tool?.tool_name === "string" ? tool.tool_name : undefined,
          detail: typeof payload.error === "string" ? payload.error : "Tool execution failed",
          status: "error",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls, status: "error" })
        return false
      }

      if (eventMatches(event.event, "RunContent")) {
        const incomingContent = sanitizeAssistantContent(normalizeContent(payload.content))
        if (incomingContent) {
          if (sawToolCall || answerPhaseStarted) {
            textContent = incomingContent.startsWith(textContent) ? incomingContent : `${textContent}${incomingContent}`
            lastVisibleContent = textContent
            handleStreamUpdate({ content: textContent, steps: runSteps, toolCalls, status: "streaming" })
          } else {
            provisionalContent = incomingContent.startsWith(provisionalContent)
              ? incomingContent
              : `${provisionalContent}${incomingContent}`
            lastVisibleContent = provisionalContent
            handleStreamUpdate({ steps: runSteps, toolCalls, status: "streaming" })
          }
        }
        return false
      }

      if (eventMatches(event.event, "RunContentCompleted")) {
        handleStreamUpdate({ steps: runSteps, toolCalls, status: "streaming" })
        return false
      }

      if (eventMatches(event.event, "RunCompleted")) {
        let debugDetail: string | null = null
        let finalContent = getAssistantContent(payload as AgentRunResponse)
        let traceDetail = formatAssistantModelTrace(payload)
        if (!finalContent) {
          debugDetail = `RunCompleted payload inspection: ${getAssistantContentDebug(payload as AgentRunResponse)}`
        }

        if (!finalContent && runIdRef.current) {
          const completedRun = await fetchCompletedRunWithRetry(
            agentId,
            runIdRef.current,
            sessionIdRef.current,
            isDebugEnabled,
            requestHeaders,
          )
          const completedRunDebug = completedRun.debug
          const contentDebug = getAssistantContentDebug(completedRun.payload || {})
          debugDetail = [debugDetail, completedRunDebug, `Completed run payload inspection: ${contentDebug}`]
            .filter(Boolean)
            .join(" | ")
          const fetchedContent = getAssistantContent(completedRun.payload || {})
          traceDetail = traceDetail || formatAssistantModelTrace((completedRun.payload || {}) as Record<string, unknown>)
          if (fetchedContent) {
            finalContent = fetchedContent
          }
        }

        if (finalContent && finalContent.length >= textContent.length) {
          textContent = finalContent
        }
        if (textContent) {
          lastVisibleContent = textContent
        }

        const toolFallbackContent = finalContent || textContent || provisionalContent || lastVisibleContent
          ? null
          : buildToolResultFallback(toolCalls)

        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: "Drafting response",
          detail: "Answer completed",
          status: "complete",
        })
        runSteps = enrichRunStartedStepWithTrace(runSteps, traceDetail)
        runSteps = appendDebugStep(runSteps, debugDetail)
        handleStreamUpdate({
          content:
            finalContent ||
            textContent ||
            provisionalContent ||
            lastVisibleContent ||
            toolFallbackContent ||
            buildEmptyAssistantResponse(debugDetail),
          steps: runSteps,
          toolCalls,
          status: "complete",
        })
        return true
      }

      if (eventMatches(event.event, "RunError")) {
        let traceDetail = formatAssistantModelTrace(payload)
        const errorMessage =
          typeof payload.content === "string" && payload.content ? payload.content : "Unable to reach the assistant."

        if ((!traceDetail || !traceDetail.includes("key:")) && runIdRef.current) {
          const completedRun = await fetchCompletedRunWithRetry(
            agentId,
            runIdRef.current,
            sessionIdRef.current,
            isDebugEnabled,
            requestHeaders,
          )
          traceDetail = traceDetail || formatAssistantModelTrace((completedRun.payload || {}) as Record<string, unknown>)
        }

        runSteps = enrichRunStartedStepWithTrace(runSteps, traceDetail)
        const traceBanner = buildTraceBanner(traceDetail)
        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: "Drafting response",
          detail: errorMessage,
          status: "error",
        })
        handleStreamUpdate({
          content:
            [
              traceBanner,
              textContent || lastVisibleContent || "The assistant run failed before returning any content.",
            ]
              .filter(Boolean)
              .join("\n\n"),
          steps: runSteps,
          toolCalls,
          status: "error",
          error: errorMessage,
        })
        return true
      }

      return false
    }

    try {
      const runHeaders = embedSessionToken
        ? {
            Accept: "application/json",
          }
        : {
            Accept: "application/json",
            ...(requestHeaders || {}),
          }
      const runDebugQuery = isDebugEnabled ? "?debug=1" : ""
      const runUrl = `${buildAssistantApiUrl(`/agents/${agentId}/runs`)}${runDebugQuery}`

      if (process.env.NODE_ENV !== "production") {
        console.debug("[assistant] submit run", {
          backendBase,
          agentId,
          url: runUrl,
          debug: isDebugEnabled,
        })
        if (isDebugEnabled && backendBase.trim()) {
          console.warn('[assistant] browser assistant URL resolved for AgentOS run', {
            runUrl,
            agentId,
          })
        }
      }

      const response = await fetch(runUrl, {
        method: "POST",
        body,
        signal: controller.signal,
        headers: {
          ...runHeaders,
          ...(isDebugEnabled ? { "X-UZone-Debug": "1" } : {}),
        },
      })

      const responseContentType = response.headers.get('content-type') || ''
      const isJsonResponse = responseContentType.includes('application/json')

      if (!response.ok) {
        const responseText = await response.text().catch(() => "")
        if (isDebugEnabled) {
          console.error("[assistant] run request failed", {
            url: runUrl,
            status: response.status,
            statusText: response.statusText,
            responseText,
            agentId,
            backendBase,
            surface,
          })
        }
        let payload: { detail?: string } | null = null
        if (responseText) {
          try {
            payload = JSON.parse(responseText) as { detail?: string }
          } catch {
            payload = null
          }
        }
        throw new Error(payload?.detail || responseText || "Unable to reach the assistant.")
      }

      if (isJsonResponse) {
        const payload = (await response.json().catch(() => null)) as AgentRunResponse | null
        sessionIdRef.current = payload?.session_id ?? null
        if (isDebugEnabled && payload?.debug) {
          console.debug('[assistant] backend run debug bundle', payload.debug)
        }
        const content = getAssistantContent(payload || {})
        const debugDetail = content ? null : getAssistantContentDebug(payload || {})
        handleStreamUpdate({
          content: content || buildEmptyAssistantResponse(debugDetail),
          status: "complete",
          steps: appendDebugStep(
            upsertStep(runSteps, {
              id: "model-request",
              label: "Drafting response",
              detail: "Answer completed",
              status: "complete",
            }),
            debugDetail,
          ),
          toolCalls,
        })
        return
      }

      if (!response.body) {
        const responseText = await response.text().catch(() => '')
        throw new Error(responseText || 'The assistant returned an empty response body.')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      let finished = false

      try {
        while (true) {
          const { value, done } = await reader.read()
          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const parsed = parseSSEEvents(buffer)
          buffer = parsed.remainder

          for (const event of parsed.events) {
            finished = await processEvent(event)
            if (finished) {
              break
            }
          }

          if (finished) {
            break
          }
        }

        if (!finished) {
          buffer += decoder.decode()
          const parsed = parseSSEEvents(buffer ? `${buffer}\n\n` : "")
          for (const event of parsed.events) {
            finished = await processEvent(event)
            if (finished) {
              break
            }
          }
        }
      } finally {
        reader.releaseLock()
      }

      if (!finished && !controller.signal.aborted) {
        let debugDetail: string | null = null
        let fallbackContent = textContent || provisionalContent || lastVisibleContent

        if (!fallbackContent && runIdRef.current) {
          const completedRun = await fetchCompletedRunWithRetry(
            agentId,
            runIdRef.current,
            sessionIdRef.current,
            isDebugEnabled,
            requestHeaders,
          )
          const completedRunDebug = completedRun.debug
          const contentDebug = getAssistantContentDebug(completedRun.payload || {})
          debugDetail = [completedRunDebug, `Completed run payload inspection: ${contentDebug}`].filter(Boolean).join(" | ")
          fallbackContent = getAssistantContent(completedRun.payload || {})
          runSteps = appendDebugStep(runSteps, debugDetail)
        }

        if (!fallbackContent) {
          fallbackContent = buildToolResultFallback(toolCalls) || ""
        }

        handleStreamUpdate({
          content: fallbackContent || buildEmptyAssistantResponse(debugDetail),
          status: "complete",
          steps: runSteps,
          toolCalls,
        })
      }
    } catch (error) {
      if (isDebugEnabled) {
        console.error("[assistant] run fetch threw", {
          backendBase,
          agentId,
          surface,
          debug: isDebugEnabled,
          error,
        })
      }
      const errorMessage = error instanceof Error ? error.message : "Unable to reach the assistant."
      setComposerError(errorMessage)
      updateAssistantMessage(assistantMessageId, (message) => ({
        ...message,
        content: message.content || "The assistant run failed before returning any content.",
        status: "error",
        error: errorMessage,
      }))
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
      runIdRef.current = null
    }
  }

  const handleNewChat = () => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    sessionIdRef.current = null
    runIdRef.current = null
    setMessages([])
    setInput("")
    setComposerError(null)
    setIsStreaming(false)
    setMessageFeedback({})
  }

  const handleCopyConversation = async () => {
    if (!messages.length) {
      setCopyMessage("There is no conversation to copy yet.")
      setCopyState("error")
      window.setTimeout(() => {
        setCopyState("idle")
        setCopyMessage(null)
      }, 2500)
      return
    }

    try {
      await copyTextToClipboard(
        buildConversationExport(messages, {
          agentId,
          customerName,
          defaultModelId: normalizedDefaultModelId,
          modelId: normalizedModelId,
          runId: runIdRef.current,
          sessionId: sessionIdRef.current,
          surface,
        }),
      )
      setCopyMessage(null)
      setCopyState("copied")
    } catch {
      setCopyMessage("Unable to copy the conversation. Your browser may be blocking clipboard access.")
      setCopyState("error")
    }

    window.setTimeout(() => {
      setCopyState("idle")
      setCopyMessage(null)
    }, 2000)
  }

  const handleCopyMessage = async (content: string) => {
    try {
      await copyTextToClipboard(content)
    } catch {
      // Ignore copy errors for inline message tools.
    }
  }

  const handleFeedbackToggle = async (message: ChatMessage, direction: MessageFeedback) => {
    if (!clientId || !clientId.trim()) {
      setComposerError("Tenant client configuration is missing for this assistant.")
      return
    }

    const conversationId = sessionIdRef.current?.trim()
    if (!conversationId) {
      setComposerError("Feedback is available after the assistant session is established.")
      return
    }

    const previous = messageFeedback[message.id]
    const nextValue = previous === direction ? undefined : direction

    setMessageFeedback((current) => ({
      ...current,
      [message.id]: nextValue,
    }))

    try {
      const response = await fetch(buildAssistantApiUrl('/public/assistant-feedback'), {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(embedSessionToken ? {} : (requestHeaders || {})),
        },
        body: JSON.stringify({
          client_id: clientId,
          agent_id: agentId,
          surface,
          conversation_id: conversationId,
          message_id: message.id,
          run_id: message.runId || undefined,
          feedback_value: nextValue ?? null,
          message_excerpt: message.content.slice(0, 4000),
        }),
      })

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null
        throw new Error(payload?.detail || "Unable to save feedback.")
      }
    } catch (error) {
      setMessageFeedback((current) => ({
        ...current,
        [message.id]: previous,
      }))
      setComposerError(error instanceof Error ? error.message : "Unable to save feedback.")
    }
  }

  const handleSuggestionClick = (prompt: string) => {
    setInput(prompt)
    void sendMessage(prompt)
  }

  const handleFollowUpClick = (prompt: string) => {
    setInput(prompt)
    composerRef.current?.focus()
  }

  return (
    <div className={variant === "chatgpt" ? "assistant-chat-card" : "admin-list"}>
      {variant === "chatgpt" ? null : (
        <>
          <div className="admin-list-heading">{title}</div>
          <div style={{ color: "var(--muted)", marginBottom: 12 }}>{description}</div>
        </>
      )}

      <div className={`agent-chat-shell agent-chat-shell-${variant}`}>
        {variant === "chatgpt" && !embeddedLayout && showToolbar ? (
          <div className="assistant-chat-toolbar">
            <div className="assistant-chat-toolbar-copy">
              <div className="assistant-chat-toolbar-title">{chatTitle}</div>
              {chatSubtitle ? <div className="assistant-chat-toolbar-subtitle">{chatSubtitle}</div> : null}
            </div>
            <div className="assistant-chat-toolbar-actions">
              <span className="assistant-chat-toolbar-stat">
                {assistantMessageCount} answer{assistantMessageCount === 1 ? '' : 's'}
              </span>
              <button
                className="assistant-chat-toolbar-icon-button"
                type="button"
                aria-label="Copy conversation"
                title={messages.length ? "Copy conversation" : "No conversation to copy yet"}
                disabled={!messages.length}
                onClick={() => void handleCopyConversation()}
              >
                <span aria-hidden="true">{copyState === "copied" ? "✓" : "⎘"}</span>
              </button>
              <button
                className="assistant-chat-toolbar-button"
                type="button"
                onClick={handleNewChat}
                disabled={isStreaming && !messages.length}
              >
                {isStreaming ? 'Stop & Reset' : 'New Chat'}
              </button>
          </div>
          {copyMessage ? <div className="assistant-chat-toolbar-copy-status">{copyMessage}</div> : null}
        </div>
        ) : null}
        <div ref={viewportRef} className={`agent-chat-log agent-chat-log-${variant}`}>
          {messages.length === 0 ? (
            <ChatEmptyState customerName={customerName} onSelectPrompt={handleSuggestionClick} />
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`agent-chat-message-row agent-chat-message-row-${message.role}`}
                data-message-id={message.id}
              >
                <div className={`agent-chat-message agent-chat-message-${message.role}`}>
                  <div className="agent-chat-message-header">
                    <div className="agent-chat-message-role-block">
                      <div className="agent-chat-message-role">
                        {message.role === "user" ? "You" : `${customerName} Assistant`}
                      </div>
                      {message.role === "assistant" && message.status === "streaming" ? (
                        <div className="agent-chat-message-status">
                          <span className="assistant-streaming-dots" aria-hidden="true">
                            <span />
                            <span />
                            <span />
                          </span>
                          Streaming
                        </div>
                      ) : null}
                    </div>
                  </div>
                  <div className="assistant-ui-message-content">
                    {message.role === "user" ? (
                      <div className="assistant-ui-user-content">{message.content}</div>
                    ) : message.content ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    ) : message.status === "streaming" ? (
                      <div className="assistant-answer-placeholder">Reviewing zoning context and preparing an answer…</div>
                    ) : (
                      <div className="assistant-answer-placeholder">No answer text was returned.</div>
                    )}
                  </div>
                  {message.role === "assistant" ? (
                    <AssistantMessageDetails
                      message={message}
                      customerName={customerName}
                      onCopyMessage={handleCopyMessage}
                      onFeedbackToggle={handleFeedbackToggle}
                      messageFeedbackValue={messageFeedback[message.id]}
                    />
                  ) : null}
                </div>
              </div>
            ))
          )}
        </div>

        <div className={`agent-chat-form assistant-ui-composer assistant-ui-composer-${variant}`}>
          {showModelControls ? (
            <div className="assistant-model-popover-shell" ref={modelPickerRef}>
              <button
                className={`assistant-model-trigger${isModelOverrideActive ? " is-override" : ""}`}
                type="button"
                aria-label="Open model settings"
                aria-haspopup="dialog"
                aria-expanded={isModelPickerOpen}
                onClick={() => setIsModelPickerOpen((open) => !open)}
              >
                <span className="assistant-model-trigger-label">Model</span>
                <span className="assistant-model-trigger-status">
                  {isModelOverrideActive ? "Override On" : "Default"}
                </span>
              </button>

              {isModelPickerOpen ? (
                <div className="assistant-model-popover" role="dialog" aria-label="Model settings">
                  <div className="assistant-model-popover-header">
                    <div className="assistant-model-controls-copy">
                      <strong>Model override</strong>
                      <span>
                        Default: <code>{defaultModelId || "backend-defined model"}</code>
                      </span>
                    </div>
                    <button
                      className="assistant-model-popover-close"
                      type="button"
                      aria-label="Close model settings"
                      onClick={() => setIsModelPickerOpen(false)}
                    >
                      Close
                    </button>
                  </div>
                  <div className="assistant-model-controls-inputs">
                    <input
                      type="text"
                      className="assistant-model-input"
                      value={modelId}
                      disabled={isStreaming}
                      onChange={(event) => setModelId(event.target.value)}
                      placeholder={defaultModelId || "Leave blank to use the backend-defined model"}
                    />
                    <button
                      className="button secondary"
                      type="button"
                      disabled={isStreaming || modelId.trim() === defaultModelId.trim()}
                      onClick={() => setModelId(defaultModelId)}
                    >
                      Use Default
                    </button>
                  </div>
                  <div className="assistant-model-controls-status">
                    {isModelOverrideActive
                      ? `Override active for new runs: ${normalizedModelId}`
                      : "No override active. New runs will use the model defined by the backend agent."}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="assistant-ui-composer-row">
            <label className="assistant-ui-input-wrap">
              <textarea
                ref={composerRef}
                name="input"
                className="assistant-ui-input"
                rows={1}
                placeholder="Ask about setbacks, overlays, parking, lot coverage, or permitted uses"
                value={input}
                disabled={isStreaming}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault()
                    void sendMessage()
                  }
                }}
              />
              <button
                className="assistant-ui-send-button"
                type="button"
                aria-label={isStreaming ? "Sending message" : "Send message"}
                onClick={() => {
                  void sendMessage()
                }}
                disabled={isStreaming || !input.trim()}
              >
                {isStreaming ? "..." : "↑"}
              </button>
            </label>
          </div>
          {showModelControls || !embeddedLayout ? (
            <div className="assistant-ui-composer-footer">
              {showModelControls ? (
                <div
                  className={`assistant-model-banner${isModelOverrideActive ? " is-override" : ""}`}
                  aria-live="polite"
                >
                  {isModelOverrideActive ? (
                    <>
                      Next run will override the backend-defined model with <code>{normalizedModelId}</code>.
                    </>
                  ) : (
                    <>
                      Next run will use the backend-defined model <code>{defaultModelId || "agent default"}</code>.
                    </>
                  )}
                </div>
              ) : null}
              {!embeddedLayout ? (
                <div className="assistant-ui-composer-meta">
                  <div className="assistant-ui-composer-hint">Enter to send. Shift+Enter for a new line.</div>
                </div>
              ) : null}
            </div>
          ) : null}
          {isPublicAssistantSurface ? (
            <div className="assistant-chat-footer-note">
              This assistant provides informational guidance only and may not reflect final determinations. By
              continuing, you agree to the{' '}
              <a href="https://gridics.com/terms/" target="_blank" rel="noreferrer">
                Terms of Service
              </a>{' '}
              and{' '}
              <a href="https://gridics.com/privacy/" target="_blank" rel="noreferrer">
                Privacy Policy
              </a>
              .
            </div>
          ) : null}
          {showPublicAssistantFooter ? (
            <div className="assistant-ui-powered-footer">
              <span>Copyright © {currentYear} Gridics. All rights reserved.</span>
              <a href="https://gridics.com/privacy/" target="_blank" rel="noreferrer">
                Privacy
              </a>
              <a href="https://gridics.com/terms/" target="_blank" rel="noreferrer">
                Terms of Service
              </a>
            </div>
          ) : null}
          {composerError ? <div className="status-banner status-banner-error">{composerError}</div> : null}
        </div>
      </div>
    </div>
  )
}
