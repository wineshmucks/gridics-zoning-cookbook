'use client'

import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
  useLocalRuntime,
  type ChatModelAdapter,
  type ChatModelRunResult,
  type ThreadAssistantMessagePart,
  type ThreadMessage,
} from '@assistant-ui/react'
import { useMemo, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type AgentRunResponse = {
  session_id?: string
  content?: unknown
  messages?: Array<{
    role?: string
    content?: unknown
  }>
}

type StreamStepStatus = 'running' | 'complete' | 'error'

type StreamStep = {
  id: string
  label: string
  detail?: string
  status: StreamStepStatus
}

type AssistantMetadata = {
  custom?: {
    runSteps?: StreamStep[]
    runState?: string
  }
}

type SSEEvent = {
  event: string
  data: Record<string, unknown>
}

function normalizeContent(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') {
          return item
        }
        if (item && typeof item === 'object' && 'text' in item && typeof item.text === 'string') {
          return item.text
        }
        return ''
      })
      .filter(Boolean)
      .join('\n\n')
  }

  if (value && typeof value === 'object') {
    return JSON.stringify(value, null, 2)
  }

  return ''
}

function getAssistantContent(payload: AgentRunResponse): string {
  const directContent = normalizeContent(payload.content)
  if (directContent) {
    return directContent
  }

  const assistantMessage = [...(payload.messages || [])]
    .reverse()
    .find((message) => message.role === 'assistant' || message.role === 'model')

  return normalizeContent(assistantMessage?.content)
}

function getLatestUserMessage(messages: readonly ThreadMessage[]): string {
  const latestUserMessage = [...messages].reverse().find((message) => message.role === 'user')
  if (!latestUserMessage) {
    return ''
  }

  return latestUserMessage.content
    .map((part) => (part.type === 'text' ? part.text : ''))
    .filter(Boolean)
    .join('\n\n')
}

function getMessageTextContent(parts: readonly { type: string; text?: string }[]): string {
  return parts
    .map((part) => (part.type === 'text' && typeof part.text === 'string' ? part.text : ''))
    .filter(Boolean)
    .join('\n\n')
}

function buildContent(text: string): ThreadAssistantMessagePart[] {
  return [
    {
      type: 'text',
      text,
    },
  ] satisfies ThreadAssistantMessagePart[]
}

function parseSSEEvents(chunk: string): { events: SSEEvent[]; remainder: string } {
  const blocks = chunk.split('\n\n')
  const remainder = blocks.pop() ?? ''
  const events: SSEEvent[] = []

  for (const block of blocks) {
    const lines = block.split('\n')
    let event = 'message'
    const dataLines: string[] = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        event = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }

    if (!dataLines.length) {
      continue
    }

    try {
      events.push({
        event,
        data: JSON.parse(dataLines.join('\n')) as Record<string, unknown>,
      })
    } catch {
      // Ignore malformed SSE payloads rather than breaking the full run.
    }
  }

  return { events, remainder }
}

