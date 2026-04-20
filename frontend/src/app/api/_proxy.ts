import { NextRequest, NextResponse } from 'next/server'

import { buildServerBackendApiUrl } from '../../lib/backend'

const HOP_BY_HOP_HEADERS = [
  'connection',
  'content-length',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]

function cloneForwardHeaders(req: NextRequest): Headers {
  const headers = new Headers(req.headers)
  for (const headerName of HOP_BY_HOP_HEADERS) {
    headers.delete(headerName)
  }
  headers.delete('host')
  return headers
}

function cloneResponseHeaders(response: Response): Headers {
  const headers = new Headers(response.headers)
  for (const headerName of HOP_BY_HOP_HEADERS) {
    headers.delete(headerName)
  }
  return headers
}

export async function proxyBackendRequest(req: NextRequest, backendPath: string): Promise<Response> {
  const targetUrl = new URL(await buildServerBackendApiUrl(backendPath))
  targetUrl.search = req.nextUrl.search

  const init: RequestInit = {
    method: req.method,
    headers: cloneForwardHeaders(req),
    redirect: 'manual',
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body = await req.arrayBuffer()
  }

  try {
    const backendResponse = await fetch(targetUrl, init)
    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: cloneResponseHeaders(backendResponse),
    })
  } catch (error) {
    return NextResponse.json(
      {
        detail: error instanceof Error ? error.message : 'Unable to reach backend service.',
      },
      { status: 502 },
    )
  }
}
