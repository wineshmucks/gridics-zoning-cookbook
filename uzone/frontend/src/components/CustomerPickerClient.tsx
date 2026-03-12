'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'

import { appendOrgIdToHref } from '../lib/org-url'

type CustomerChoice = {
  orgid: string
  client_id: string
  city_name: string
  department_name: string
}

type Props = {
  customers: CustomerChoice[]
  returnTo: string
}

export function CustomerPickerClient({ customers, returnTo }: Props) {
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

  return (
    <>
      <label className="field" style={{ marginBottom: 20 }}>
        <span>Search customers</span>
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
          }}
          placeholder="Search by city, department, or client ID"
        />
      </label>

      <div style={{ display: 'grid', gap: 12 }}>
        {filteredCustomers.map((customer) => (
          <Link
            key={customer.orgid}
            className="button secondary"
            href={appendOrgIdToHref(returnTo, customer.orgid)}
            prefetch={false}
            style={{ justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}
          >
            <span>{customer.city_name}</span>
            <span style={{ color: 'var(--muted)' }}>{customer.department_name}</span>
          </Link>
        ))}
      </div>

      {filteredCustomers.length === 0 ? (
        <p style={{ color: 'var(--muted)', marginBottom: 0 }}>
          No customers match that search yet.
        </p>
      ) : null}
    </>
  )
}
