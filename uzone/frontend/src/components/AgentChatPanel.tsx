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

function AssistantMessage({ customerName }: { customerName: string }) {
  const role = useAuiState((state) => state.message.role)
  const content = useAuiState((state) => state.message.content)
  const error = useAuiState((state) =>
    state.message.status?.type === 'incomplete' && state.message.status.reason === 'error'
      ? state.message.status.error
      : null,
  )
  const textContent = getMessageTextContent(content)

  return (
    <MessagePrimitive.Root
      className={`agent-chat-message ${
        role === 'assistant' ? 'agent-chat-message-assistant' : 'agent-chat-message-user'
      }`}
    >
      <div className="agent-chat-message-role">
        {role === 'assistant' ? `${customerName} Assistant` : 'You'}
      </div>
      <div className="assistant-ui-message-content">
        {role === 'assistant' ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{textContent}</ReactMarkdown>
        ) : (
          <div className="assistant-ui-user-content">{textContent}</div>
        )}
      </div>
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
  onNewChat,
  placeholder,
  variant,
}: {
  onNewChat: () => void
  placeholder: string
  variant: 'default' | 'chatgpt'
}) {
  const isRunning = useAuiState((state) => state.thread.isRunning)

  return (
    <ComposerPrimitive.Root className={`agent-chat-form assistant-ui-composer assistant-ui-composer-${variant}`}>
      <label className="field">
        <ComposerPrimitive.Input
          className="assistant-ui-input"
          rows={1}
          placeholder={placeholder}
          disabled={isRunning}
          submitMode="ctrlEnter"
        />
      </label>
      <div className="assistant-ui-composer-footer">
        <div className="assistant-ui-composer-hint">Press Ctrl+Enter to send. Enter adds a new line.</div>
        <div className="button-row">
          <ComposerPrimitive.Send className="button" type="button">
            {isRunning ? 'Sending…' : 'Send'}
          </ComposerPrimitive.Send>
          <AssistantToolbar onNewChat={onNewChat} />
        </div>
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

  const adapter = useMemo<ChatModelAdapter>(
    () => ({
      run: async ({ messages, abortSignal }) => {
        const trimmed = getLatestUserMessage(messages).trim()
        if (!trimmed) {
          return {
            content: [
              {
                type: 'text',
                text: 'Please enter a message before sending.',
              },
            ] satisfies ThreadAssistantMessagePart[],
          }
        }

        const body = new FormData()
        body.set('message', trimmed)
        body.set('stream', 'false')
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

        const response = await fetch(`${backendBase}/agents/${agentId}/runs`, {
          method: 'POST',
          body,
          signal: abortSignal,
        })

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as { detail?: string } | null
          throw new Error(payload?.detail || 'Unable to reach the assistant.')
        }

        const payload = (await response.json()) as AgentRunResponse
        sessionIdRef.current = typeof payload.session_id === 'string' ? payload.session_id : null

        return {
          content: [
            {
              type: 'text',
              text: getAssistantContent(payload) || 'The assistant returned an empty response.',
            },
          ] satisfies ThreadAssistantMessagePart[],
        }
      },
    }),
    [agentId, backendBase, clientId, customerName, surface],
  )

  const runtime = useLocalRuntime(adapter)

  return (
    <div className={variant === 'chatgpt' ? 'assistant-chat-card' : 'admin-list'}>
      {variant === 'chatgpt' ? (
        <div className="assistant-chat-card-header">
          <div>
            <div className="assistant-chat-card-title">{title}</div>
            <div className="assistant-chat-card-copy">{description}</div>
          </div>
        </div>
      ) : (
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
                  Ask a zoning question about {customerName}. The conversation stays scoped to this
                  customer&apos;s zoning knowledge.
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
            onNewChat={() => {
              sessionIdRef.current = null
            }}
            placeholder="What does the zoning code say about ADUs, setbacks, parking, or lot coverage?"
            variant={variant}
          />
        </div>
      </AssistantRuntimeProvider>
    </div>
  )
}
