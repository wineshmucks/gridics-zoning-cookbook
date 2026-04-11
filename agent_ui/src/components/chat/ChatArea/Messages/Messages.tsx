import type { ChatMessage } from '@/types/os'

import { AgentMessage, UserMessage } from './MessageItem'
import Tooltip from '@/components/ui/tooltip'
import { memo, useMemo, useState } from 'react'
import {
  ToolCallProps,
  ReasoningStepProps,
  ReasoningProps,
  ReferenceData,
  Reference
} from '@/types/os'
import React, { type FC } from 'react'

import Icon from '@/components/ui/icon'
import ChatBlankState from './ChatBlankState'

interface MessageListProps {
  messages: ChatMessage[]
}

interface MessageWrapperProps {
  message: ChatMessage
  isLastMessage: boolean
}

interface ReferenceProps {
  references: ReferenceData[]
}

interface ReferenceItemProps {
  reference: Reference
}

const ReferenceItem: FC<ReferenceItemProps> = ({ reference }) => (
  <div className="relative flex h-[63px] w-[190px] cursor-default flex-col justify-between overflow-hidden rounded-md bg-background-secondary p-3 transition-colors hover:bg-background-secondary/80">
    <p className="text-sm font-medium text-primary">{reference.name}</p>
    <p className="truncate text-xs text-primary/40">{reference.content}</p>
  </div>
)

const References: FC<ReferenceProps> = ({ references }) => (
  <div className="flex flex-col gap-4">
    {references.map((referenceData, index) => (
      <div
        key={`${referenceData.query}-${index}`}
        className="flex flex-col gap-3"
      >
        <div className="flex flex-wrap gap-3">
          {referenceData.references.map((reference, refIndex) => (
            <ReferenceItem
              key={`${reference.name}-${reference.meta_data.chunk}-${refIndex}`}
              reference={reference}
            />
          ))}
        </div>
      </div>
    ))}
  </div>
)

const AgentMessageWrapper = ({ message }: MessageWrapperProps) => {
  return (
    <div className="flex flex-col gap-y-9">
      {message.extra_data?.reasoning_steps &&
        message.extra_data.reasoning_steps.length > 0 && (
          <div className="flex items-start gap-4">
            <Tooltip
              delayDuration={0}
              content={<p className="text-accent">Reasoning</p>}
              side="top"
            >
              <Icon type="reasoning" size="sm" />
            </Tooltip>
            <div className="flex flex-col gap-3">
              <p className="text-xs uppercase">Reasoning</p>
              <Reasonings reasoning={message.extra_data.reasoning_steps} />
            </div>
          </div>
        )}
      {message.extra_data?.references &&
        message.extra_data.references.length > 0 && (
          <div className="flex items-start gap-4">
            <Tooltip
              delayDuration={0}
              content={<p className="text-accent">References</p>}
              side="top"
            >
              <Icon type="references" size="sm" />
            </Tooltip>
            <div className="flex flex-col gap-3">
              <References references={message.extra_data.references} />
            </div>
          </div>
        )}
      {message.tool_calls && message.tool_calls.length > 0 && (
        <div className="flex items-start gap-3">
          <Tooltip
            delayDuration={0}
            content={<p className="text-accent">Tool Calls</p>}
            side="top"
          >
            <Icon
              type="hammer"
              className="rounded-lg bg-background-secondary p-1"
              size="sm"
              color="secondary"
            />
          </Tooltip>

          <div className="flex flex-wrap gap-2">
            {message.tool_calls.map((toolCall, index) => (
              <ToolComponent
                key={
                  toolCall.tool_call_id ||
                  `${toolCall.tool_name}-${toolCall.created_at}-${index}`
                }
                tools={toolCall}
              />
            ))}
          </div>
        </div>
      )}
      <AgentMessage message={message} />
    </div>
  )
}
const Reasoning: FC<ReasoningStepProps> = ({ index, stepTitle }) => (
  <div className="flex items-center gap-2 text-secondary">
    <div className="flex h-[20px] items-center rounded-md bg-background-secondary p-2">
      <p className="text-xs">STEP {index + 1}</p>
    </div>
    <p className="text-xs">{stepTitle}</p>
  </div>
)
const Reasonings: FC<ReasoningProps> = ({ reasoning }) => (
  <div className="flex flex-col items-start justify-center gap-2">
    {reasoning.map((title, index) => (
      <Reasoning
        key={`${title.title}-${title.action}-${index}`}
        stepTitle={title.title}
        index={index}
      />
    ))}
  </div>
)

const formatJsonBlock = (value: unknown): string => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

type GridicsTraceRequest = {
  method?: string
  path?: string
  url?: string
  params?: Record<string, unknown>
  headers?: Record<string, unknown>
}

type GridicsTraceResponse = {
  status_code?: number
  body?: string
  json?: unknown
}

type GridicsTraceEntry = {
  request?: GridicsTraceRequest
  response?: GridicsTraceResponse
  error?: string
}

