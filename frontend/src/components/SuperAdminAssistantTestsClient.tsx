'use client'

import { useState } from 'react'

import type { CustomerRecord } from '../app/admin/actions'
import { buildApiUrl } from '../lib/api'
import { CompactSummaryHeader, FormSection } from './AdminSurfacePrimitives'

type AssistantTestCase = {
  id: string
  name: string
  question: string
  propertySelected: boolean
  propertyAddress: string
  propertyLat: string
  propertyLng: string
}

type AssistantTestRunResult = {
  payload: string
  session_state: Record<string, unknown>
  dependencies: Record<string, unknown>
  metadata: Record<string, unknown>
  content: string | null
  run_id: string | null
  session_id: string | null
  duration_ms: number
  raw_response: unknown
}

type AssistantTestStatus = {
  state: 'idle' | 'running' | 'passed' | 'failed'
  error: string | null
  result: AssistantTestRunResult | null
}

const starterCases: AssistantTestCase[] = [
  {
    id: 'case-general-setbacks',
    name: 'General setback question',
    question: 'What setback rules should I review before designing an addition?',
    propertySelected: false,
    propertyAddress: '',
    propertyLat: '',
    propertyLng: '',
  },
  {
    id: 'case-selected-property',
    name: 'Selected property setbacks',
    question: 'Tell me about setbacks for this property.',
    propertySelected: true,
    propertyAddress: '3148 Mary St #1, Miami, FL 33133',
    propertyLat: '25.732787',
    propertyLng: '-80.239989',
  },
]

