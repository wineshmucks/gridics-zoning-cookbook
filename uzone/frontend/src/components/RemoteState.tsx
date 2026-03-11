'use client'

export function LoadingCard({ title }: { title: string }) {
  return (
    <section className="card">
      <h1 className="section-title">{title}</h1>
      <div style={{ color: 'var(--muted)' }}>Loading...</div>
    </section>
  )
}

export function ErrorCard({ title, message }: { title: string; message: string }) {
  return (
    <section className="card">
      <h1 className="section-title">{title}</h1>
      <div style={{ color: '#9b3d2f' }}>{message}</div>
    </section>
  )
}

