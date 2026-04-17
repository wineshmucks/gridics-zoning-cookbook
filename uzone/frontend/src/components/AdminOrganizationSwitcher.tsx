'use client'

import { useClerk } from '@clerk/nextjs'
import { useRouter, useSearchParams } from 'next/navigation'
import { startTransition, useState } from 'react'

import type { ClientMembership } from '../lib/permissions'
import { buildInternalOrgScopePath, replaceScopePathInPathname } from '../lib/org-url'
import { useHydratedPathname } from '../lib/use-hydrated-pathname'

type Props = {
  memberships: ClientMembership[]
  selectedOrganizationId: string | null
  currentScopePath: string | null
}

export function AdminOrganizationSwitcher({ memberships, selectedOrganizationId, currentScopePath }: Props) {
  const { setActive } = useClerk()
  const pathname = useHydratedPathname()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [pendingOrganizationId, setPendingOrganizationId] = useState<string | null>(null)

  if (memberships.length <= 1) {
    return null
  }

  async function handleChange(nextOrganizationId: string) {
    if (!nextOrganizationId || nextOrganizationId === selectedOrganizationId) {
      return
    }

    const membership = memberships.find((item) => item.organizationId === nextOrganizationId)
    if (!membership) {
      return
    }

    setPendingOrganizationId(nextOrganizationId)

    try {
      await setActive({ organization: nextOrganizationId })
    } catch (error) {
      console.error('Unable to switch active organization.', error)
    }

    const params = new URLSearchParams(searchParams.toString())
    params.delete('clientid')
    const nextPathname = replaceScopePathInPathname(
      pathname,
      currentScopePath,
      buildInternalOrgScopePath(membership.organizationId),
    )
    const nextSearch = params.toString()

    startTransition(() => {
      router.replace(nextSearch ? `${nextPathname}?${nextSearch}` : nextPathname)
      router.refresh()
    })
  }

  return (
    <section className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'end' }}>
        <div>
          <h1 className="section-title" style={{ marginBottom: 8 }}>
            Admin Organization
          </h1>
          <p style={{ color: 'var(--muted)', margin: 0 }}>
            Switch between Clerk organizations where you have admin access.
          </p>
        </div>
        <label className="field" style={{ minWidth: 280, margin: 0 }}>
          <span>Current organization</span>
          <select
            value={selectedOrganizationId || ''}
            disabled={pendingOrganizationId !== null}
            onChange={(event) => {
              void handleChange(event.target.value)
            }}
          >
            {memberships.map((membership) => (
              <option key={membership.organizationId} value={membership.organizationId}>
                {membership.organizationName}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  )
}