function newCaseId() {
  return `case-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback
}

function buildInitialStatuses(cases: AssistantTestCase[]): Record<string, AssistantTestStatus> {
  return Object.fromEntries(
    cases.map((testCase) => [
      testCase.id,
      {
        state: 'idle',
        error: null,
        result: null,
      } satisfies AssistantTestStatus,
    ]),
  )
}

function parseCoordinate(value: string): number | null {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function SuperAdminAssistantTestsClient({ customer }: { customer: CustomerRecord }) {
  const [cases, setCases] = useState<AssistantTestCase[]>(starterCases)
  const [prependPropertyNote, setPrependPropertyNote] = useState(true)
  const [statuses, setStatuses] = useState<Record<string, AssistantTestStatus>>(() =>
    buildInitialStatuses(starterCases),
  )
  const organizationId = customer.clerk_organization_id || customer.id

  const updateCase = (id: string, patch: Partial<AssistantTestCase>) => {
    setCases((current) =>
      current.map((testCase) => (testCase.id === id ? { ...testCase, ...patch } : testCase)),
    )
  }

  const addCase = () => {
    const nextCase: AssistantTestCase = {
      id: newCaseId(),
      name: 'New assistant test',
      question: '',
      propertySelected: false,
      propertyAddress: '',
      propertyLat: '',
      propertyLng: '',
    }
    setCases((current) => [...current, nextCase])
    setStatuses((current) => ({
      ...current,
      [nextCase.id]: { state: 'idle', error: null, result: null },
    }))
  }

  const removeCase = (id: string) => {
    setCases((current) => current.filter((testCase) => testCase.id !== id))
    setStatuses((current) => {
      const next = { ...current }
      delete next[id]
      return next
    })
  }

  const runCase = async (testCase: AssistantTestCase) => {
    const question = testCase.question.trim()
    if (!question) {
      setStatuses((current) => ({
        ...current,
        [testCase.id]: {
          state: 'failed',
          error: 'Enter a question before running this test.',
          result: null,
        },
      }))
      return
    }

    const latitude = parseCoordinate(testCase.propertyLat)
    const longitude = parseCoordinate(testCase.propertyLng)
    if (testCase.propertySelected && (!testCase.propertyAddress.trim() || latitude === null || longitude === null)) {
      setStatuses((current) => ({
        ...current,
        [testCase.id]: {
          state: 'failed',
          error: 'Selected-property tests need address, latitude, and longitude.',
          result: null,
        },
      }))
      return
    }

    setStatuses((current) => ({
      ...current,
      [testCase.id]: { state: 'running', error: null, result: current[testCase.id]?.result || null },
    }))

    try {
      const response = await fetch(buildApiUrl('/api/admin/assistant-tests/run'), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({
          question,
          client_id: customer.client_id,
          organization_id: organizationId,
          property_context:
            testCase.propertySelected && latitude !== null && longitude !== null
              ? {
                  address: testCase.propertyAddress.trim(),
                  latitude,
                  longitude,
                }
              : null,
          prepend_property_note: prependPropertyNote,
        }),
      })

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null)
        throw new Error(
          typeof errorPayload?.detail === 'string'
            ? errorPayload.detail
            : 'Unable to run assistant test.',
        )
      }

      const result = (await response.json()) as AssistantTestRunResult
      setStatuses((current) => ({
        ...current,
        [testCase.id]: { state: 'passed', error: null, result },
      }))
    } catch (error) {
      setStatuses((current) => ({
        ...current,
        [testCase.id]: {
          state: 'failed',
          error: getErrorMessage(error, 'Unable to run assistant test.'),
          result: null,
        },
      }))
    }
  }

  const runAll = async () => {
    for (const testCase of cases) {
      await runCase(testCase)
    }
  }

  return (
    <div className="panel-stack super-admin-panel-stack">
      <section className="super-admin-summary-card">
        <CompactSummaryHeader title="Assistant Tests" icon="assistant-setup" />
      </section>

      <section className="super-admin-content-panel">
        <FormSection title="Runner" icon="assistant-setup">
          <div className="admin-form admin-form-compact">
            <div className="admin-form-note">
              Define test prompts, optionally include selected-property context, and run them against the
              customer zoning team with explicit session state.
            </div>
            <div className="admin-form-grid">
              <label className="field">
                <span>Jurisdiction context</span>
                <input value={`${customer.city_name} (${customer.client_id})`} readOnly />
                <small>
                  Sends client_id={customer.client_id}
                  {customer.jurisdiction_id ? ` and jurisdiction_id=${customer.jurisdiction_id}` : ''}.
                </small>
              </label>
              <label className="field">
                <span>Property note</span>
                <select
                  value={prependPropertyNote ? 'yes' : 'no'}
                  onChange={(event) => setPrependPropertyNote(event.target.value === 'yes')}
                >
                  <option value="yes">Prepend selected-property system note</option>
                  <option value="no">Session state only</option>
                </select>
                <small>The backend always passes active_property_context when property context is enabled.</small>
              </label>
            </div>
            <div className="admin-form-actions">
              <button className="button button-fit" type="button" onClick={addCase}>
                Add test case
              </button>
              <button className="button secondary button-fit" type="button" onClick={() => void runAll()}>
                Run all tests
              </button>
            </div>
          </div>
        </FormSection>

        <div className="admin-stack">
          {cases.map((testCase, index) => {
            const status = statuses[testCase.id] || { state: 'idle', error: null, result: null }
            return (
              <section key={testCase.id} className="admin-list">
                <div className="admin-list-heading">Test {index + 1}</div>
                <div className="admin-form admin-form-compact">
                  <div className="admin-form-grid">
                    <label className="field">
                      <span>Name</span>
                      <input
                        value={testCase.name}
                        onChange={(event) => updateCase(testCase.id, { name: event.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span>Property state</span>
                      <select
                        value={testCase.propertySelected ? 'selected' : 'none'}
                        onChange={(event) =>
                          updateCase(testCase.id, { propertySelected: event.target.value === 'selected' })
                        }
                      >
                        <option value="none">No selected property</option>
                        <option value="selected">Selected property</option>
                      </select>
                    </label>
                  </div>

                  <label className="field field-full">
                    <span>User question</span>
                    <textarea
                      rows={3}
                      value={testCase.question}
                      onChange={(event) => updateCase(testCase.id, { question: event.target.value })}
                      placeholder="What can I build on this property?"
                    />
                  </label>

                  {testCase.propertySelected ? (
                    <div className="admin-form-grid">
                      <label className="field">
                        <span>Property address</span>
                        <input
                          value={testCase.propertyAddress}
                          onChange={(event) => updateCase(testCase.id, { propertyAddress: event.target.value })}
                          placeholder="3148 Mary St #1, Miami, FL 33133"
                        />
                      </label>
                      <label className="field">
                        <span>Latitude</span>
                        <input
                          value={testCase.propertyLat}
                          onChange={(event) => updateCase(testCase.id, { propertyLat: event.target.value })}
                          placeholder="25.732787"
                        />
                      </label>
                      <label className="field">
                        <span>Longitude</span>
                        <input
                          value={testCase.propertyLng}
                          onChange={(event) => updateCase(testCase.id, { propertyLng: event.target.value })}
                          placeholder="-80.239989"
                        />
                      </label>
                    </div>
                  ) : null}

                  <div className="admin-form-actions">
                    <button
                      className="button button-fit"
                      type="button"
                      disabled={status.state === 'running'}
                      onClick={() => void runCase(testCase)}
                    >
                      {status.state === 'running' ? 'Running…' : 'Run test'}
                    </button>
                    <button
                      className="button secondary button-fit"
                      type="button"
                      disabled={cases.length === 1}
                      onClick={() => removeCase(testCase.id)}
                    >
                      Remove
                    </button>
                  </div>

                  {status.error ? <div className="status-banner status-banner-error">{status.error}</div> : null}
                  {status.state === 'passed' ? (
                    <div className="status-banner status-banner-success">
                      Completed in {status.result?.duration_ms ?? 0} ms.
                    </div>
                  ) : null}

                  {status.result ? (
                    <div className="admin-stack">
                      <div className="admin-list">
                        <div className="admin-list-heading">Assistant response</div>
                        <div className="admin-form-note" style={{ whiteSpace: 'pre-wrap' }}>
                          {status.result.content || 'No response content returned.'}
                        </div>
                      </div>
                      <div className="admin-list">
                        <div className="admin-list-heading">Run payload and state</div>
                        <pre className="assistant-test-json">
                          {JSON.stringify(
                            {
                              payload: status.result.payload,
                              session_state: status.result.session_state,
                              dependencies: status.result.dependencies,
                              metadata: status.result.metadata,
                              run_id: status.result.run_id,
                              session_id: status.result.session_id,
                            },
                            null,
                            2,
                          )}
                        </pre>
                      </div>
                    </div>
                  ) : null}
                </div>
              </section>
            )
          })}
        </div>
      </section>
    </div>
  )
}
