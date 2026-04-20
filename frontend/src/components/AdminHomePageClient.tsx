'use client'

import { useEffect, useState, useTransition } from 'react'

import type { AdminHomePageFaqItem, AdminHomePagePayload, AdminHomePageServiceItem } from '../app/admin/actions'
import { fetchAdminHomePageContentAction, saveAdminHomePageContentAction } from '../app/admin/actions'
import { AdminSectionTitle } from './AdminSectionTitle'

function slugify(value: string) {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || `item-${Date.now()}`
  )
}

function buildServiceItem(): AdminHomePageServiceItem {
  return {
    id: `service-${Date.now()}`,
    title: 'New service',
    description: '',
    processing_time: '',
    fee: '',
  }
}

function buildFaqItem(): AdminHomePageFaqItem {
  return {
    id: `faq-${Date.now()}`,
    question: 'New question',
    answer: '',
  }
}

export function AdminHomePageClient({ initialPayload }: { initialPayload: AdminHomePagePayload }) {
  const [payload, setPayload] = useState(initialPayload)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'homepage' | 'about' | 'services' | 'contact' | 'faq'>('homepage')
  const [isPending, startTransition] = useTransition()

  useEffect(() => {
    setPayload(initialPayload)
  }, [initialPayload])

  async function refresh(successMessage?: string) {
    const nextPayload = await fetchAdminHomePageContentAction()
    setPayload(nextPayload)
    setMessage(successMessage || null)
  }

  return (
    <section className="admin-sections">
      <div className="card admin-section-detail admin-home-hero">
        <div className="admin-header">
          <div>
            <div className="eyebrow">Admin</div>
            <AdminSectionTitle icon="home-page" title="Home Page Content">
              <p className="admin-copy">
                Manage the public-facing content for {payload.client.city_name}. All changes are scoped
                to this jurisdiction.
              </p>
            </AdminSectionTitle>
          </div>
          <button
            type="button"
            className="button"
            disabled={isPending}
            onClick={() => {
              setError(null)
              setMessage(null)
              startTransition(async () => {
                try {
                  const result = await saveAdminHomePageContentAction(payload.content)
                  await refresh(result.success)
                } catch (nextError) {
                  setError(
                    nextError instanceof Error ? nextError.message : 'Unable to save home page content.',
                  )
                }
              })
            }}
          >
            {isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        {message ? <div className="success-banner">{message}</div> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <div className="admin-home-tabs">
          {[
            ['homepage', 'Homepage'],
            ['about', 'About'],
            ['services', 'Services'],
            ['contact', 'Contact'],
            ['faq', 'FAQ'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`admin-home-tab${activeTab === key ? ' is-active' : ''}`}
              onClick={() => setActiveTab(key as typeof activeTab)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'homepage' ? (
        <div className="card admin-home-section">
          <h2 className="admin-section-title">Hero Section</h2>
          <div className="admin-home-grid">
            <label className="field">
              Badge
              <input
                value={payload.content.hero.badge}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      hero: { ...current.content.hero, badge: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field full-span">
              Main heading
              <input
                value={payload.content.hero.title}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      hero: { ...current.content.hero, title: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field full-span">
              Subtitle
              <textarea
                rows={4}
                value={payload.content.hero.subtitle}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      hero: { ...current.content.hero, subtitle: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field">
              Primary button
              <input
                value={payload.content.hero.primary_button_text}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      hero: { ...current.content.hero, primary_button_text: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field">
              Secondary button
              <input
                value={payload.content.hero.secondary_button_text}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      hero: { ...current.content.hero, secondary_button_text: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field">
              Learn more button
              <input
                value={payload.content.hero.learn_more_text}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      hero: { ...current.content.hero, learn_more_text: event.target.value },
                    },
                  }))
                }
              />
            </label>
          </div>

          <div className="admin-home-card-grid">
            {payload.content.hero.stats.map((item, index) => (
              <article key={`${item.label}-${index}`} className="card admin-home-item-card">
                <label className="field">
                  Label
                  <input
                    value={item.label}
                    onChange={(event) =>
                      setPayload((current) => ({
                        ...current,
                        content: {
                          ...current.content,
                          hero: {
                            ...current.content.hero,
                            stats: current.content.hero.stats.map((stat, statIndex) =>
                              statIndex === index ? { ...stat, label: event.target.value } : stat,
                            ),
                          },
                        },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  Value
                  <input
                    value={item.value}
                    onChange={(event) =>
                      setPayload((current) => ({
                        ...current,
                        content: {
                          ...current.content,
                          hero: {
                            ...current.content.hero,
                            stats: current.content.hero.stats.map((stat, statIndex) =>
                              statIndex === index ? { ...stat, value: event.target.value } : stat,
                            ),
                          },
                        },
                      }))
                    }
                  />
                </label>
                <label className="field">
                  Icon
                  <input
                    value={item.icon}
                    onChange={(event) =>
                      setPayload((current) => ({
                        ...current,
                        content: {
                          ...current.content,
                          hero: {
                            ...current.content.hero,
                            stats: current.content.hero.stats.map((stat, statIndex) =>
                              statIndex === index ? { ...stat, icon: event.target.value } : stat,
                            ),
                          },
                        },
                      }))
                    }
                  />
                </label>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {activeTab === 'about' ? (
        <div className="card admin-home-section">
          <h2 className="admin-section-title">About Section</h2>
          <div className="admin-home-grid">
            <label className="field full-span">
              Section title
              <input
                value={payload.content.about.title}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      about: { ...current.content.about, title: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field full-span">
              Body copy
              <textarea
                rows={6}
                value={payload.content.about.body}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      about: { ...current.content.about, body: event.target.value },
                    },
                  }))
                }
              />
            </label>
          </div>
        </div>
      ) : null}

      {activeTab === 'services' ? (
        <div className="card admin-home-section">
          <div className="admin-home-section-head">
            <h2 className="admin-section-title">Services Overview</h2>
            <button
              type="button"
              className="button secondary"
              onClick={() =>
                setPayload((current) => ({
                  ...current,
                  content: {
                    ...current.content,
                    services: [...current.content.services, buildServiceItem()],
                  },
                }))
              }
            >
              Add Service
            </button>
          </div>

          <div className="admin-home-card-grid">
            {payload.content.services.map((service, index) => (
              <article key={service.id} className="card admin-home-item-card">
                <div className="admin-home-item-head">
                  <h3 className="admin-section-title">{service.title || `Service ${index + 1}`}</h3>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() =>
                      setPayload((current) => ({
                        ...current,
                        content: {
                          ...current.content,
                          services: current.content.services.filter((_, itemIndex) => itemIndex !== index),
                        },
                      }))
                    }
                  >
                    Remove
                  </button>
                </div>
                <div className="admin-home-grid">
                  <label className="field full-span">
                    Service title
                    <input
                      value={service.title}
                      onChange={(event) =>
                        setPayload((current) => ({
                          ...current,
                          content: {
                            ...current.content,
                            services: current.content.services.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, title: event.target.value, id: slugify(event.target.value) }
                                : item,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="field full-span">
                    Description
                    <textarea
                      rows={4}
                      value={service.description}
                      onChange={(event) =>
                        setPayload((current) => ({
                          ...current,
                          content: {
                            ...current.content,
                            services: current.content.services.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, description: event.target.value } : item,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    Processing time
                    <input
                      value={service.processing_time}
                      onChange={(event) =>
                        setPayload((current) => ({
                          ...current,
                          content: {
                            ...current.content,
                            services: current.content.services.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, processing_time: event.target.value } : item,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="field">
                    Fee label
                    <input
                      value={service.fee}
                      onChange={(event) =>
                        setPayload((current) => ({
                          ...current,
                          content: {
                            ...current.content,
                            services: current.content.services.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, fee: event.target.value } : item,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {activeTab === 'contact' ? (
        <div className="card admin-home-section">
          <h2 className="admin-section-title">Contact Section</h2>
          <div className="admin-home-grid">
            <label className="field full-span">
              Section title
              <input
                value={payload.content.contact.title}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      contact: { ...current.content.contact, title: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field full-span">
              Body copy
              <textarea
                rows={5}
                value={payload.content.contact.body}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      contact: { ...current.content.contact, body: event.target.value },
                    },
                  }))
                }
              />
            </label>
            <label className="field">
              Email
              <input
                value={payload.content.contact.email || ''}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      contact: { ...current.content.contact, email: event.target.value || null },
                    },
                  }))
                }
              />
            </label>
            <label className="field">
              Phone
              <input
                value={payload.content.contact.phone || ''}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      contact: { ...current.content.contact, phone: event.target.value || null },
                    },
                  }))
                }
              />
            </label>
            <label className="field full-span">
              Address
              <input
                value={payload.content.contact.address || ''}
                onChange={(event) =>
                  setPayload((current) => ({
                    ...current,
                    content: {
                      ...current.content,
                      contact: { ...current.content.contact, address: event.target.value || null },
                    },
                  }))
                }
              />
            </label>
          </div>
        </div>
      ) : null}

      {activeTab === 'faq' ? (
        <div className="card admin-home-section">
          <div className="admin-home-section-head">
            <h2 className="admin-section-title">FAQ</h2>
            <button
              type="button"
              className="button secondary"
              onClick={() =>
                setPayload((current) => ({
                  ...current,
                  content: {
                    ...current.content,
                    faq: [...current.content.faq, buildFaqItem()],
                  },
                }))
              }
            >
              Add Question
            </button>
          </div>

          <div className="admin-home-card-grid">
            {payload.content.faq.map((faq, index) => (
              <article key={faq.id} className="card admin-home-item-card">
                <div className="admin-home-item-head">
                  <h3 className="admin-section-title">Question {index + 1}</h3>
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() =>
                      setPayload((current) => ({
                        ...current,
                        content: {
                          ...current.content,
                          faq: current.content.faq.filter((_, itemIndex) => itemIndex !== index),
                        },
                      }))
                    }
                  >
                    Remove
                  </button>
                </div>
                <div className="admin-home-grid">
                  <label className="field full-span">
                    Question
                    <input
                      value={faq.question}
                      onChange={(event) =>
                        setPayload((current) => ({
                          ...current,
                          content: {
                            ...current.content,
                            faq: current.content.faq.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, question: event.target.value, id: slugify(event.target.value) }
                                : item,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="field full-span">
                    Answer
                    <textarea
                      rows={5}
                      value={faq.answer}
                      onChange={(event) =>
                        setPayload((current) => ({
                          ...current,
                          content: {
                            ...current.content,
                            faq: current.content.faq.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, answer: event.target.value } : item,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}
