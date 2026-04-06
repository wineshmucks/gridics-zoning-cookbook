'use client'

import { useMemo, useState } from 'react'

import { appendScopePathToHref } from '../lib/org-url'

type CustomerChoice = {
  orgid: string
  path_alias?: string | null
  client_id: string
  city_name: string
  department_name: string
}

type Props = {
  customers: CustomerChoice[]
  returnTo: string
}

export function JurisdictionPickerClient({ customers, returnTo }: Props) {
  const [query, setQuery] = useState('')

  const filteredCustomers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) {
      return customers
    }

    return customers.filter((customer) =>
      [customer.city_name, customer.department_name, customer.client_id]
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery),
    )
  }, [customers, query])

  const buildCustomerHref = (customer: CustomerChoice) => {
    const scopedHref = appendScopePathToHref(returnTo, customer.path_alias || `/${customer.orgid}`)
    return scopedHref !== '/' && scopedHref.endsWith('/') ? scopedHref.slice(0, -1) : scopedHref
  }

  return (
    <div className="jurisdiction-picker-stack">
      <div className="jurisdiction-picker-toolbar">
        <label className="field jurisdiction-picker-search">
          <span>Find jurisdiction</span>
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
              className="jurisdiction-picker-search-input"
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
              }}
              placeholder="Search jurisdictions"
            />
          </span>
          <span className="jurisdiction-picker-search-note">
            Search by city, department, or jurisdiction ID.
          </span>
        </label>
      </div>

      <div className="jurisdiction-picker-grid">
        {filteredCustomers.map((customer) => (
          <article key={customer.orgid} className="jurisdiction-picker-card">
            <div className="jurisdiction-picker-card-top">
              <span className="jurisdiction-picker-status">Available now</span>
            </div>

            <div className="jurisdiction-picker-card-body">
              <div>
                <h2 className="jurisdiction-picker-card-title">{customer.city_name}</h2>
                <p className="jurisdiction-picker-card-copy">{customer.department_name}</p>
              </div>
              <div className="jurisdiction-picker-metadata" aria-label="Available tools">
                <span className="jurisdiction-picker-meta-item">Letters available</span>
                <span className="jurisdiction-picker-meta-item">Chat assistant available</span>
                <span className="jurisdiction-picker-meta-item">Property search available</span>
              </div>
            </div>

            <div className="jurisdiction-picker-actions">
              <a
                className="button jurisdiction-picker-button-primary"
                href={buildCustomerHref(customer)}
              >
                Select jurisdiction
              </a>
            </div>
          </article>
        ))}
      </div>

      {filteredCustomers.length === 0 ? (
        <p className="jurisdiction-picker-empty-copy">
          No jurisdictions match that search yet.
        </p>
      ) : null}
    </div>
  )
}