function toStepLabel(toolName?: string): string {
  if (!toolName) {
    return 'Working'
  }

  if (toolName === 'query_customer_zoning_code') {
    return 'Lookup knowledge'
  }

  return toolName
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function toStepDetail(tool: Record<string, unknown> | undefined): string | undefined {
  if (!tool) {
    return undefined
  }

  const args = tool.tool_args
  if (!args || typeof args !== 'object') {
    return undefined
  }

  const toolArgs = args as Record<string, unknown>
  const query = typeof toolArgs.query === 'string' ? toolArgs.query.trim() : ''
  if (query) {
    return query
  }

  const limit = typeof toolArgs.limit === 'number' ? toolArgs.limit : null
  if (limit) {
    return `Searching top ${limit} matches`
  }

  return undefined
}

function summarizeToolResult(raw: unknown): string | undefined {
  if (typeof raw !== 'string') {
    return undefined
  }

  try {
    const parsed = JSON.parse(raw) as { results?: unknown[] }
    if (Array.isArray(parsed.results)) {
      return parsed.results.length === 1 ? '1 zoning source matched' : `${parsed.results.length} zoning sources matched`
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

function buildMetadata(steps: StreamStep[], runState: string): ChatModelRunResult['metadata'] {
  return {
    custom: {
      runSteps: steps,
      runState,
    },
  }
}

function buildStreamUpdate(
  content: string,
  steps: StreamStep[],
  runState: string,
  status?: ChatModelRunResult['status'],
): ChatModelRunResult {
  return {
    content: buildContent(content || (runState === 'error' ? 'The assistant run failed before returning any content.' : '')),
    metadata: buildMetadata(steps, runState),
    ...(status ? { status } : {}),
  }
}

function RunSteps() {
  const metadata = useAuiState((state) => state.message.metadata as AssistantMetadata)
  const status = useAuiState((state) => state.message.status)
  const steps = metadata?.custom?.runSteps ?? []

  if (!steps.length) {
    return null
  }

  return (
    <div className="assistant-run-steps">
      <div className="assistant-run-steps-label">
        {status?.type === 'complete' ? 'Run trace' : 'Live steps'}
      </div>
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
    </div>
  )
}

function AssistantMessage({ customerName }: { customerName: string }) {
  const role = useAuiState((state) => state.message.role)
  const content = useAuiState((state) => state.message.content)
  const status = useAuiState((state) => state.message.status)
  const error = useAuiState((state) =>
    state.message.status?.type === 'incomplete' && state.message.status.reason === 'error'
      ? state.message.status.error
      : null,
  )
  const textContent = getMessageTextContent(content)
  const isStreaming = role === 'assistant' && status?.type !== 'complete'

  return (
    <MessagePrimitive.Root
      className={`agent-chat-message ${
        role === 'assistant' ? 'agent-chat-message-assistant' : 'agent-chat-message-user'
      }`}
    >
      <div className="agent-chat-message-header">
        <div className="agent-chat-message-role">
          {role === 'assistant' ? `${customerName} Assistant` : 'You'}
        </div>
        {isStreaming ? <div className="agent-chat-message-status">Streaming</div> : null}
      </div>
      <div className="assistant-ui-message-content">
        {role === 'assistant' ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{textContent}</ReactMarkdown>
        ) : (
          <div className="assistant-ui-user-content">{textContent}</div>
        )}
      </div>
      {role === 'assistant' ? <RunSteps /> : null}
      <MessagePrimitive.Error>
        <div className="status-banner status-banner-error">
          {typeof error === 'string' ? error : 'Unable to reach the assistant.'}
        </div>
      </MessagePrimitive.Error>
    </MessagePrimitive.Root>
  )
}

function AssistantToolbar({ onNewChat }: { onNewChat: () => void }) {
  const aui = useAui()
  const isRunning = useAuiState((state) => state.thread.isRunning)

  return isRunning ? (
    <ComposerPrimitive.Cancel className="button secondary" type="button">
      Stop
    </ComposerPrimitive.Cancel>
  ) : (
    <button
      className="button secondary"
      type="button"
      onClick={() => {
        onNewChat()
        aui.thread().reset()
      }}
    >
      New Chat
    </button>
  )
}

function AssistantComposer({
  placeholder,
  variant,
}: {
  placeholder: string
  variant: 'default' | 'chatgpt'
}) {
  const isRunning = useAuiState((state) => state.thread.isRunning)

  return (
    <ComposerPrimitive.Root className={`agent-chat-form assistant-ui-composer assistant-ui-composer-${variant}`}>
      <div className="assistant-ui-composer-row">
        <label className="field assistant-ui-input-wrap">
          <ComposerPrimitive.Input
            className="assistant-ui-input"
            rows={1}
            placeholder={placeholder}
            disabled={isRunning}
            submitMode="ctrlEnter"
          />
          <ComposerPrimitive.Send
            className="assistant-ui-send-button"
            type="button"
            aria-label={isRunning ? 'Sending' : 'Send message'}
          >
            {isRunning ? '...' : '->'}
          </ComposerPrimitive.Send>
        </label>
      </div>
      <div className="assistant-ui-composer-footer">
        <div className="assistant-ui-composer-hint">Ctrl+Enter to send. Enter for a new line.</div>
      </div>
    </ComposerPrimitive.Root>
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
  variant = 'default',
}: {
  agentId: string
  backendBase: string
  customerName: string
  clientId: string
  surface: string
  title: string
  description: string
  variant?: 'default' | 'chatgpt'
}) {
  const sessionIdRef = useRef<string | null>(null)
  const runIdRef = useRef<string | null>(null)

  const adapter = useMemo<ChatModelAdapter>(
    () => ({
      run: async function* ({ messages, abortSignal }) {
        const trimmed = getLatestUserMessage(messages).trim()
        if (!trimmed) {
          yield {
            content: buildContent('Please enter a message before sending.'),
            status: {
              type: 'complete',
              reason: 'stop',
            },
          }
          return
        }

        const body = new FormData()
        body.set('message', trimmed)
        body.set('stream', 'true')
        if (sessionIdRef.current) {
          body.set('session_id', sessionIdRef.current)
        }
        body.set(
          'dependencies',
          JSON.stringify({
            client_id: clientId,
            customer_name: customerName,
          }),
        )
        body.set(
          'metadata',
          JSON.stringify({
            surface,
            client_id: clientId,
          }),
        )

        let response: Response
        try {
          response = await fetch(`${backendBase}/agents/${agentId}/runs`, {
            method: 'POST',
            body,
            signal: abortSignal,
            headers: {
              Accept: 'text/event-stream',
            },
          })
        } catch (error) {
          throw error
        }

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as { detail?: string } | null
          throw new Error(payload?.detail || 'Unable to reach the assistant.')
        }

        if (!response.body) {
          const payload = (await response.json().catch(() => null)) as AgentRunResponse | null
          sessionIdRef.current = payload?.session_id ?? null
          yield {
            content: buildContent(getAssistantContent(payload || {}) || 'The assistant returned an empty response.'),
            status: {
              type: 'complete',
              reason: 'stop',
            },
          }
          return
        }

        let cancelled = false
        const cancelRemoteRun = () => {
          cancelled = true
          if (!runIdRef.current) {
            return
          }

          void fetch(`${backendBase}/agents/${agentId}/runs/${runIdRef.current}/cancel`, {
            method: 'POST',
            keepalive: true,
          }).catch(() => null)
        }

        abortSignal.addEventListener('abort', cancelRemoteRun, { once: true })

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let textContent = ''
        let runSteps: StreamStep[] = [
          {
            id: 'run-started',
            label: 'Preparing answer',
            detail: 'Opening an agent run for this tenant-scoped conversation',
            status: 'running',
          },
        ]

        yield buildStreamUpdate(textContent, runSteps, 'starting')

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
              const payload = event.data
              const maybeSessionId = typeof payload.session_id === 'string' ? payload.session_id : null
              const maybeRunId = typeof payload.run_id === 'string' ? payload.run_id : null
              if (maybeSessionId) {
                sessionIdRef.current = maybeSessionId
              }
              if (maybeRunId) {
                runIdRef.current = maybeRunId
              }

              if (event.event === 'RunStarted') {
                const model = typeof payload.model === 'string' ? payload.model : 'configured model'
                runSteps = upsertStep(runSteps, {
                  id: 'run-started',
                  label: 'Preparing answer',
                  detail: `Connected to ${model}`,
                  status: 'complete',
                })
                runSteps = upsertStep(runSteps, {
                  id: 'model-request',
                  label: 'Drafting response',
                  detail: 'The assistant is planning the answer',
                  status: 'running',
                })
                yield buildStreamUpdate(textContent, runSteps, 'running')
                continue
              }

              if (event.event === 'ToolCallStarted') {
                const tool =
                  payload.tool && typeof payload.tool === 'object' ? (payload.tool as Record<string, unknown>) : undefined
                const toolId =
                  typeof tool?.tool_call_id === 'string'
                    ? tool.tool_call_id
                    : `tool-${typeof tool?.tool_name === 'string' ? tool.tool_name : runSteps.length}`
                runSteps = upsertStep(runSteps, {
                  id: toolId,
                  label: toStepLabel(typeof tool?.tool_name === 'string' ? tool.tool_name : undefined),
                  detail: toStepDetail(tool),
                  status: 'running',
                })
                yield buildStreamUpdate(textContent, runSteps, 'running')
                continue
              }

              if (event.event === 'ToolCallCompleted') {
                const tool =
                  payload.tool && typeof payload.tool === 'object' ? (payload.tool as Record<string, unknown>) : undefined
                const toolId =
                  typeof tool?.tool_call_id === 'string'
                    ? tool.tool_call_id
                    : `tool-${typeof tool?.tool_name === 'string' ? tool.tool_name : runSteps.length}`
                runSteps = upsertStep(runSteps, {
                  id: toolId,
                  label: toStepLabel(typeof tool?.tool_name === 'string' ? tool.tool_name : undefined),
                  detail: summarizeToolResult(tool?.result) || toStepDetail(tool),
                  status: 'complete',
                })
                yield buildStreamUpdate(textContent, runSteps, 'running')
                continue
              }

              if (event.event === 'ToolCallError') {
                const tool =
                  payload.tool && typeof payload.tool === 'object' ? (payload.tool as Record<string, unknown>) : undefined
                const toolId =
                  typeof tool?.tool_call_id === 'string'
                    ? tool.tool_call_id
                    : `tool-${typeof tool?.tool_name === 'string' ? tool.tool_name : runSteps.length}`
                runSteps = upsertStep(runSteps, {
                  id: toolId,
                  label: toStepLabel(typeof tool?.tool_name === 'string' ? tool.tool_name : undefined),
                  detail: typeof payload.error === 'string' ? payload.error : 'Tool execution failed',
                  status: 'error',
                })
                yield buildStreamUpdate(textContent, runSteps, 'error')
                continue
              }

              if (event.event === 'RunContent') {
                textContent += normalizeContent(payload.content)
                yield buildStreamUpdate(textContent, runSteps, 'running')
                continue
              }

              if (event.event === 'RunCompleted') {
                const finalContent = normalizeContent(payload.content)
                if (finalContent && finalContent.length >= textContent.length) {
                  textContent = finalContent
                }
                runSteps = upsertStep(runSteps, {
                  id: 'model-request',
                  label: 'Drafting response',
                  detail: 'Answer completed',
                  status: 'complete',
                })
                yield buildStreamUpdate(textContent || 'The assistant returned an empty response.', runSteps, 'complete', {
                  type: 'complete',
                  reason: 'stop',
                })
                runIdRef.current = null
                return
              }

              if (event.event === 'RunError') {
                runSteps = upsertStep(runSteps, {
                  id: 'model-request',
                  label: 'Drafting response',
                  detail: typeof payload.content === 'string' ? payload.content : 'The run failed unexpectedly',
                  status: 'error',
                })
                yield buildStreamUpdate(textContent, runSteps, 'error', {
                  type: 'incomplete',
                  reason: 'error',
                  error:
                    typeof payload.content === 'string' && payload.content
                      ? payload.content
                      : 'Unable to reach the assistant.',
                })
                runIdRef.current = null
                return
              }
            }
          }

          if (cancelled) {
            return
          }

          yield buildStreamUpdate(textContent || 'The assistant returned an empty response.', runSteps, 'complete', {
            type: 'complete',
            reason: 'stop',
          })
        } finally {
          abortSignal.removeEventListener('abort', cancelRemoteRun)
          runIdRef.current = null
          reader.releaseLock()
        }
      },
    }),
    [agentId, backendBase, clientId, customerName, surface],
  )

  const runtime = useLocalRuntime(adapter)

  return (
    <div className={variant === 'chatgpt' ? 'assistant-chat-card' : 'admin-list'}>
      {variant === 'chatgpt' ? null : (
        <>
          <div className="admin-list-heading">{title}</div>
          <div style={{ color: 'var(--muted)', marginBottom: 12 }}>{description}</div>
        </>
      )}

      <AssistantRuntimeProvider runtime={runtime}>
        <div className={`agent-chat-shell assistant-ui-shell agent-chat-shell-${variant}`}>
          <ThreadPrimitive.Root className="assistant-ui-thread">
            <ThreadPrimitive.Viewport className={`agent-chat-log assistant-ui-viewport agent-chat-log-${variant}`}>
              <ThreadPrimitive.Empty>
                <div className="agent-chat-empty">
                  <div className="agent-chat-empty-title">Ask anything about {customerName} zoning</div>
                  <p>
                    Answers stream in as they are generated, and the assistant now exposes its live
                    knowledge lookup steps while it works.
                  </p>
                </div>
              </ThreadPrimitive.Empty>
              <ThreadPrimitive.Messages
                components={{
                  Message: () => <AssistantMessage customerName={customerName} />,
                }}
              />
            </ThreadPrimitive.Viewport>
          </ThreadPrimitive.Root>

          <AssistantComposer
            placeholder="Ask about setbacks, ADUs, parking, overlays, lot coverage, or permitted uses..."
            variant={variant}
          />
        </div>
      </AssistantRuntimeProvider>
    </div>
  )
}
