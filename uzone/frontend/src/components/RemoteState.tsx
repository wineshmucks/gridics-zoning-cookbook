'use client'

export function LoadingCard({ title }: { title: string }) {
  return (
    <section className="card page-stack">
      <div className="page-intro">
        <div className="eyebrow">Working</div>
        <h1 className="section-title">{title}</h1>
      </div>
      <div style={{ color: 'var(--muted)' }}>Loading...</div>
    </section>
  )
}

export function ErrorCard({ title, message }: { title: string; message: string }) {
  return (
    <section className="card page-stack">
      <div className="page-intro">
        <div className="eyebrow">Needs attention</div>
        <h1 className="section-title">{title}</h1>
      </div>
      <div className="status-banner status-banner-error">{message}</div>
    </section>
  )
}
