import Link from 'next/link'

export default function NotFound() {
  return (
    <section className="jurisdiction-picker-page">
      <div className="jurisdiction-picker-shell">
        <section className="card jurisdiction-picker-empty jurisdiction-picker-empty-state">
          <h1 className="section-title">Page not found</h1>
          <p style={{ color: 'var(--muted)', margin: 0 }}>
            The page you requested could not be found.
          </p>
          <div style={{ marginTop: '1rem' }}>
            <Link className="button jurisdiction-picker-button-primary" href="/select-jurisdiction">
              Select a jurisdiction
            </Link>
          </div>
        </section>
      </div>
    </section>
  )
}
