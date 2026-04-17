import { NextRequest, NextResponse } from 'next/server'

type ClientErrorPayload = {
  message?: string
  stack?: string
  source?: string
  location?: string
  userAgent?: string
  kind?: 'error' | 'unhandledrejection'
}

export async function POST(req: NextRequest) {
  let payload: ClientErrorPayload | null = null

  try {
    payload = (await req.json()) as ClientErrorPayload
  } catch {
    payload = null
  }

  console.error('[client-error]', {
    kind: payload?.kind || 'error',
    message: payload?.message || 'unknown',
    source: payload?.source || null,
    location: payload?.location || null,
    userAgent: payload?.userAgent || null,
    stack: payload?.stack || null,
  })

  return NextResponse.json({ ok: true })
}
