import type { TenantConfig } from '../../../lib/tenant'
import type { SurfaceHomepageConfig } from '../../public-homepage/surface-homepage-types'

export function buildLettersHomepageConfig(_tenant: TenantConfig): SurfaceHomepageConfig {
  return {
    rulesTitle: 'Jurisdiction Rules',
    rulesSubtitle: 'How this public surface should be used',
    howItWorksTitle: 'How It Works',
    howItWorksSubtitle: 'Get your zoning verification letter in 4 simple steps',
    howItWorksSteps: [
      ['1', 'Select Property', 'Use our interactive map to search and select your property by address or parcel number'],
      ['2', 'Create Account', 'Sign up or log in to your account to manage and track all your letter requests'],
      ['3', 'Submit & Pay', 'Complete the request form, review your order, and securely pay online with credit card'],
      ['4', 'Receive Letter', 'Track your request status and receive your official letter via email or mail'],
    ],
    featuresTitle: 'Why Choose Our Service?',
    featuresSubtitle: 'Modern, efficient, and transparent zoning verification process',
    featureCards: [
      [
        'F',
        'Fast Processing',
        'Standard letters delivered in under 3 business days, with 24-hour expedited option available',
      ],
      ['M', 'Interactive Map', 'Easy property selection with our integrated map system - search by address or parcel number'],
      ['E', 'Real-Time Tracking', 'Track your request status from submission to delivery with email notifications at each step'],
      ['S', 'Secure Payment', 'PCI DSS compliant payment processing with industry-standard encryption for your protection'],
      ['O', 'Order History', 'Access all your past requests and letters anytime through your personal account dashboard'],
      ['C', 'Official Documentation', 'All letters include official city seal, authorized signatures, and verified zoning data'],
    ],
    faqSubtitle: 'Find answers to common questions about zoning verification letters',
    ctaCopy: 'Request your zoning verification letter today',
    heroPrimarySectionLabel: 'Request Letter',
    heroSecondarySectionLabel: 'Ask the Zoning Assistant',
    footerCopy: 'Official zoning verification letter system for {city_name}.',
    footerQuickLinks: [
      { label: 'Request Letter', href: '/request/new', target: 'same' },
      { label: 'Property Search', href: '/request/new', target: 'same' },
      { label: 'Track Request', href: '/account/requests', target: 'same' },
      { label: 'FAQs', href: '/#faq-section', target: 'same' },
    ],
    footerResourceLinks: [
      { label: 'Services', href: '/#letter-types-section', target: 'same' },
      { label: 'Why Choose Us', href: '/#features-section', target: 'same' },
      { label: 'Payment Options', href: '/#faq-section', target: 'same' },
      { label: 'Contact Support', href: '/#cta-section', target: 'same' },
    ],
  }
}
