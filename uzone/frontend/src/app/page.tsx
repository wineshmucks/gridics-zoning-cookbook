import Link from 'next/link'

import { BuildingLogo } from '../components/BuildingLogo'
import { getCurrentOrgId } from '../lib/org-context'
import { appendOrgIdToHref } from '../lib/org-url'
import { getTenantConfig } from '../lib/tenant'

export default async function HomePage() {
  const tenant = await getTenantConfig()
  const orgId = await getCurrentOrgId()
  const standardPrice = `$${(tenant.standard_letter_fee_cents / 100).toFixed(2)}`
  const comprehensivePrice = `$${(tenant.comprehensive_letter_fee_cents / 100).toFixed(2)}`
  const expeditedPrice = `+$${(tenant.expedited_fee_cents / 100).toFixed(2)}`

  return (
    <>
      <section className="home-hero">
        <div className="home-container">
          <div className="home-hero-inner">
            <div className="hero-chip">Official City Documentation</div>
            <h1 className="home-hero-title">Zoning Verification Letters</h1>
            <p className="home-hero-copy">
              Request official zoning verification letters for your property quickly and securely.
              Get verified documentation for real estate transactions, permits, and legal purposes
              in less than 3 business days.
            </p>
            <div className="button-row">
              <Link className="button button-hero-light" href={appendOrgIdToHref('/request/new', orgId)}>
                Request a Letter
              </Link>
              <Link className="button button-hero-outline" href={appendOrgIdToHref('/assistant', orgId)}>
                Ask the Zoning Assistant
              </Link>
              <a className="button button-hero-outline" href="#info-section">
                Learn More
              </a>
            </div>
            <div className="hero-stats">
              <div className="hero-stat">
                <div className="hero-stat-icon">◔</div>
                <div>
                  <p>Processing Time</p>
                  <strong>Under 3 Days</strong>
                </div>
              </div>
              <div className="hero-divider" />
              <div className="hero-stat">
                <div className="hero-stat-icon">◈</div>
                <div>
                  <p>Security</p>
                  <strong>PCI Compliant</strong>
                </div>
              </div>
              <div className="hero-divider" />
              <div className="hero-stat">
                <div className="hero-stat-icon">◉</div>
                <div>
                  <p>Updates</p>
                  <strong>Real-Time Tracking</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="info-section" className="home-section">
        <div className="home-container">
          <div className="section-center">
            <h2>What is a Zoning Verification Letter?</h2>
            <p>
              An official document from the {tenant.city_name} {tenant.department_name} that
              confirms the zoning classification and permitted uses for a specific property.
            </p>
          </div>

          <div className="home-grid home-grid-3">
            <div className="feature-card feature-card-soft">
              <div className="feature-icon">H</div>
              <h3>Real Estate Transactions</h3>
              <p>
                Required for property sales, purchases, and due diligence processes to verify zoning
                compliance and permitted uses.
              </p>
            </div>

            <div className="feature-card feature-card-soft">
              <div className="feature-icon">T</div>
              <h3>Permit Applications</h3>
              <p>
                Essential documentation for building permits, business licenses, and development
                applications to ensure zoning compliance.
              </p>
            </div>

            <div className="feature-card feature-card-soft">
              <div className="feature-icon">L</div>
              <h3>Legal &amp; Financial</h3>
              <p>
                Required for legal proceedings, mortgage applications, and insurance purposes to
                establish official zoning status.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="letter-types-section" className="home-section home-section-alt">
        <div className="home-container">
          <div className="section-center">
            <h2>Available Letter Types</h2>
            <p>Choose the verification letter that meets your specific needs</p>
          </div>

          <div className="home-grid home-grid-2">
            <div className="letter-card">
              <div className="letter-card-head">
                <div>
                  <h3>Standard Zoning Letter</h3>
                  <p>Basic zoning classification and permitted uses</p>
                </div>
                <div className="letter-price">
                  <span>Starting at</span>
                  <strong>{standardPrice}</strong>
                </div>
              </div>
              <ul className="check-list">
                <li>Zoning classification</li>
                <li>Permitted uses list</li>
                <li>Basic property information</li>
                <li>Official city seal and signature</li>
                <li>3 business day processing</li>
              </ul>
              <Link
                className="button button-block"
                href={appendOrgIdToHref('/request/new?letter_type=standard', orgId)}
              >
                Select Standard Letter
              </Link>
            </div>

            <div className="letter-card letter-card-featured">
              <div className="letter-badge">Most Popular</div>
              <div className="letter-card-head">
                <div>
                  <h3>Comprehensive Zoning Letter</h3>
                  <p>Detailed zoning analysis with restrictions</p>
                </div>
                <div className="letter-price">
                  <span>Starting at</span>
                  <strong>{comprehensivePrice === '$xx.xx' ? '$xxx.xx' : comprehensivePrice}</strong>
                </div>
              </div>
              <ul className="check-list">
                <li>Everything in Standard, plus:</li>
                <li>Detailed setback requirements</li>
                <li>Height and density restrictions</li>
                <li>Parking requirements</li>
                <li>Overlay district information</li>
                <li>Referenced zoning code sections</li>
              </ul>
              {tenant.zoning_code_url ? (
                <a
                  className="button secondary"
                  href={tenant.zoning_code_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Review Zoning Code
                </a>
              ) : null}
              <Link
                className="button button-block"
                href={appendOrgIdToHref('/request/new?letter_type=comprehensive', orgId)}
              >
                Select Comprehensive Letter
              </Link>
            </div>
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
            <Link className="button button-hero-light" href={appendOrgIdToHref('/request/new', orgId)}>
              Start Your Request
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
            {[
              [
                'How long does it take to receive my letter?',
                "Standard processing takes less than 3 business days. Expedited processing (24 hours) is available for an additional $50 fee. You'll receive email notifications at each stage of processing.",
              ],
              [
                'What payment methods are accepted?',
                'We accept all major credit cards through our secure payment gateway. All transactions are PCI DSS compliant and encrypted for your security.',
              ],
              [
                'Can I request letters for multiple properties?',
                'Yes, you can select multiple parcels during the property selection process. Each property will require a separate letter and fee.',
              ],
              [
                'How will I receive my zoning verification letter?',
                'You can choose to receive your letter via email (PDF format) or physical mail. Email delivery is instant upon approval, while physical mail takes 3-5 additional business days.',
              ],
              [
                'What information is included in the letter?',
                'Standard letters include zoning classification, permitted uses, and basic property information. Comprehensive letters also include setbacks, height restrictions, parking requirements, and overlay district information.',
              ],
              [
                'Can I track the status of my request?',
                'Yes, once you create an account and submit a request, you can log in anytime to view your order history and track the current status of all your requests in real-time.',
              ],
            ].map(([question, answer]) => (
              <div key={question} className="faq-item">
                <div className="faq-head">
                  <div>
                    <h3>{question}</h3>
                    <p>{answer}</p>
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
          <h2>Need Help Getting Started?</h2>
          <p>
            Our {tenant.department_name} staff is here to assist you with any questions about the
            zoning verification letter process.
          </p>
          <div className="support-cards">
            <div className="support-card">
              <h3>Call Us</h3>
              <p>{tenant.support_phone || '(555) 123-4567'}</p>
              <span>Mon-Fri, 8am-5pm</span>
            </div>
            <div className="support-card">
              <h3>Email Us</h3>
              <p>{tenant.support_email || 'planning@dreamtown.gov'}</p>
              <span>Response within 24 hours</span>
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
                  <Link href={appendOrgIdToHref('/request/new', orgId)}>Request Letter</Link>
                </li>
                <li>
                  <Link href={appendOrgIdToHref('/request/new', orgId)}>Property Search</Link>
                </li>
                <li>
                  <Link href={appendOrgIdToHref('/account/requests', orgId)}>Track Request</Link>
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
                  <a href="#letter-types-section">Zoning Code</a>
                </li>
                <li>
                  <a href="#features-section">Zoning Map</a>
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
              <h4>Contact</h4>
              <ul className="footer-list">
                <li>{tenant.contact_address || '123 Main St, Dream Town'}</li>
                <li>{tenant.support_phone || '(555) 123-4567'}</li>
                <li>{tenant.support_email || 'planning@dreamtown.gov'}</li>
              </ul>
            </div>
          </div>
          <div className="footer-bar">
            <p>© 2024 {tenant.city_name}. All rights reserved.</p>
            <div className="footer-inline-links">
              <a href="/">Privacy Policy</a>
              <a href="/">Terms of Service</a>
              <a href="/">Accessibility</a>
            </div>
          </div>
        </div>
      </footer>
    </>
  )
}
