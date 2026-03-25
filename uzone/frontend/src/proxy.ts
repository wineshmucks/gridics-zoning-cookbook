import { clerkMiddleware } from '@clerk/nextjs/server'
import { NextRequest, NextResponse } from 'next/server'

import {
  EXCLUDED_ROUTE_PREFIXES,
  INTERNAL_ORG_ROUTE_PREFIX,
  ORG_ID_COOKIE,
  SCOPE_PATH_COOKIE,
  UNSCOPED_ROUTE_PREFIXES,
} from './lib/org-constants'

function isProtectedPath(pathname: string) {
  return (
    pathname.startsWith('/staff') ||
    pathname.startsWith('/admin') ||
    pathname.startsWith('/super-admin') ||
    pathname.startsWith('/account')
  )
}

function normalizeScopePath(value: string | null | undefined) {
  if (!value) return ''
  const normalized = value.trim().replace(/\/+$/, '')
  return normalized && normalized.startsWith('/') ? normalized : normalized ? `/${normalized}` : ''
}

function getBackendBaseUrl() {
  const baseUrl =
    process.env.UZONE_API_BASE ||
    process.env.NEXT_PUBLIC_UZONE_API_BASE ||
    'http://backend:8000'
  return baseUrl.replace(/\/+$/, '')
}

async function resolveAliasPrefix(pathname: string): Promise<{ orgId: string; scopePath: string; scopedPathname: string } | null> {
  const parts = pathname.split('/').filter(Boolean)
  for (let index = parts.length; index >= 1; index -= 1) {
    const candidate = `/${parts.slice(0, index).join('/')}`
    try {
      const response = await fetch(
        `${getBackendBaseUrl()}/api/public/path-alias?path=${encodeURIComponent(candidate)}`,
        { cache: 'no-store' },
      )
      if (!response.ok) {
        continue
      }
      const payload = (await response.json()) as { orgid?: string | null; path_alias?: string | null }
      if (!payload.orgid || !payload.path_alias) {
        continue
      }
      const scopePath = normalizeScopePath(payload.path_alias)
      return {
        orgId: payload.orgid,
        scopePath,
        scopedPathname: pathname.slice(scopePath.length) || '/',
      }
    } catch {
      return null
    }
  }

  return null
}

