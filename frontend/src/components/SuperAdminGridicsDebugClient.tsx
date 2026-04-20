'use client'

import { useActionState } from 'react'

import {
  runSuperAdminGridicsDebugAction,
  type SuperAdminGridicsDebugState,
} from '../app/admin/actions'

const initialState: SuperAdminGridicsDebugState = {
  error: null,
  success: null,
  request: null,
  response: null,
}

export function SuperAdminGridicsDebugClient() {
  const [state, formAction, isPending] = useActionState(
    runSuperAdminGridicsDebugAction,
    initialState,
  )

  return (
    <section className="card admin-stack" style={{ marginBottom: 18 }}>
      <div className="admin-header">
        <div>
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Gridics Debug
          </h1>
          <p className="admin-copy">
            Enter a full property address and inspect the raw Gridics property-record response as
            formatted JSON.
          </p>
        </div>
      </div>

      <form action={formAction} className="admin-form" style={{ maxWidth: 760 }}>
        <div className="admin-list-heading">Property lookup</div>
        <label className="field">
          <span>Full address</span>
          <textarea
            name="address"
            required
            rows={3}
            placeholder="444 Brickell Ave, Miami, FL 33131"
            defaultValue={state.request?.inputAddress || ''}
          />
        </label>
        <div style={{ color: 'var(--muted)' }}>
          Include street, city, two-letter state abbreviation, and 5-digit ZIP code.
        </div>
        <button className="button" type="submit" disabled={isPending}>
          {isPending ? 'Loading…' : 'Fetch Gridics Response'}
        </button>
        {state.error ? <div className="status-banner status-banner-error">{state.error}</div> : null}
        {state.success ? (
          <div className="status-banner status-banner-success">{state.success}</div>
        ) : null}
      </form>

      {state.request ? (
        <div className="admin-list">
          <div className="admin-list-heading">Resolved request</div>
          <dl className="detail-list">
            <div>
              <dt>Input</dt>
              <dd>{state.request.inputAddress}</dd>
            </div>
            <div>
              <dt>Gridics address</dt>
              <dd>{state.request.normalizedAddress || 'Unavailable'}</dd>
            </div>
            <div>
              <dt>State env</dt>
              <dd>{state.request.stateEnv || 'Unavailable'}</dd>
            </div>
            <div>
              <dt>ZIP code</dt>
              <dd>{state.request.zipCode || 'Unavailable'}</dd>
            </div>
          </dl>
        </div>
      ) : null}

      {state.response !== null ? (
        <div className="admin-list">
          <div className="admin-list-heading">Gridics JSON</div>
          <pre
            style={{
              margin: 0,
              padding: 16,
              overflowX: 'auto',
              borderRadius: 16,
              background: 'rgba(15, 23, 42, 0.96)',
              color: '#dbeafe',
              fontSize: 13,
              lineHeight: 1.5,
            }}
          >
            {JSON.stringify(state.response, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  )
}
