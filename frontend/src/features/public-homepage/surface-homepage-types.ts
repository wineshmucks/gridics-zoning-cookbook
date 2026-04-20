export type SurfaceHomepageStep = [string, string, string]

export type SurfaceHomepageFeatureCard = [string, string, string]

export type SurfaceHomepageLink = {
  label: string
  href: string
  target?: 'same' | 'assistant' | 'letters'
}

export type SurfaceHomepageConfig = {
  rulesTitle: string
  rulesSubtitle: string
  howItWorksTitle: string
  howItWorksSubtitle: string
  howItWorksSteps: SurfaceHomepageStep[]
  featuresTitle: string
  featuresSubtitle: string
  featureCards: SurfaceHomepageFeatureCard[]
  faqSubtitle: string
  ctaCopy: string
  heroPrimarySectionLabel: string
  heroSecondarySectionLabel: string
  footerCopy: string
  footerQuickLinks: SurfaceHomepageLink[]
  footerResourceLinks: SurfaceHomepageLink[]
}