async function runMiddlewareLogic(req: NextRequest, auth?: any) {
  const pathname = req.nextUrl.pathname
  const firstSegment = pathname.split('/').filter(Boolean)[0] || ''
  const isAiAssistantRoute = pathname === '/ai-assistant' || pathname.startsWith('/ai-assistant/')
  const isExcludedRoute = EXCLUDED_ROUTE_PREFIXES.includes(firstSegment)
  const isHomepage = pathname === '/'
  const isUnscopedCustomerRoute = UNSCOPED_ROUTE_PREFIXES.includes(firstSegment)
  const orgIdFromCookie = req.cookies.get(ORG_ID_COOKIE)?.value?.trim() || ''
  const scopePathFromCookie = normalizeScopePath(req.cookies.get(SCOPE_PATH_COOKIE)?.value || '')
  let effectiveOrgId = orgIdFromCookie
  let effectiveScopePath = scopePathFromCookie
  let scopedPathname = pathname
  let isScopedRoute = false

  if (isAiAssistantRoute) {
    const assistantScopePath = pathname === '/ai-assistant' ? '' : pathname.slice('/ai-assistant'.length)
    if (assistantScopePath.startsWith(`/${INTERNAL_ORG_ROUTE_PREFIX}/`)) {
      const parts = assistantScopePath.split('/').filter(Boolean)
      const orgId = parts[1] || ''
      if (orgId) {
        effectiveOrgId = orgId
        effectiveScopePath = normalizeScopePath(`/${INTERNAL_ORG_ROUTE_PREFIX}/${orgId}`)
      }
    } else if (assistantScopePath) {
      const aliasMatch = await resolveAliasPrefix(assistantScopePath)
      if (aliasMatch) {
        effectiveOrgId = aliasMatch.orgId
        effectiveScopePath = aliasMatch.scopePath
      }
    }
  } else if (pathname.startsWith(`/${INTERNAL_ORG_ROUTE_PREFIX}/`)) {
    const parts = pathname.split('/').filter(Boolean)
    const orgId = parts[1] || ''
    if (orgId) {
      effectiveOrgId = orgId
      effectiveScopePath = normalizeScopePath(`/${INTERNAL_ORG_ROUTE_PREFIX}/${orgId}`)
      scopedPathname = pathname.slice(effectiveScopePath.length) || '/'
      isScopedRoute = true
    }
  } else if (!isExcludedRoute && !isHomepage) {
    const aliasMatch = await resolveAliasPrefix(pathname)
    if (aliasMatch) {
      effectiveOrgId = aliasMatch.orgId
      effectiveScopePath = aliasMatch.scopePath
      scopedPathname = aliasMatch.scopedPathname
      isScopedRoute = true
    }
  }

  const requestHeaders = new Headers(req.headers)
  requestHeaders.set('x-uzone-host', req.headers.get('host') || '')
  requestHeaders.set('x-uzone-clientid', req.nextUrl.searchParams.get('clientid') || '')
  requestHeaders.set('x-uzone-orgid', effectiveOrgId)
  requestHeaders.set('x-uzone-scope-path', effectiveScopePath)
  requestHeaders.set('x-uzone-scoped-path', scopedPathname)

  const authPath = isScopedRoute ? scopedPathname : pathname

  if (auth && process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && isProtectedPath(authPath)) {
    await auth.protect()
  }

  if (!isExcludedRoute && isHomepage) {
    const redirectUrl = req.nextUrl.clone()
    redirectUrl.pathname = '/select-jurisdiction'
    redirectUrl.search = ''
    redirectUrl.searchParams.set('returnTo', '/')
    return NextResponse.redirect(redirectUrl)
  }

  if (!isExcludedRoute && isUnscopedCustomerRoute && !effectiveOrgId) {
    const redirectUrl = req.nextUrl.clone()
    redirectUrl.pathname = '/select-jurisdiction'
    redirectUrl.search = ''
    redirectUrl.searchParams.set('returnTo', `${req.nextUrl.pathname}${req.nextUrl.search}`)
    return NextResponse.redirect(redirectUrl)
  }

  if (!isExcludedRoute && isUnscopedCustomerRoute) {
    const redirectUrl = req.nextUrl.clone()
    const barePath = req.nextUrl.pathname.startsWith('/') ? req.nextUrl.pathname : `/${req.nextUrl.pathname}`
    const scopePrefix = effectiveScopePath || normalizeScopePath(`/${effectiveOrgId}`)
    redirectUrl.pathname = `${scopePrefix}${barePath === '/' ? '' : barePath}`
    return NextResponse.redirect(redirectUrl)
  }

  const rewriteUrl = req.nextUrl.clone()
  if (isScopedRoute) {
    rewriteUrl.pathname = scopedPathname
  }

  const response = NextResponse.rewrite(rewriteUrl, {
    request: {
      headers: requestHeaders,
    },
  })

  if (!isExcludedRoute && effectiveOrgId && !isHomepage) {
    response.cookies.set(ORG_ID_COOKIE, effectiveOrgId, {
      path: '/',
      sameSite: 'lax',
    })
    if (effectiveScopePath) {
      response.cookies.set(SCOPE_PATH_COOKIE, effectiveScopePath, {
        path: '/',
        sameSite: 'lax',
      })
    }
  }

  return response
}

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)

export default clerkEnabled 
  ? clerkMiddleware(async (auth, req) => runMiddlewareLogic(req, auth))
  : async (req: NextRequest) => runMiddlewareLogic(req)

export const config = {
  matcher: ['/((?!_next|.*\\..*).*)', '/'],
}