const parseMaybeJson = (value: unknown): unknown => {
  if (typeof value !== 'string') return value
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

const parsePythonLikeObject = (value: unknown): unknown => {
  if (typeof value !== 'string') return value
  const trimmed = value.trim()
  if (!trimmed || !['{', '['].includes(trimmed[0])) return value

  let converted = ''
  let inSingle = false
  let escaped = false

  for (const ch of trimmed) {
    if (inSingle) {
      if (escaped) {
        converted += ch
        escaped = false
        continue
      }
      if (ch === '\\') {
        converted += ch
        escaped = true
        continue
      }
      if (ch === "'") {
        converted += '"'
        inSingle = false
        continue
      }
      converted += ch
      continue
    }

    if (ch === "'") {
      converted += '"'
      inSingle = true
      continue
    }
    converted += ch
  }

  converted = converted
    .replace(/\\'/g, "'")
    .replace(/\bNone\b/g, 'null')
    .replace(/\bTrue\b/g, 'true')
    .replace(/\bFalse\b/g, 'false')

  try {
    return JSON.parse(converted)
  } catch {
    return value
  }
}

const extractGridicsTrace = (value: unknown): GridicsTraceEntry[] => {
  const parsed = parsePythonLikeObject(parseMaybeJson(value))
  if (!parsed || typeof parsed !== 'object') return []

  const obj = parsed as Record<string, unknown>
  const traceValue = obj['_gridics_api_trace'] ?? obj['gridics_api_trace']
  if (!Array.isArray(traceValue)) return []

  return traceValue as GridicsTraceEntry[]
}

const formatToolDuration = (seconds: number | undefined): string | null => {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds) || seconds < 0) {
    return null
  }

  if (seconds >= 1) {
    return `${seconds.toFixed(seconds >= 10 ? 1 : 2)}s`
  }

  return `${Math.round(seconds * 1000)}ms`
}

const ToolComponent = memo(({ tools }: ToolCallProps) => {
  const [showDetails, setShowDetails] = useState(false)
  const toolResponseSource = tools.result ?? tools.content
  const toolDuration = formatToolDuration(tools.metrics?.time)
  const requestDetails = useMemo(
    () => formatJsonBlock(tools.tool_args),
    [tools.tool_args]
  )
  const responseDetails = useMemo(
    () => formatJsonBlock(toolResponseSource),
    [toolResponseSource]
  )
  const gridicsTrace = useMemo(
    () => extractGridicsTrace(toolResponseSource),
    [toolResponseSource]
  )
  const hasGridicsTrace = gridicsTrace.length > 0
  const canShowDetails = Boolean(requestDetails || responseDetails)

  return (
    <div className="flex max-w-full flex-col gap-2 rounded-xl bg-accent px-3 py-2 text-xs">
      <div className="flex items-center gap-2">
        <p className="font-dmmono uppercase text-primary/80">{tools.tool_name}</p>
        {toolDuration && (
          <span className="rounded-full border border-primary/20 px-2 py-0.5 text-[10px] uppercase text-primary/60">
            {toolDuration}
          </span>
        )}
        {canShowDetails && (
          <button
            type="button"
            onClick={() => setShowDetails((prev) => !prev)}
            className="rounded-md border border-primary/20 px-2 py-0.5 text-[10px] uppercase text-primary/70 transition hover:bg-primary/10"
          >
            {showDetails ? 'Hide Details' : 'View Details'}
          </button>
        )}
      </div>
      {showDetails && canShowDetails && (
        <div className="space-y-2">
          {toolDuration && (
            <div className="rounded-md bg-background p-2">
              <p className="mb-1 text-[10px] uppercase text-primary/60">Duration</p>
              <p className="text-[11px] text-primary/80">{toolDuration}</p>
            </div>
          )}
          <div className="rounded-md border border-primary/20 bg-background p-2">
            <p className="mb-2 text-[10px] uppercase text-primary/60">Gridics API Trace</p>
            {hasGridicsTrace ? (
              <div className="space-y-2">
                {gridicsTrace.map((entry, index) => (
                  <div key={`${tools.tool_name}-trace-${index}`} className="rounded-md bg-accent p-2">
                    <p className="mb-1 text-[10px] uppercase text-primary/60">Call {index + 1}</p>
                    {entry.request && (
                      <div className="mb-2 rounded-md bg-background p-2">
                        <p className="mb-1 text-[10px] uppercase text-primary/60">Request</p>
                        <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words text-[11px] text-primary/80">
                          {formatJsonBlock(entry.request)}
                        </pre>
                      </div>
                    )}
                    {(entry.response || entry.error) && (
                      <div className="rounded-md bg-background p-2">
                        <p className="mb-1 text-[10px] uppercase text-primary/60">Response</p>
                        <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words text-[11px] text-primary/80">
                          {entry.error
                            ? entry.error
                            : formatJsonBlock(entry.response)}
                        </pre>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-primary/60">
                No Gridics trace found in this tool response.
              </p>
            )}
          </div>
          {requestDetails && (
            <div className="rounded-md bg-background p-2">
              <p className="mb-1 text-[10px] uppercase text-primary/60">Request</p>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words text-[11px] text-primary/80">
                {requestDetails}
              </pre>
            </div>
          )}
          {responseDetails && (
            <div className="rounded-md bg-background p-2">
              <p className="mb-1 text-[10px] uppercase text-primary/60">Response</p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words text-[11px] text-primary/80">
                {responseDetails}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
})
ToolComponent.displayName = 'ToolComponent'
const Messages = ({ messages }: MessageListProps) => {
  if (messages.length === 0) {
    return <ChatBlankState />
  }

  return (
    <>
      {messages.map((message, index) => {
        const key = `${message.role}-${message.created_at}-${index}`
        const isLastMessage = index === messages.length - 1

        if (message.role === 'agent') {
          return (
            <AgentMessageWrapper
              key={key}
              message={message}
              isLastMessage={isLastMessage}
            />
          )
        }
        return <UserMessage key={key} message={message} />
      })}
    </>
  )
}

export default Messages
