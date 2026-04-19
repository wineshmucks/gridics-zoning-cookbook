import Link from 'next/link'
import { SignUp } from '@clerk/nextjs'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sign Up',
  robots: {
    index: false,
    follow: false,
  },
}

export default function SignUpPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)

  if (!clerkEnabled) {
    return (
      <section className="auth-page">
        <div className="auth-page-shell">
          <div className="auth-page-copy">
            <p className="auth-page-kicker">Gridics AI Assistant</p>
            <h1 className="auth-page-title">Sign up is unavailable right now.</h1>
            <p>
              Authentication is not configured in this environment, so there is no sign-up flow to open.
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
          <h1 className="auth-page-title">Create your account.</h1>
          <p>
            Join the assistant to get jurisdiction-specific tools, intake workflows, and account access.
          </p>
          <div className="auth-page-note">Already have an account? Use the sign-in link in the form.</div>
        </div>
        <div className="card auth-page-card">
          <SignUp
            routing="path"
            path="/sign-up"
            signInUrl="/sign-in"
            fallbackRedirectUrl="/"
            signInFallbackRedirectUrl="/"
          />
        </div>
      </div>
    </section>
  )
}
