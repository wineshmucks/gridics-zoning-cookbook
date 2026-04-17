'use client'

import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'

import { appendScopePathToHref } from '../lib/org-url'
import { BuildingLogo } from './BuildingLogo'

type CustomerChoice = {
  orgid: string
  path_alias?: string | null
  logo_path?: string | null
  client_id: string
  city_name: string
  department_name: string
}

type Props = {
  customers: CustomerChoice[]
  suggestedCustomers: CustomerChoice[]
  returnTo: string
}

function normalizeText(value: string) {
  return value.trim().toLowerCase()
}

function buildSearchCorpus(customer: CustomerChoice) {
  return [
    customer.city_name,
    customer.department_name,
    customer.client_id,
    customer.orgid,
    customer.path_alias || '',
  ]
    .join(' ')
    .toLowerCase()
}

function scoreCustomer(customer: CustomerChoice, query: string) {
  const normalizedQuery = normalizeText(query)
  if (!normalizedQuery) {
    return 0
  }

  const corpus = buildSearchCorpus(customer)
  const tokens = normalizedQuery.split(/\s+/).filter(Boolean)
  if (tokens.length === 0) {
    return 0
  }

  let score = 0
  const corpusStartsWithQuery = corpus.startsWith(normalizedQuery)
  const corpusContainsQuery = corpus.includes(normalizedQuery)

  if (corpusStartsWithQuery) {
    score += 100
  } else if (corpusContainsQuery) {
    score += 50
  }

  for (const token of tokens) {
    if (corpus.startsWith(token)) {
      score += 30
    } else if (corpus.includes(token)) {
      score += 12
    } else {
      score -= 10
    }
  }

  if (customer.city_name.toLowerCase().startsWith(normalizedQuery)) {
    score += 25
  }

  return score
}

function buildCustomerHref(customer: CustomerChoice, returnTo: string) {
  const scopedHref = appendScopePathToHref(returnTo, customer.path_alias || `/${customer.orgid}`)
  return scopedHref !== '/' && scopedHref.endsWith('/') ? scopedHref.slice(0, -1) : scopedHref
}

function JurisdictionCard({
  customer,
  returnTo,
}: {
  customer: CustomerChoice
  returnTo: string
}) {
  return (
    <article className="jurisdiction-picker-card">
      <div className="jurisdiction-picker-card-body">
        <div className="jurisdiction-picker-card-identity">
          <div className={`jurisdiction-picker-card-logo${customer.logo_path ? ' has-image' : ''}`}>
            <BuildingLogo logoUrl={customer.logo_path || null} alt={`${customer.city_name} logo`} />
          </div>
          <div className="jurisdiction-picker-card-copy-stack">
            <h2 className="jurisdiction-picker-card-title">{customer.city_name}</h2>
            <p className="jurisdiction-picker-card-copy">{customer.department_name}</p>
          </div>
        </div>

        <div className="jurisdiction-picker-card-support">
          <div className="jurisdiction-picker-actions">
            <a className="button jurisdiction-picker-button-primary" href={buildCustomerHref(customer, returnTo)}>
              Continue
            </a>
          </div>
        </div>
      </div>
    </article>
  )
}

function SuggestedJurisdictionCard({
  customer,
  returnTo,
}: {
  customer: CustomerChoice
  returnTo: string
}) {
  return <JurisdictionCard customer={customer} returnTo={returnTo} />
}

function JurisdictionSection({
  title,
  subtitle,
  customers,
  emptyCopy,
  returnTo,
}: {
  title: string
  subtitle?: string
  customers: CustomerChoice[]
  emptyCopy?: string
  returnTo: string
}) {
  return (
    <section className="jurisdiction-picker-results-section">
      <div className="jurisdiction-picker-section-head">
        <div>
          <h2 className="jurisdiction-picker-section-title">{title}</h2>
          {subtitle ? <p className="jurisdiction-picker-section-copy">{subtitle}</p> : null}
        </div>
      </div>

      {customers.length > 0 ? (
        <div className="jurisdiction-picker-results-list">
          {customers.map((customer) => (
            <JurisdictionCard key={customer.orgid} customer={customer} returnTo={returnTo} />
          ))}
        </div>
      ) : emptyCopy ? (
        <p className="jurisdiction-picker-empty-copy">{emptyCopy}</p>
      ) : null}
    </section>
  )
}

