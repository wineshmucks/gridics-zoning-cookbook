import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'
import { NextResponse } from 'next/server'

const isProtectedRoute = createRouteMatcher([
  '/staff(.*)',
  '/admin(.*)',
  '/super-admin(.*)',
  '/account(.*)',
])

export default clerkMiddleware(async (auth, req) => {
  const requestHeaders = new Headers(req.headers)
  requestHeaders.set('x-uzone-host', req.headers.get('host') || '')
  requestHeaders.set('x-uzone-clientid', req.nextUrl.searchParams.get('clientid') || '')

  if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && isProtectedRoute(req)) {
    await auth.protect()
  }

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  })
})

export const config = {
  matcher: ['/((?!_next|.*\\..*).*)', '/'],
}
