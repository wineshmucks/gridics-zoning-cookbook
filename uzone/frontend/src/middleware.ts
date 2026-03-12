import { clerkMiddleware } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'

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

export default clerkMiddleware(async (auth, req) => {
  const pathname = req.nextUrl.pathname
  const { orgId: orgIdFromPath, scopedPathname } = getScopedPathParts(pathname)
  const firstSegment = pathname.split('/').filter(Boolean)[0] || ''
  const isScopedRoute = isScopedPath(pathname)
  const isExcludedRoute = EXCLUDED_ROUTE_PREFIXES.includes(firstSegment)
  const isUnscopedCustomerRoute = UNSCOPED_ROUTE_PREFIXES.includes(firstSegment) || pathname === '/'
  const orgIdFromCookie = req.cookies.get(ORG_ID_COOKIE)?.value?.trim() || ''
  const effectiveOrgId = orgIdFromPath || orgIdFromCookie
  const requestHeaders = new Headers(req.headers)
  requestHeaders.set('x-uzone-host', req.headers.get('host') || '')
  requestHeaders.set('x-uzone-clientid', req.nextUrl.searchParams.get('clientid') || '')
  requestHeaders.set('x-uzone-orgid', effectiveOrgId)

  const authPath = isScopedRoute ? scopedPathname : pathname

  if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && isProtectedPath(authPath)) {
    await auth.protect()
  }

  if (!isExcludedRoute && isUnscopedCustomerRoute && !effectiveOrgId) {
    const redirectUrl = req.nextUrl.clone()
    redirectUrl.pathname = '/select-customer'
    redirectUrl.search = ''
    redirectUrl.searchParams.set('returnTo', `${req.nextUrl.pathname}${req.nextUrl.search}`)
    return NextResponse.redirect(redirectUrl)
  }

  if (!isExcludedRoute && isUnscopedCustomerRoute) {
    const redirectUrl = req.nextUrl.clone()
    redirectUrl.pathname = '/select-customer'
    redirectUrl.search = ''
    redirectUrl.searchParams.set('returnTo', `${req.nextUrl.pathname}${req.nextUrl.search}`)
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

  if (!isExcludedRoute && effectiveOrgId) {
    response.cookies.set(ORG_ID_COOKIE, effectiveOrgId, {
      path: '/',
      sameSite: 'lax',
    })
  }

  return response
})

export const config = {
  matcher: ['/((?!_next|.*\\..*).*)', '/'],
}
