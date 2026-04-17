import type { TenantConfig } from '../../../lib/tenant'
import type { SurfaceHomepageConfig } from '../../public-homepage/surface-homepage-types'

export function buildAssistantHomepageConfig(_tenant: TenantConfig): SurfaceHomepageConfig {
  return {
    rulesTitle: 'Assistant Rules',
    rulesSubtitle: 'How the assistant should behave on this host',
    howItWorksTitle: 'How the Assistant Works',
    howItWorksSubtitle:
      'Use the assistant to scope the question, review the market, and move to the right workflow',
    howItWorksSteps: [
      ['1', 'Ask a Question', 'Start with the property, project, or zoning question you need answered'],
      [
        '2',
        'Scope the Market',
        'The assistant uses the jurisdiction’s market to determine whether the question applies',
      ],
      ['3', 'Review the Answer', 'Read the cited response and any caveats before taking action'],
      ['4', 'Follow Up', 'If needed, continue with staff review or move into the letters workflow'],
    ],
    featuresTitle: 'Why Use the Assistant?',
    featuresSubtitle: 'Fast, market-aware answers for staff and public users',
    featureCards: [
      ['M', 'Market-Aware', 'Responses are scoped to the jurisdiction’s configured market before answering'],
      ['C', 'Cited Answers', 'The assistant should provide source-backed responses whenever possible'],
      ['S', 'Surface Routing', 'Different hosts can expose different rules and home pages for each product'],
      ['H', 'Human Handoff', 'Use the assistant to collect context before passing to staff review'],
      ['Q', 'Question Triage', 'Separate assistant-friendly questions from letter requests early'],
      ['R', 'Runtime Rules', 'Configure per-surface homepage content and usage rules per jurisdiction'],
    ],
    faqSubtitle: 'Find answers about assistant behavior, markets, and jurisdiction scope',
    ctaCopy: 'Open the assistant and start asking market-aware zoning questions',
    heroPrimarySectionLabel: 'Open Assistant',
    heroSecondarySectionLabel: 'Request a Letter',
    footerCopy: 'Assistant-first zoning guidance for {city_name}.',
    footerQuickLinks: [
      { label: 'Open Assistant', href: '/assistant', target: 'assistant' },
      { label: 'Request Letter', href: '/request/new', target: 'letters' },
      { label: 'Choose Jurisdiction', href: '/select-jurisdiction', target: 'same' },
      { label: 'FAQs', href: '/#faq-section', target: 'same' },
    ],
    footerResourceLinks: [
      { label: 'Assistant Rules', href: '/#features-section', target: 'same' },
      { label: 'Markets', href: '/#info-section', target: 'same' },
      { label: 'Usage Guide', href: '/#how-it-works-section', target: 'same' },
      { label: 'Contact Support', href: '/#cta-section', target: 'same' },
    ],
  }
}
