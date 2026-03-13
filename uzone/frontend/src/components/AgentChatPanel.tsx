'use client'

import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type AgentRunResponse = {
  session_id?: string
  run_id?: string
  content?: unknown
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
  detail?: string
  status: StreamStepStatus
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  steps?: StreamStep[]
  toolCalls?: StreamToolCall[]
  status?: 'streaming' | 'complete' | 'error'
  error?: string | null
}

type SSEEvent = {
  event: string
  data: Record<string, unknown>
}

function formatConversation(messages: ChatMessage[], customerName: string): string {
  return messages
    .map((message) => {
      const speaker = message.role === "user" ? "You" : `${customerName} Assistant`
      const sections = [`${speaker}\n${message.content || "(no visible message content)"}`]

      if (message.toolCalls?.length) {
        sections.push(
          [
            "Tool activity",
            ...message.toolCalls.map((toolCall) =>
              `- ${toolCall.label}${toolCall.detail ? `: ${toolCall.detail}` : ""} [${toolCall.status}]`,
            ),
          ].join("\n"),
        )
      }

      if (message.steps?.length) {
        sections.push(
          [
            "Run timeline",
            ...message.steps.map((step) => `- ${step.label}${step.detail ? `: ${step.detail}` : ""} [${step.status}]`),
          ].join("\n"),
        )
      }

      return sections.join("\n\n")
    })
    .join("\n\n---\n\n")
}

function normalizeContent(value: unknown): string {
  const visited = new WeakSet<object>()

  const collectText = (input: unknown): string[] => {
    if (typeof input === "string") {
      const trimmed = input.trim()
      return trimmed ? [trimmed] : []
    }

    if (typeof input === "number" || typeof input === "boolean") {
      return [String(input)]
    }

    if (Array.isArray(input)) {
      return input.flatMap((item) => collectText(item))
    }

    if (!input || typeof input !== "object") {
      return []
    }

    if (visited.has(input)) {
      return []
    }
    visited.add(input)

    const record = input as Record<string, unknown>
    const prioritizedKeys = [
      "output_text",
      "text",
      "content",
      "value",
      "markdown",
      "response",
      "message",
      "parts",
      "blocks",
      "items",
      "results",
    ]

    const prioritized = prioritizedKeys.flatMap((key) => (key in record ? collectText(record[key]) : []))
    if (prioritized.length) {
      return prioritized
    }

    return Object.values(record).flatMap((item) => collectText(item))
  }

  const extracted = collectText(value)
    .map((item) => item.trim())
    .filter(Boolean)

  if (extracted.length) {
    return extracted.join("\n\n")
  }

  if (typeof value === "string") {
    return value
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return item
        }
        if (item && typeof item === "object" && "text" in item && typeof item.text === "string") {
          return item.text
        }
        return ""
      })
      .filter(Boolean)
      .join("\n\n")
  }

  if (value && typeof value === "object") {
    return JSON.stringify(value, null, 2)
  }

  return ""
}

function sanitizeAssistantContent(text: string): string {
  if (!text) {
    return ""
  }

  let sanitized = text

  sanitized = sanitized.replace(/<tool_call>[\s\S]*?<\/tool_call>/gi, "")
  sanitized = sanitized.replace(/<function=[^>]+>[\s\S]*?<\/function>/gi, "")
  sanitized = sanitized.replace(/<parameter=[^>]+>[\s\S]*?<\/parameter>/gi, "")
  sanitized = sanitized.replace(/\banalyze_customer_zoning_request\(\.\.\.\) completed in [0-9.]+s\.?\s*/gi, "")
  sanitized = sanitized.replace(/\bquery_customer_zoning_code\(\.\.\.\) completed in [0-9.]+s\.?\s*/gi, "")

  return sanitized.trim()
}

