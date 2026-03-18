import { clerkMiddleware } from '@clerk/nextjs/server'
import { NextRequest, NextResponse } from 'next/server'

import { EXCLUDED_ROUTE_PREFIXES, ORG_ID_COOKIE, UNSCOPED_ROUTE_PREFIXES } from './lib/org-constants'
import { getScopedPathParts, isScopedPath } from './lib/org-url'

function isProtectedPath(pathname: string) {
  return (
    pathname.startsWith('/staff') ||
    pathname.startsWith('/admin') ||
    pathname.startsWith('/super-admin') ||
    pathname.startsWith('/account')
  )
}

async function runMiddlewareLogic(req: NextRequest, auth?: any) {
  const pathname = req.nextUrl.pathname
  const { orgId: orgIdFromPath, scopedPathname } = getScopedPathParts(pathname)
  const firstSegment = pathname.split('/').filter(Boolean)[0] || ''
  const isScopedRoute = isScopedPath(pathname)
  const isExcludedRoute = EXCLUDED_ROUTE_PREFIXES.includes(firstSegment)
  const isHomepage = pathname === '/'
  const isUnscopedCustomerRoute = UNSCOPED_ROUTE_PREFIXES.includes(firstSegment)
  const orgIdFromCookie = req.cookies.get(ORG_ID_COOKIE)?.value?.trim() || ''
  const effectiveOrgId = orgIdFromPath || orgIdFromCookie
  const requestHeaders = new Headers(req.headers)
  requestHeaders.set('x-uzone-host', req.headers.get('host') || '')
  requestHeaders.set('x-uzone-clientid', req.nextUrl.searchParams.get('clientid') || '')
  requestHeaders.set('x-uzone-orgid', effectiveOrgId)

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
    redirectUrl.pathname = `/${effectiveOrgId}${barePath === '/' ? '' : barePath}`
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
