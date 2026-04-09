import Link from 'next/link'

import { BuildingLogo } from '../components/BuildingLogo'
import { getCurrentHost, getCurrentOrgId, getCurrentScopePath } from '../lib/org-context'
import { appendScopePathToHref, buildAssistantHref, buildLettersHref } from '../lib/org-url'
import { getTenantConfig } from '../lib/tenant'

export default async function HomePage() {
  const tenant = await getTenantConfig()
  const orgId = await getCurrentOrgId()
  const currentScopePath = await getCurrentScopePath()
  const currentHost = await getCurrentHost()
  const content = tenant.home_page_content
  const standardPrice = `$${(tenant.standard_letter_fee_cents / 100).toFixed(2)}`
  const comprehensivePrice = `$${(tenant.comprehensive_letter_fee_cents / 100).toFixed(2)}`
  const expeditedPrice = `+$${(tenant.expedited_fee_cents / 100).toFixed(2)}`
  const topServices = content.services.slice(0, 2)
  const infoServices = content.services.slice(0, 3)

  return (
    <>
      <section className="home-hero">
        <div className="home-container">
          <div className="home-hero-inner">
            <div className="hero-chip">{content.hero.badge}</div>
            <h1 className="home-hero-title">{content.hero.title}</h1>
            <p className="home-hero-copy">{content.hero.subtitle}</p>
            <div className="button-row">
              <Link className="button button-hero-light" href={buildLettersHref('/request/new', currentScopePath, currentHost)}>
                {content.hero.primary_button_text}
              </Link>
              <Link
                className="button button-hero-outline"
                href={buildAssistantHref(currentScopePath, currentHost)}
              >
                {content.hero.secondary_button_text}
              </Link>
              <a className="button button-hero-outline" href="#info-section">
                {content.hero.learn_more_text}
              </a>
            </div>
            <div className="hero-stats">
              {content.hero.stats.map((item, index) => (
                <div key={`${item.label}-${index}`} className="hero-stat">
                  {index > 0 ? <div className="hero-divider" /> : null}
                  <div className="hero-stat-icon">{item.icon}</div>
                  <div>
                    <p>{item.label}</p>
                    <strong>{item.value}</strong>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="info-section" className="home-section">
        <div className="home-container">
          <div className="section-center">
            <h2>{content.about.title}</h2>
            <p>{content.about.body}</p>
          </div>

          <div className="home-grid home-grid-3">
            {infoServices.map((service) => (
              <div key={service.id} className="feature-card feature-card-soft">
                <div className="feature-icon">{service.title.slice(0, 1).toUpperCase()}</div>
                <h3>{service.title}</h3>
                <p>{service.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="letter-types-section" className="home-section home-section-alt">
        <div className="home-container">
          <div className="section-center">
            <h2>Available Services</h2>
            <p>Jurisdiction-specific offerings and timing</p>
          </div>

          <div className="home-grid home-grid-2">
            {topServices.map((service, index) => (
              <div key={service.id} className={`letter-card${index === 1 ? ' letter-card-featured' : ''}`}>
                {index === 1 ? <div className="letter-badge">Featured</div> : null}
                <div className="letter-card-head">
                  <div>
                    <h3>{service.title}</h3>
                    <p>{service.description}</p>
                  </div>
                  <div className="letter-price">
                    <span>Fee</span>
                    <strong>{service.fee}</strong>
                  </div>
                </div>
                <ul className="check-list">
                  <li>Processing time: {service.processing_time}</li>
                  <li>Jurisdiction-specific public service content</li>
                  <li>Online request intake and status visibility</li>
                </ul>
                {index === 1 && tenant.zoning_code_url ? (
                  <a className="button secondary" href={tenant.zoning_code_url} target="_blank" rel="noreferrer">
                    Review Zoning Code
                  </a>
                ) : null}
                <Link className="button button-block" href={buildLettersHref('/request/new', currentScopePath, currentHost)}>
                  {content.hero.primary_button_text}
                </Link>
              </div>
            ))}
          </div>

          <div className="expedite-card">
            <div className="expedite-content">
              <div className="expedite-icon">⚡</div>
              <div>
                <h4>Expedited Processing Available</h4>
                <p>Need your letter faster? Upgrade to 24-hour processing</p>
              </div>
            </div>
            <div className="letter-price">
              <span>Additional fee</span>
              <strong>{expeditedPrice}</strong>
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works-section" className="home-section">
        <div className="home-container">
          <div className="section-center">
            <h2>How It Works</h2>
            <p>Get your zoning verification letter in 4 simple steps</p>
          </div>

          <div className="home-grid home-grid-4">
            {[
              [
                '1',
                'Select Property',
                'Use our interactive map to search and select your property by address or parcel number',
              ],
              [
                '2',
                'Create Account',
                'Sign up or log in to your account to manage and track all your letter requests',
              ],
              [
                '3',
                'Submit & Pay',
                'Complete the request form, review your order, and securely pay online with credit card',
              ],
              [
                '4',
                'Receive Letter',
                'Track your request status and receive your official letter via email or mail',
              ],
            ].map(([step, title, copy]) => (
              <div key={step} className="step-card">
                <div className="step-number">{step}</div>
                <div className="step-stem" />
                <h3>{title}</h3>
                <p>{copy}</p>
              </div>
            ))}
          </div>

          <div className="cta-band">
            <h3>Ready to Get Started?</h3>
            <p>Request your zoning verification letter today</p>
            <Link className="button button-hero-light" href={buildLettersHref('/request/new', currentScopePath, currentHost)}>
              {content.hero.primary_button_text}
            </Link>
          </div>
        </div>
      </section>

      <section id="features-section" className="home-section home-section-alt">
        <div className="home-container">
          <div className="section-center">
            <h2>Why Choose Our Service?</h2>
            <p>Modern, efficient, and transparent zoning verification process</p>
          </div>

          <div className="home-grid home-grid-3">
            {[
              [
                'F',
                'Fast Processing',
                'Standard letters delivered in under 3 business days, with 24-hour expedited option available',
              ],
              [
                'M',
                'Interactive Map',
                'Easy property selection with our integrated map system - search by address or parcel number',
              ],
              [
                'E',
                'Real-Time Tracking',
                'Track your request status from submission to delivery with email notifications at each step',
              ],
              [
                'S',
                'Secure Payment',
                'PCI DSS compliant payment processing with industry-standard encryption for your protection',
              ],
              [
                'O',
                'Order History',
                'Access all your past requests and letters anytime through your personal account dashboard',
              ],
              [
                'C',
                'Official Documentation',
                'All letters include official city seal, authorized signatures, and verified zoning data',
              ],
            ].map(([icon, title, copy]) => (
              <div key={title} className="feature-card">
                <div className="feature-icon feature-icon-soft">{icon}</div>
                <h3>{title}</h3>
                <p>{copy}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="faq-section" className="home-section">
        <div className="home-container">
          <div className="section-center">
            <h2>Frequently Asked Questions</h2>
            <p>Find answers to common questions about zoning verification letters</p>
          </div>

          <div className="faq-list">
            {content.faq.map((item) => (
              <div key={item.id} className="faq-item">
                <div className="faq-head">
                  <div>
                    <h3>{item.question}</h3>
                    <p>{item.answer}</p>
                  </div>
                  <span className="faq-chevron">⌄</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="cta-section" className="support-section">
        <div className="home-container support-section-inner">
          <h2>{content.contact.title}</h2>
          <p>{content.contact.body}</p>
          <div className="support-cards">
            <div className="support-card">
              <h3>Call Us</h3>
              <p>{content.contact.phone || tenant.support_phone || '(555) 123-4567'}</p>
              <span>Mon-Fri, 8am-5pm</span>
            </div>
            <div className="support-card">
              <h3>Email Us</h3>
              <p>{content.contact.email || tenant.support_email || 'planning@dreamtown.gov'}</p>
              <span>Response within 24 hours</span>
            </div>
            <div className="support-card">
              <h3>Fees</h3>
              <p>
                Standard from {standardPrice}, comprehensive from {comprehensivePrice}
              </p>
              <span>Expedited: {expeditedPrice}</span>
            </div>
          </div>
        </div>
      </section>

      <footer className="home-footer">
        <div className="home-container">
          <div className="home-grid home-grid-footer">
            <div>
              <div className="brand brand-footer">
                <div className="brand-mark brand-mark-public brand-mark-small">
                  <BuildingLogo />
                </div>
                <div>
                  <h3>{tenant.city_name}</h3>
                  <p>{tenant.department_name}</p>
                </div>
              </div>
              <p className="footer-copy">
                Official zoning verification letter system for {tenant.city_name}.
              </p>
            </div>

            <div>
              <h4>Quick Links</h4>
              <ul className="footer-list">
                <li>
                  <Link href={buildLettersHref('/request/new', currentScopePath, currentHost)}>Request Letter</Link>
                </li>
                <li>
                  <Link href={buildLettersHref('/request/new', currentScopePath, currentHost)}>Property Search</Link>
                </li>
                <li>
                  <Link href={buildLettersHref('/account/requests', currentScopePath, currentHost)}>Track Request</Link>
                </li>
                <li>
                  <a href="#faq-section">FAQs</a>
                </li>
              </ul>
            </div>

            <div>
              <h4>Resources</h4>
              <ul className="footer-list">
                <li>
                  <a href="#letter-types-section">Services</a>
                </li>
                <li>
                  <a href="#features-section">Why Choose Us</a>
                </li>
                <li>
                  <a href="#faq-section">Payment Options</a>
                </li>
                <li>
                  <a href="#cta-section">Contact Support</a>
                </li>
              </ul>
            </div>

            <div>
              <h4>Office</h4>
              <ul className="footer-list">
                <li>{content.contact.address || tenant.contact_address || tenant.city_name}</li>
                <li>{content.contact.email || tenant.support_email || 'support@example.gov'}</li>
                <li>{content.contact.phone || tenant.support_phone || '(555) 123-4567'}</li>
              </ul>
            </div>
          </div>
        </div>
      </footer>
    </>
  )
}