function getAssistantContent(payload: AgentRunResponse): string {
  const directContent = sanitizeAssistantContent(normalizeContent(payload.content))
  if (directContent) {
    return directContent
  }

  const assistantMessage = [...(payload.messages || [])]
    .reverse()
    .find((message) => message.role === "assistant" || message.role === "model")

  return sanitizeAssistantContent(normalizeContent(assistantMessage?.content))
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
  if (typeof raw !== "string") {
    return undefined
  }

  try {
    const parsed = JSON.parse(raw) as {
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
  backendBase: string,
  agentId: string,
  runId: string,
  sessionId: string | null,
): Promise<CompletedRunFetchResult> {
  if (!sessionId) {
    return {
      payload: null,
      debug: "Completed run lookup was skipped because no session_id was available.",
    }
  }

  try {
    const response = await fetch(
      `${backendBase}/agents/${agentId}/runs/${runId}?session_id=${encodeURIComponent(sessionId)}`,
      {
        cache: "no-store",
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

function RunSteps({ steps, status }: { steps?: StreamStep[]; status?: ChatMessage["status"] }) {
  const [isOpen, setIsOpen] = useState(false)

  if (!steps?.length) {
    return null
  }

  return (
    <div className="assistant-run-steps">
      <button
        className="assistant-run-toggle"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
      >
        <span className="assistant-run-steps-label">{status === "complete" ? "Run timeline" : "In progress"}</span>
        <span className="assistant-run-toggle-copy">
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

  return (
    <div className="assistant-run-steps assistant-tool-calls">
      <button
        className="assistant-run-toggle"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
      >
        <span className="assistant-run-steps-label">Tool activity</span>
        <span className="assistant-run-toggle-copy">
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
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function AgentChatPanel({
  agentId,
  backendBase,
  customerName,
  clientId,
  surface,
  title,
  description,
  variant = "default",
}: {
  agentId: string
  backendBase: string
  customerName: string
  clientId: string
  surface: string
  title: string
  description: string
  variant?: "default" | "chatgpt"
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const [composerError, setComposerError] = useState<string | null>(null)
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle")
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const runIdRef = useRef<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) {
      return
    }
    viewport.scrollTop = viewport.scrollHeight
  }, [messages])

  const updateAssistantMessage = (messageId: string, updater: (message: ChatMessage) => ChatMessage): void => {
    setMessages((prevMessages) =>
      prevMessages.map((message) => (message.id === messageId ? updater(message) : message)),
    )
  }

  const sendMessage = async () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming) {
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
      }

      if (event.event === "RunStarted") {
        const model = typeof payload.model === "string" ? payload.model : "configured model"
        runSteps = upsertStep(runSteps, {
          id: "run-started",
          label: "Preparing answer",
          detail: `Connected to ${model}`,
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

      if (event.event === "ModelRequestStarted") {
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

      if (event.event === "ModelRequestCompleted") {
        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: answerPhaseStarted ? "Writing final answer" : "Drafting response",
          detail: answerPhaseStarted ? "Final answer draft completed" : "Planning completed",
          status: "complete",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (event.event === "ToolCallStarted") {
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
          detail: toStepDetail(tool),
          status: "running",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (event.event === "ToolCallCompleted") {
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
          detail: summarizeToolResult(tool?.result) || toStepDetail(tool),
          status: "complete",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls })
        return false
      }

      if (event.event === "ToolCallError") {
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
          detail: typeof payload.error === "string" ? payload.error : "Tool execution failed",
          status: "error",
        })
        handleStreamUpdate({ steps: runSteps, toolCalls, status: "error" })
        return false
      }

      if (event.event === "RunContent") {
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

      if (event.event === "RunContentCompleted") {
        handleStreamUpdate({ steps: runSteps, toolCalls, status: "streaming" })
        return false
      }

      if (event.event === "RunCompleted") {
        let debugDetail: string | null = null
        let finalContent = sanitizeAssistantContent(
          normalizeContent(payload.content) || getAssistantContent(payload as AgentRunResponse),
        )

        if (!finalContent && runIdRef.current) {
          const completedRun = await fetchCompletedRun(backendBase, agentId, runIdRef.current, sessionIdRef.current)
          debugDetail = completedRun.debug
          const fetchedContent = getAssistantContent(completedRun.payload || {})
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

        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: "Drafting response",
          detail: "Answer completed",
          status: "complete",
        })
        runSteps = appendDebugStep(runSteps, debugDetail)
        handleStreamUpdate({
          content: finalContent || textContent || provisionalContent || lastVisibleContent || buildEmptyAssistantResponse(debugDetail),
          steps: runSteps,
          toolCalls,
          status: "complete",
        })
        return true
      }

      if (event.event === "RunError") {
        const errorMessage =
          typeof payload.content === "string" && payload.content ? payload.content : "Unable to reach the assistant."
        runSteps = upsertStep(runSteps, {
          id: "model-request",
          label: "Drafting response",
          detail: errorMessage,
          status: "error",
        })
        handleStreamUpdate({
          content: textContent || lastVisibleContent || "The assistant run failed before returning any content.",
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
      const response = await fetch(`${backendBase}/agents/${agentId}/runs`, {
        method: "POST",
        body,
        signal: controller.signal,
        headers: {
          Accept: "text/event-stream",
        },
      })

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null
        throw new Error(payload?.detail || "Unable to reach the assistant.")
      }

      if (!response.body) {
        const payload = (await response.json().catch(() => null)) as AgentRunResponse | null
        sessionIdRef.current = payload?.session_id ?? null
        handleStreamUpdate({
          content: getAssistantContent(payload || {}) || "The assistant returned an empty response.",
          status: "complete",
          steps: upsertStep(runSteps, {
            id: "model-request",
            label: "Drafting response",
            detail: "Answer completed",
            status: "complete",
          }),
          toolCalls,
        })
        return
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
          const completedRun = await fetchCompletedRun(backendBase, agentId, runIdRef.current, sessionIdRef.current)
          debugDetail = completedRun.debug
          fallbackContent = getAssistantContent(completedRun.payload || {})
          runSteps = appendDebugStep(runSteps, debugDetail)
        }

        handleStreamUpdate({
          content: fallbackContent || buildEmptyAssistantResponse(debugDetail),
          status: "complete",
          steps: runSteps,
          toolCalls,
        })
      }
    } catch (error) {
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
  }

  const handleCopyConversation = async () => {
    if (!messages.length) {
      setCopyState("error")
      return
    }

    try {
      await navigator.clipboard.writeText(formatConversation(messages, customerName))
      setCopyState("copied")
    } catch {
      setCopyState("error")
    }

    window.setTimeout(() => {
      setCopyState("idle")
    }, 2000)
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
        <div ref={viewportRef} className={`agent-chat-log agent-chat-log-${variant}`}>
          {messages.length === 0 ? (
            <div className="agent-chat-empty">
              <div className="agent-chat-empty-title">Ask anything about {customerName} zoning</div>
              <p>Answers stream in as they are generated, and the assistant exposes its live lookup steps while it works.</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`agent-chat-message agent-chat-message-${message.role}`}
                data-message-id={message.id}
              >
                <div className="agent-chat-message-header">
                  <div className="agent-chat-message-role">
                    {message.role === "user" ? "You" : `${customerName} Assistant`}
                  </div>
                  {message.role === "assistant" && message.status === "streaming" ? (
                    <div className="agent-chat-message-status">Streaming</div>
                  ) : null}
                </div>
                <div className="assistant-ui-message-content">
                  {message.role === "user" ? (
                    <div className="assistant-ui-user-content">{message.content}</div>
                  ) : message.content ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                  ) : message.status === "streaming" ? (
                    <div className="assistant-answer-placeholder">Preparing final answer...</div>
                  ) : (
                    <div className="assistant-answer-placeholder">No answer text was returned.</div>
                  )}
                </div>
                {message.role === "assistant" ? <ToolCallList toolCalls={message.toolCalls} /> : null}
                {message.role === "assistant" ? <RunSteps steps={message.steps} status={message.status} /> : null}
                {message.role === "assistant" && message.error ? (
                  <div className="status-banner status-banner-error">{message.error}</div>
                ) : null}
              </div>
            ))
          )}
        </div>

        <div className={`agent-chat-form assistant-ui-composer assistant-ui-composer-${variant}`}>
          <div className="assistant-ui-composer-row">
            <label className="field assistant-ui-input-wrap">
              <textarea
                name="input"
                className="assistant-ui-input"
                rows={1}
                placeholder="Ask about setbacks, ADUs, parking, overlays, lot coverage, or permitted uses..."
                value={input}
                disabled={isStreaming}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
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
                {isStreaming ? "..." : "->"}
              </button>
            </label>
          </div>
          <div className="assistant-ui-composer-footer">
            <div className="assistant-ui-composer-hint">Ctrl+Enter to send. Enter for a new line.</div>
            <button className="button secondary" type="button" onClick={() => void handleCopyConversation()}>
              {copyState === "copied" ? "Copied" : copyState === "error" ? "Copy Failed" : "Copy Conversation"}
            </button>
            <button className="button secondary" type="button" onClick={handleNewChat} disabled={isStreaming && !messages.length}>
              {isStreaming ? "Stop & Reset" : "New Chat"}
            </button>
          </div>
          {composerError ? <div className="status-banner status-banner-error">{composerError}</div> : null}
        </div>
      </div>
    </div>
  )
}
