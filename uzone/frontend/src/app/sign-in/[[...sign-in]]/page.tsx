import Link from 'next/link'
import { SignIn } from '@clerk/nextjs'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sign In',
  robots: {
    index: false,
    follow: false,
  },
}

export default function SignInPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)

  if (!clerkEnabled) {
    return (
      <section className="auth-page">
        <div className="auth-page-shell">
          <div className="auth-page-copy">
            <p className="auth-page-kicker">Gridics AI Assistant</p>
            <h1 className="auth-page-title">Sign in is unavailable right now.</h1>
            <p>
              Authentication is not configured in this environment, so there is no sign-in flow to open.
            </p>
            <Link className="button button-signin" href="/">
              <span className="button-signin-icon">•</span>
              Return home
            </Link>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="auth-page">
      <div className="auth-page-shell">
        <div className="auth-page-copy">
          <p className="auth-page-kicker">Gridics AI Assistant</p>
          <h1 className="auth-page-title">Sign in to continue.</h1>
          <p>
            Use your Gridics account to access the assistant, manage jurisdictions, and review requests.
          </p>
          <div className="auth-page-note">Need a new account? Use the sign-up link in the form.</div>
        </div>
        <div className="card auth-page-card">
          <SignIn
            routing="path"
            path="/sign-in"
            signUpUrl="/sign-up"
            fallbackRedirectUrl="/"
            signUpFallbackRedirectUrl="/"
          />
        </div>
      </div>
    </section>
  )
}
