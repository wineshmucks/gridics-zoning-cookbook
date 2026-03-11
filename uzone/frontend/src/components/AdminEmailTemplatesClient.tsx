'use client'

import { useEffect, useMemo, useState, useTransition } from 'react'

import type { AdminEmailTemplate, AdminEmailTemplatesPayload } from '../app/admin/actions'
import {
  fetchAdminEmailTemplatesAction,
  resetAdminEmailTemplateOverrideAction,
  saveAdminEmailTemplateOverrideAction,
} from '../app/admin/actions'

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value))
}

function statusTone(status: AdminEmailTemplate['status']) {
  if (status === 'active') {
    return 'is-active'
  }
  if (status === 'draft') {
    return 'is-draft'
  }
  return 'is-inactive'
}

type FormState = {
  name: string
  description: string
  category: string
  status: AdminEmailTemplate['status']
  subject_template: string
  body_template: string
}

function toFormState(template: AdminEmailTemplate): FormState {
  return {
    name: template.name,
    description: template.description || '',
    category: template.category,
    status: template.status,
    subject_template: template.subject_template,
    body_template: template.body_template,
  }
}

export function AdminEmailTemplatesClient({
  initialPayload,
}: {
  initialPayload: AdminEmailTemplatesPayload
}) {
  const fallbackTemplate: AdminEmailTemplate | null = initialPayload.templates[0] || null
  const [payload, setPayload] = useState(initialPayload)
  const [selectedCode, setSelectedCode] = useState(fallbackTemplate?.code || '')
  const [query, setQuery] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  const filteredTemplates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) {
      return payload.templates
    }

    return payload.templates.filter((template) => {
      return (
        template.name.toLowerCase().includes(normalizedQuery) ||
        template.code.toLowerCase().includes(normalizedQuery) ||
        template.trigger_state.toLowerCase().includes(normalizedQuery) ||
        (template.description || '').toLowerCase().includes(normalizedQuery)
      )
    })
  }, [payload.templates, query])

  const selectedTemplate =
    payload.templates.find((template) => template.code === selectedCode) || filteredTemplates[0] || null

  const [formState, setFormState] = useState<FormState>(
    selectedTemplate
      ? toFormState(selectedTemplate)
      : fallbackTemplate
        ? toFormState(fallbackTemplate)
        : {
            name: '',
            description: '',
            category: 'request_updates',
            status: 'draft',
            subject_template: '',
            body_template: '',
          },
  )

  useEffect(() => {
    if (selectedTemplate) {
      setFormState(toFormState(selectedTemplate))
    }
  }, [selectedTemplate])

  async function refreshTemplates(successMessage?: string) {
    const nextPayload = await fetchAdminEmailTemplatesAction()
    setPayload(nextPayload)
    setSelectedCode((currentCode) => {
      if (nextPayload.templates.some((template) => template.code === currentCode)) {
        return currentCode
      }
      return nextPayload.templates[0]?.code || ''
    })
    setMessage(successMessage || null)
  }

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setFormState((current) => ({ ...current, [field]: value }))
  }

  if (!selectedTemplate) {
    return (
      <section className="card admin-section-detail">
        <div className="admin-header">
          <div>
            <div className="eyebrow">Admin</div>
            <h1 className="section-title" style={{ marginBottom: 8 }}>
              Email Templates
            </h1>
            <p className="admin-copy">No email templates are available for the current customer.</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="admin-sections">
      <div className="card admin-section-detail email-admin-hero">
        <div className="admin-header">
          <div>
            <div className="eyebrow">Admin</div>
            <h1 className="section-title" style={{ marginBottom: 8 }}>
              Email Templates
            </h1>
            <p className="admin-copy">
              Manage request-state notifications for {payload.client.city_name}. Gridics provides the
              default setup, and customer-specific overrides replace that default only when saved.
            </p>
          </div>
          <div className="email-admin-summary">
            <div className="email-admin-summary-label">Customer</div>
            <div className="email-admin-summary-value">{payload.client.city_name}</div>
            <div className="email-admin-summary-meta">{payload.client.client_id}</div>
          </div>
        </div>

        {message ? <div className="success-banner">{message}</div> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <div className="email-admin-toolbar">
          <label className="field">
            Search templates
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by state or template name"
            />
          </label>
          <div className="email-admin-toolbar-note">
            <span className="pill">Defaults owned by Gridics</span>
            <span className="pill">{payload.templates.filter((item) => item.is_override).length} overrides</span>
          </div>
        </div>
      </div>

      <div className="email-admin-layout">
        <div className="card email-admin-list">
          {filteredTemplates.map((template) => (
            <button
              key={template.code}
              type="button"
              className={`email-template-list-item ${template.code === selectedTemplate.code ? 'is-selected' : ''}`}
              onClick={() => {
                setSelectedCode(template.code)
                setMessage(null)
                setError(null)
              }}
            >
              <div className="email-template-list-item-top">
                <div>
                  <div className="email-template-list-item-title">{template.name}</div>
                  <div className="email-template-list-item-state">{template.trigger_state}</div>
                </div>
                <span className={`status-pill ${statusTone(template.status)}`}>{template.status}</span>
              </div>
              <p className="email-template-list-item-copy">{template.description || 'No description provided.'}</p>
              <div className="email-template-list-item-meta">
                <span className={`source-pill ${template.is_override ? 'is-override' : ''}`}>
                  {template.is_override ? 'Customer override' : 'Gridics default'}
                </span>
                <span>Updated {formatTimestamp(template.updated_at)}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="email-admin-editor-stack">
          <div className="card email-admin-editor">
            <div className="stack-header">
              <div>
                <h2 className="admin-section-title">{selectedTemplate.name}</h2>
                <p className="admin-copy">
                  State trigger: <strong>{selectedTemplate.trigger_state}</strong>
                </p>
              </div>
              <div className="email-admin-source">
                <span className={`source-pill ${selectedTemplate.is_override ? 'is-override' : ''}`}>
                  {selectedTemplate.is_override ? 'Customer override' : 'Gridics default'}
                </span>
              </div>
            </div>

            <div className="email-admin-form-grid">
              <label className="field">
                Template name
                <input
                  value={formState.name}
                  onChange={(event) => updateField('name', event.target.value)}
                />
              </label>
              <label className="field">
                Status
                <select
                  value={formState.status}
                  onChange={(event) =>
                    updateField('status', event.target.value as AdminEmailTemplate['status'])
                  }
                >
                  <option value="active">Active</option>
                  <option value="draft">Draft</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
              <label className="field full-span">
                Description
                <input
                  value={formState.description}
                  onChange={(event) => updateField('description', event.target.value)}
                />
              </label>
              <label className="field full-span">
                Subject
                <input
                  value={formState.subject_template}
                  onChange={(event) => updateField('subject_template', event.target.value)}
                />
              </label>
              <label className="field full-span">
                Email body
                <textarea
                  rows={12}
                  value={formState.body_template}
                  onChange={(event) => updateField('body_template', event.target.value)}
                />
              </label>
            </div>

            <div className="button-row">
              <button
                type="button"
                className="button"
                disabled={isPending}
                onClick={() => {
                  setError(null)
                  setMessage(null)
                  startTransition(async () => {
                    try {
                      const result = await saveAdminEmailTemplateOverrideAction({
                        code: selectedTemplate.code,
                        name: formState.name.trim(),
                        description: formState.description.trim(),
                        category: formState.category,
                        subject_template: formState.subject_template.trim(),
                        body_template: formState.body_template.trim(),
                        status: formState.status,
                      })
                      await refreshTemplates(result.success)
                    } catch (nextError) {
                      setError(nextError instanceof Error ? nextError.message : 'Unable to save template.')
                    }
                  })
                }}
              >
                {isPending ? 'Saving...' : 'Save Override'}
              </button>
              <button
                type="button"
                className="button secondary"
                disabled={isPending || !selectedTemplate.is_override}
                onClick={() => {
                  setError(null)
                  setMessage(null)
                  startTransition(async () => {
                    try {
                      const result = await resetAdminEmailTemplateOverrideAction(selectedTemplate.code)
                      await refreshTemplates(result.success)
                    } catch (nextError) {
                      setError(
                        nextError instanceof Error ? nextError.message : 'Unable to reset template override.',
                      )
                    }
                  })
                }}
              >
                Reset to Gridics Default
              </button>
            </div>
          </div>

          <div className="card email-admin-preview">
            <div className="stack-header">
              <div>
                <h2 className="admin-section-title">Preview</h2>
                <p className="admin-copy">
                  Variables such as <code>{'{{request_id}}'}</code> remain editable merge tokens.
                </p>
              </div>
              <span className={`status-pill ${statusTone(formState.status)}`}>{formState.status}</span>
            </div>
            <div className="email-preview-shell">
              <div className="email-preview-subject">Subject: {formState.subject_template}</div>
              <div
                className="email-preview-body"
                dangerouslySetInnerHTML={{ __html: formState.body_template }}
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