export function JurisdictionPickerClient({ customers, suggestedCustomers, returnTo }: Props) {
  const [query, setQuery] = useState('')
  const searchRef = useRef<HTMLInputElement | null>(null)
  const deferredQuery = useDeferredValue(query)

  useEffect(() => {
    searchRef.current?.focus()
  }, [])

  const filteredCustomers = useMemo(() => {
    const normalizedQuery = deferredQuery.trim().toLowerCase()
    if (!normalizedQuery) {
      return customers
    }

    return [...customers]
      .map((customer) => ({ customer, score: scoreCustomer(customer, normalizedQuery) }))
      .filter(({ score }) => score > -10)
      .sort((left, right) => {
        if (right.score !== left.score) {
          return right.score - left.score
        }
        return left.customer.city_name.localeCompare(right.customer.city_name)
      })
      .map(({ customer }) => customer)
  }, [customers, deferredQuery])

  const quickAccessCustomers = useMemo(() => {
    const recentOrSuggested = suggestedCustomers.slice(0, 4)
    const seen = new Set<string>()
    return recentOrSuggested.filter((customer) => {
      if (seen.has(customer.orgid)) {
        return false
      }
      seen.add(customer.orgid)
      return true
    })
  }, [suggestedCustomers])

  const hasQuery = query.trim().length > 0
  const visibleCustomers = hasQuery ? filteredCustomers : customers
  const filteredCount = visibleCustomers.length
  const resultsSubtitle = hasQuery
    ? `${filteredCount} jurisdiction${filteredCount === 1 ? '' : 's'} match your search.`
    : 'Search first, then continue immediately once you find the right jurisdiction.'

  return (
    <div className="jurisdiction-picker-stack">
      <section className="jurisdiction-picker-search-section">
        <div className="jurisdiction-picker-toolbar">
          <label className="field jurisdiction-picker-search">
            <span>Find your city or jurisdiction</span>
            <span className="jurisdiction-picker-search-field">
              <span className="jurisdiction-picker-search-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path
                    d="M10.5 4.5a6 6 0 1 0 3.783 10.657l4.28 4.28 1.414-1.414-4.28-4.28A6 6 0 0 0 10.5 4.5Zm0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z"
                    fill="currentColor"
                  />
                </svg>
              </span>
              <input
                ref={searchRef}
                className="jurisdiction-picker-search-input"
                type="search"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                }}
                placeholder="Search by city, state, department, or jurisdiction ID"
                autoComplete="off"
                spellCheck={false}
                autoCapitalize="off"
              />
            </span>
          </label>
        </div>
      </section>

      <section className="jurisdiction-picker-results-section">
        <div className="jurisdiction-picker-section-head">
          <div>
            <h2 className="jurisdiction-picker-section-title">Recent or suggested jurisdictions</h2>
            <p className="jurisdiction-picker-section-copy">Fast access to a few commonly used jurisdictions.</p>
          </div>
        </div>

        {quickAccessCustomers.length > 0 ? (
          <div className="jurisdiction-picker-results-list jurisdiction-picker-results-list-suggested">
            {quickAccessCustomers.map((customer) => (
              <SuggestedJurisdictionCard key={customer.orgid} customer={customer} returnTo={returnTo} />
            ))}
          </div>
        ) : (
          <p className="jurisdiction-picker-empty-copy">
            Suggested jurisdictions will appear here after you start using the system.
          </p>
        )}
      </section>

      <JurisdictionSection
        title="Available jurisdictions"
        subtitle={resultsSubtitle}
        customers={visibleCustomers}
        returnTo={returnTo}
        emptyCopy={
          hasQuery
            ? 'No jurisdictions found. Try another search term or contact support if you need access to a jurisdiction.'
            : undefined
        }
      />
    </div>
  )
}
