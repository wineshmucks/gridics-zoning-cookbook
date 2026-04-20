'use client'

import { useEffect, useState } from 'react'

type AgentPromptField = {
  id: string
  label: string
  description: string
  fieldName: string
}

type AgentPromptEditorProps = {
  field: AgentPromptField
  subtitle?: string
  modelSummary?: string
  value: string
  defaultPrompt: string
  defaultPromptLabel: string
  editLabel: string
  resetLabel: string
  onChange: (value: string) => void
  onReset: () => void
}

function normalizePrompt(value: string) {
  return value.trim()
}

export function AgentPromptEditor({
  field,
  subtitle,
  modelSummary,
  value,
  defaultPrompt,
  defaultPromptLabel,
  editLabel,
  resetLabel,
  onChange,
  onReset,
}: AgentPromptEditorProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [draftValue, setDraftValue] = useState(value || defaultPrompt)
  const trimmedValue = normalizePrompt(value)
  const trimmedDefault = normalizePrompt(defaultPrompt)
  const hasOverride = trimmedValue.length > 0 && trimmedValue !== trimmedDefault
  const matchesDefault = trimmedValue.length > 0 && trimmedValue === trimmedDefault
  const usingDefault = trimmedValue.length === 0
  const statusLabel = usingDefault
    ? `Using ${defaultPromptLabel}`
    : matchesDefault
      ? `Matches ${defaultPromptLabel}`
      : 'Overridden'
  const statusClassName = usingDefault
    ? 'is-inherited'
    : matchesDefault
      ? 'is-default'
      : 'is-overridden'
  const displayPrompt = usingDefault ? defaultPrompt : value

  useEffect(() => {
    if (isEditing) {
      return
    }
    setDraftValue(value || defaultPrompt)
  }, [defaultPrompt, isEditing, value])

  function beginEditing() {
    setDraftValue(value || defaultPrompt)
    setIsEditing(true)
  }

  function cancelEditing() {
    setDraftValue(value || defaultPrompt)
    setIsEditing(false)
  }

  function saveEditing() {
    const normalizedDraft = normalizePrompt(draftValue)
    if (!normalizedDraft) {
      onReset()
      setIsEditing(false)
      return
    }
    onChange(normalizedDraft === trimmedDefault ? '' : draftValue)
    setIsEditing(false)
  }

  return (
    <article className="card admin-agent-prompt-card">
      <div className="admin-agent-prompt-card-head">
        <div className="admin-agent-prompt-card-title-wrap">
          {subtitle ? <span className="admin-agent-prompt-eyebrow">{subtitle}</span> : null}
          <strong>{field.label}</strong>
          {modelSummary ? <span className="admin-agent-prompt-model">{modelSummary}</span> : null}
          <span className={`admin-agent-prompt-status ${statusClassName}`}>{statusLabel}</span>
        </div>
        <div className="admin-agent-prompt-actions">
          {isEditing ? (
            <>
              <button className="button button-fit" type="button" onClick={saveEditing}>
                Save
              </button>
              <button className="button secondary button-fit" type="button" onClick={cancelEditing}>
                Cancel
              </button>
            </>
          ) : (
            <button className="button secondary button-fit" type="button" onClick={beginEditing}>
              {editLabel}
            </button>
          )}
          <button className="button secondary button-fit" type="button" onClick={onReset} disabled={usingDefault}>
            {resetLabel}
          </button>
        </div>
      </div>

      {isEditing ? (
        <label className="field field-full admin-agent-prompt-input">
          <span>Edit override</span>
          <textarea
            name={field.fieldName}
            rows={14}
            placeholder={`Leave blank to inherit the ${defaultPromptLabel.toLowerCase()}.`}
            value={draftValue}
            onChange={(event) => setDraftValue(event.target.value)}
          />
          <small>{field.description}</small>
        </label>
      ) : (
        <div className="admin-agent-prompt-preview">
          <div className="admin-agent-prompt-preview-label">Current prompt</div>
          <pre>{displayPrompt || `No ${defaultPromptLabel.toLowerCase()} is configured yet.`}</pre>
        </div>
      )}

      <details className="admin-agent-prompt-default">
        <summary>{defaultPromptLabel}</summary>
        <div>
          {trimmedDefault ? (
            <pre>{defaultPrompt}</pre>
          ) : (
            <p>No {defaultPromptLabel.toLowerCase()} is configured yet.</p>
          )}
        </div>
      </details>

      <div className="admin-agent-prompt-footer">
        {!usingDefault ? (
          <small>
            {hasOverride
              ? `This prompt differs from the ${defaultPromptLabel.toLowerCase()}.`
              : `This prompt matches the ${defaultPromptLabel.toLowerCase()}.`}
          </small>
        ) : null}
      </div>
    </article>
  )
}
