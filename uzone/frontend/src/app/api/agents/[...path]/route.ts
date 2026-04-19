import { NextRequest } from 'next/server'

import { proxyBackendRequest } from '../../_proxy'

export const dynamic = 'force-dynamic'

function getProxyPath(params: { path?: string[] }) {
  const segments = Array.isArray(params.path) ? params.path : []
  return `/api/agents/${segments.join('/')}`
}

async function proxy(req: NextRequest, context: { params: { path?: string[] } }) {
  return proxyBackendRequest(req, getProxyPath(context.params))
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE, proxy as HEAD, proxy as OPTIONS }
