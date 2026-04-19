'use client'

import { useActionState } from 'react'

import {
  runSuperAdminDatabaseCleanupAction,
  type DatabaseInfo,
  type SuperAdminDatabaseState,
} from '../app/admin/actions'

function formatSizeLabel(table: { size_label: string | null; size_bytes: number | null }) {
  if (table.size_label) {
    return table.size_label
  }
  if (table.size_bytes === null) {
    return 'Unavailable'
  }
  return `${table.size_bytes} B`
}

function countDanglingRows(databaseInfo: DatabaseInfo | null) {
  return databaseInfo?.dangling_tables.reduce((sum, item) => sum + item.dangling_rows, 0) ?? 0
}

function sortTablesAlpha<T extends { table_name: string }>(items: T[] | undefined | null): T[] {
  return [...(items || [])].sort((a, b) => a.table_name.localeCompare(b.table_name))
}

export function SuperAdminDatabaseClient({
  databaseInfo,
  loadError,
}: {
  databaseInfo: DatabaseInfo | null
  loadError: string | null
}) {
  const [state, formAction, isPending] = useActionState(
    runSuperAdminDatabaseCleanupAction,
    {
      error: null,
      success: null,
      databaseInfo,
      cleanupResult: null,
    } satisfies SuperAdminDatabaseState,
  )

  const resolvedInfo = state.databaseInfo || databaseInfo
  const sortedTables = sortTablesAlpha(resolvedInfo?.tables)
  const sortedDanglingTables = sortTablesAlpha(resolvedInfo?.dangling_tables)
  const sortedCleanupTables = sortTablesAlpha(state.cleanupResult?.deleted_by_table)
  const totalSizeLabel = resolvedInfo?.total_size_label || 'Unavailable'
  const totalDanglingRows = countDanglingRows(resolvedInfo)
  const danglingTableCount = sortedDanglingTables.length
  const tableCount = sortedTables.length
  const canClean = Boolean(totalDanglingRows > 0)

  return (
    <section className="card admin-stack super-admin-database-page" style={{ marginBottom: 18 }}>
      <div className="admin-header">
        <div className="super-admin-page-header-copy">
          <div className="eyebrow">Super Admin</div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Database Health
          </h1>
          <p className="admin-copy">
            Inspect database size, table footprint, and dangling jurisdiction records before you clean them up.
          </p>
        </div>
        <form action={formAction}>
          <button className="button secondary" type="submit" disabled={isPending || !canClean}>
            {isPending ? 'Cleaning…' : 'Clean Dangling Records'}
          </button>
        </form>
      </div>

      {loadError ? <div className="status-banner status-banner-error">{loadError}</div> : null}
      {state.error ? <div className="status-banner status-banner-error">{state.error}</div> : null}
      {state.success ? <div className="status-banner status-banner-success">{state.success}</div> : null}

      <div className="super-admin-metrics-row" aria-label="Database summary">
        <div className="super-admin-metric">
          <span>Total size</span>
          <strong>{totalSizeLabel}</strong>
        </div>
        <div className="super-admin-metric">
          <span>Tables</span>
          <strong>{tableCount}</strong>
        </div>
        <div className="super-admin-metric">
          <span>Dangling tables</span>
          <strong>{danglingTableCount}</strong>
        </div>
        <div className="super-admin-metric">
          <span>Dangling rows</span>
          <strong>{totalDanglingRows}</strong>
        </div>
      </div>

      <section className="super-admin-section-shell">
        <div className="super-admin-section-head">
          <div className="admin-list-heading super-admin-section-heading">Database tables</div>
          <div className="super-admin-section-meta">{tableCount} total</div>
        </div>
        {sortedTables.length ? (
          <table className="table super-admin-table">
            <thead>
              <tr>
                <th>Table</th>
                <th className="is-numeric">Rows</th>
                <th className="is-numeric">Size</th>
              </tr>
            </thead>
            <tbody>
              {sortedTables.map((table) => (
                <tr key={table.table_name}>
                  <td>{table.table_name}</td>
                  <td className="is-numeric">{table.row_count}</td>
                  <td className="is-numeric">{formatSizeLabel(table)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="super-admin-empty-inline">
            <strong>No table data available.</strong>
            <span>Unable to load the database summary.</span>
          </div>
        )}
      </section>

      <section className="super-admin-section-shell">
        <div className="super-admin-section-head">
          <div className="admin-list-heading super-admin-section-heading">Dangling jurisdiction records</div>
          <div className="super-admin-section-meta">{danglingTableCount} tables</div>
        </div>
        {sortedDanglingTables.length ? (
          <table className="table super-admin-table">
            <thead>
              <tr>
                <th>Table</th>
                <th className="is-numeric">Dangling rows</th>
                <th>Sample IDs</th>
              </tr>
            </thead>
            <tbody>
              {sortedDanglingTables.map((item) => (
                <tr key={item.table_name}>
                  <td>{item.table_name}</td>
                  <td className="is-numeric">{item.dangling_rows}</td>
                  <td>{item.sample_ids.length ? item.sample_ids.join(', ') : 'Unavailable'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="super-admin-empty-inline">
            <strong>No dangling records found.</strong>
            <span>All jurisdiction-linked rows currently have matching jurisdictions.</span>
          </div>
        )}
      </section>

      {state.cleanupResult ? (
        <section className="super-admin-section-shell">
          <div className="super-admin-section-head">
            <div className="admin-list-heading super-admin-section-heading">Last cleanup</div>
            <div className="super-admin-section-meta">{state.cleanupResult.deleted_rows_total} rows removed</div>
          </div>
          {sortedCleanupTables.length ? (
            <table className="table super-admin-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th className="is-numeric">Deleted rows</th>
                </tr>
              </thead>
              <tbody>
                {sortedCleanupTables.map((item) => (
                  <tr key={item.table_name}>
                    <td>{item.table_name}</td>
                    <td className="is-numeric">{item.deleted_rows}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="super-admin-empty-inline">
              <strong>No records were removed.</strong>
              <span>There was nothing to clean up.</span>
            </div>
          )}
        </section>
      ) : null}
    </section>
  )
}
