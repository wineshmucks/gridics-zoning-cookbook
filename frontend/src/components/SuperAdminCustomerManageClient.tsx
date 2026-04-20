'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useActionState, useEffect, useState } from 'react'

import {
  deleteCustomerAction,
  inviteClientAdminAction,
  removeCustomerLogoAction,
  removeClientAdminAction,
  saveCustomerGeneralSettingsAction,
  setCustomerActiveStateAction,
  type CustomerMutationState,
  type InviteAdminState,
  type RemoveAdminState,
} from '../app/admin/actions'
import { buildApiUrl } from '../lib/api'
import { CompactSummaryHeader, FormSection } from './AdminSurfacePrimitives'
import { BuildingLogo } from './BuildingLogo'

type AdminMember = {
  userId: string
  identifier: string
  name: string
  role: string
}

type PendingInvite = {
  id: string
  emailAddress: string
  role: string
  status: string
}

type SelectedCustomer = {
  id: string
  clientId: string
  name: string
  departmentName: string | null
  pathAlias: string | null
  market: string | null
  logoPath: string | null
  logoSource: 'jurisdiction' | null
  clerkOrganizationId: string
  slug: string | null
  customerId: string | null
  isActive: boolean | null
}

const initialInviteState: InviteAdminState = {
  error: null,
  success: null,
}

const initialRemoveState: RemoveAdminState = {
  error: null,
  success: null,
}

const initialCustomerMutationState: CustomerMutationState = {
  error: null,
  success: null,
}

export function SuperAdminCustomerManageClient({
  customer,
  adminMembers,
  pendingInvites,
  marketOptions,
}: {
  customer: SelectedCustomer
  adminMembers: AdminMember[]
  pendingInvites: PendingInvite[]
  marketOptions: string[]
}) {
  const [inviteState, inviteAction, invitePending] = useActionState(inviteClientAdminAction, initialInviteState)
  const [removeState, removeAction, removePending] = useActionState(removeClientAdminAction, initialRemoveState)
  const [statusState, statusAction, statusPending] = useActionState(
    setCustomerActiveStateAction,
    initialCustomerMutationState,
  )
  const [generalState, generalAction, generalPending] = useActionState(
    saveCustomerGeneralSettingsAction,
    initialCustomerMutationState,
  )
  const [removeLogoState, removeLogoAction, removeLogoPending] = useActionState(
    removeCustomerLogoAction,
    initialCustomerMutationState,
  )
  const [deleteState, deleteAction, deletePending] = useActionState(
    deleteCustomerAction,
    initialCustomerMutationState,
  )
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeSection = searchParams.get('section') === 'admin-users' ? 'admin-users' : 'general'
  const [selectedLogoPreviewUrl, setSelectedLogoPreviewUrl] = useState<string | null>(null)

  useEffect(() => {
    if (generalState.redirectPath) {
      router.push(generalState.redirectPath)
      router.refresh()
      return
    }

    if (
      !inviteState.success &&
      !removeState.success &&
      !statusState.success &&
      !generalState.success &&
      !removeLogoState.success
    ) {
      return
    }

    router.refresh()
  }, [
    generalState.redirectPath,
    generalState.success,
    inviteState.success,
    removeLogoState.success,
    removeState.success,
    router,
    statusState.success,
  ])

  useEffect(() => {
    return () => {
      if (selectedLogoPreviewUrl) {
        URL.revokeObjectURL(selectedLogoPreviewUrl)
      }
    }
  }, [selectedLogoPreviewUrl])

  useEffect(() => {
    if (!deleteState.success) {
      return
    }

    router.push('/super-admin')
    router.refresh()
  }, [deleteState.success, router])

  const statusLabel =
    customer.isActive === true ? 'Active' : customer.isActive === false ? 'Inactive' : 'Unprovisioned'
  const statusTone =
    customer.isActive === true ? 'is-active' : customer.isActive === false ? 'is-inactive' : 'is-draft'
  const currentLogoUrl = customer.logoPath ? buildApiUrl(customer.logoPath) : null
  const previewLogoUrl = selectedLogoPreviewUrl || currentLogoUrl
  const summaryTitle = activeSection === 'admin-users' ? 'Admin Users' : 'General'
  const summaryIcon = activeSection === 'admin-users' ? 'admin-users' : 'jurisdiction-details'
  const hasJurisdictionLogo = customer.logoSource === 'jurisdiction' && Boolean(customer.logoPath)

  return (
    <div className="panel-stack super-admin-panel-stack">
      <section className="super-admin-summary-card">
        <CompactSummaryHeader
          title={summaryTitle}
          icon={summaryIcon}
          status={<span className={`status-pill ${statusTone}`}>{statusLabel}</span>}
          meta={
            <div className="compact-summary-meta-list">
              <div>
                <span>Admins</span>
                <strong>{adminMembers.length}</strong>
              </div>
              <div>
                <span>Invites</span>
                <strong>{pendingInvites.length}</strong>
              </div>
            </div>
          }
        />
      </section>

      {activeSection === 'general' ? (
        <section className="super-admin-content-panel">
          <form id="customer-general-form" action={generalAction} className="admin-form admin-form-compact super-admin-general-form">
            <input type="hidden" name="organizationId" value={customer.id} />

            <div className="admin-form-grid admin-form-grid-2">
              <label className="field">
                <span>Organization ID</span>
                <input name="clientId" defaultValue={customer.clientId} required />
              </label>
              <label className="field">
                <span>Jurisdiction name</span>
                <input name="cityName" defaultValue={customer.name} required />
              </label>
              <label className="field">
                <span>Department name</span>
                <input
                  name="departmentName"
                  defaultValue={customer.departmentName || 'Planning & Zoning Department'}
                  required
                />
              </label>
              <label className="field">
                <span>Clerk organization ID</span>
                <input name="clerkOrganizationId" defaultValue={customer.clerkOrganizationId} required />
              </label>
              <label className="field">
                <span>Clerk slug</span>
                <input name="clerkSlug" defaultValue={customer.slug || ''} placeholder="miami-planning" />
              </label>
              <label className="field">
                <span>Public path alias</span>
                <input name="pathAlias" defaultValue={customer.pathAlias || ''} placeholder="/us/fl/miami" />
              </label>
              <label className="field">
                <span>Market served</span>
                <input
                  name="market"
                  defaultValue={customer.market || ''}
                  list="market-options"
                  placeholder="Miami, FL"
                  required
                />
                <datalist id="market-options">
                  {marketOptions.map((market) => (
                    <option key={market} value={market} />
                  ))}
                </datalist>
                <small>Start typing to find the Gridics market this jurisdiction belongs to.</small>
              </label>
            </div>

            <FormSection title="Logo" icon="assistant-setup">
              <div className="settings-logo-stack">
                <label className="field settings-logo-upload-field">
                  <span>Upload logo</span>
                  <input
                    name="logoFile"
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    onChange={(event) => {
                      const nextFile = event.target.files?.[0] || null
                      setSelectedLogoPreviewUrl((currentValue) => {
                        if (currentValue) {
                          URL.revokeObjectURL(currentValue)
                        }
                        return nextFile ? URL.createObjectURL(nextFile) : null
                      })
                    }}
                  />
                </label>
                <div className="settings-logo-preview">
                  {previewLogoUrl ? (
                    <div className="settings-logo-preview-inner">
                      <BuildingLogo logoUrl={previewLogoUrl} alt={`${customer.name} logo preview`} />
                      <div className="settings-logo-preview-meta">
                        <strong>{hasJurisdictionLogo ? 'Jurisdiction logo' : 'Uploaded logo'}</strong>
                        <span>{customer.logoPath || 'No saved path'}</span>
                      </div>
                    </div>
                  ) : (
                    <span>No logo selected.</span>
                  )}
                </div>
                {customer.logoPath ? (
                  <div className="settings-logo-actions">
                    <input type="hidden" name="customerName" value={customer.name} />
                    <button
                      className="button button-link"
                      type="submit"
                      formAction={removeLogoAction}
                      disabled={removeLogoPending}
                    >
                      {removeLogoPending ? 'Removing…' : 'Remove logo'}
                    </button>
                  </div>
                ) : null}
              </div>
            </FormSection>

            {generalState.error ? <div className="status-banner status-banner-error">{generalState.error}</div> : null}
            {generalState.success ? <div className="status-banner status-banner-success">{generalState.success}</div> : null}
            {removeLogoState.error ? <div className="status-banner status-banner-error">{removeLogoState.error}</div> : null}
            {removeLogoState.success ? <div className="status-banner status-banner-success">{removeLogoState.success}</div> : null}
          </form>

          <FormSection title="Status" icon="jurisdiction-details">
            <form action={statusAction} className="admin-form admin-form-compact super-admin-status-form">
              <input type="hidden" name="organizationId" value={customer.id} />
              <input type="hidden" name="customerName" value={customer.name} />
              <div className="super-admin-status-inline">
                <div className="admin-inline-title">Public availability</div>
                <label className="field field-inline super-admin-status-field">
                  <select aria-label="Status" name="isActive" defaultValue={customer.isActive === false ? 'false' : 'true'}>
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </label>
              </div>
              <div className="admin-form-actions admin-form-actions-end">
                <button className="button secondary" type="submit" disabled={statusPending}>
                  {statusPending ? 'Updating…' : 'Update Status'}
                </button>
              </div>
            </form>
            {statusState.error ? <div className="status-banner status-banner-error">{statusState.error}</div> : null}
            {statusState.success ? <div className="status-banner status-banner-success">{statusState.success}</div> : null}
          </FormSection>

          <FormSection title="Danger Zone" className="is-danger">
            <div className="super-admin-danger-zone">
              <div className="admin-inline-title">Delete jurisdiction</div>
              <form action={deleteAction} className="super-admin-danger-zone-actions">
                <input type="hidden" name="organizationId" value={customer.id} />
                <input type="hidden" name="customerName" value={customer.name} />
                <button className="button secondary super-admin-danger-button" type="submit" disabled={deletePending}>
                  {deletePending ? 'Deleting…' : 'Delete'}
                </button>
              </form>
            </div>
            {deleteState.error ? <div className="status-banner status-banner-error">{deleteState.error}</div> : null}
            {deleteState.success ? <div className="status-banner status-banner-success">{deleteState.success}</div> : null}
          </FormSection>

          <div className="admin-form-actions admin-form-actions-end super-admin-form-footer">
            <button className="button" type="submit" form="customer-general-form" disabled={generalPending}>
              {generalPending ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </section>
      ) : null}

      {activeSection === 'admin-users' ? (
        <section className="super-admin-content-panel">
          <FormSection title="Admin Users" icon="admin-users" hideHeader>
            <div className="admin-form-shell">
              <form action={inviteAction} className="admin-form admin-form-compact">
                <input type="hidden" name="organizationId" value={customer.id} />
                <label className="field field-full">
                  <span>Email address</span>
                  <input name="emailAddress" type="email" placeholder="planning-admin@example.gov" required />
                </label>
                <div className="admin-form-actions">
                  <button className="button" type="submit" disabled={invitePending}>
                    {invitePending ? 'Sending…' : 'Send Admin Invite'}
                  </button>
                </div>
                {inviteState.error ? <div className="status-banner status-banner-error">{inviteState.error}</div> : null}
                {inviteState.success ? <div className="status-banner status-banner-success">{inviteState.success}</div> : null}
              </form>

              <div className="admin-form-divider" />

              <div className="admin-form-shell">
                <div className="admin-inline-title">Assigned admins</div>
                {adminMembers.length ? (
                  <div className="admin-member-list">
                    {adminMembers.map((member) => (
                      <div key={member.userId} className="admin-member-row">
                        <div>
                          <div className="admin-inline-title">{member.name}</div>
                          <div className="admin-form-note">{member.identifier} · {member.role}</div>
                        </div>
                        <form action={removeAction}>
                          <input type="hidden" name="organizationId" value={customer.id} />
                          <input type="hidden" name="userId" value={member.userId} />
                          <button className="button secondary" type="submit" disabled={removePending}>
                            Remove
                          </button>
                        </form>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="admin-form-note">No admins.</div>
                )}
                {removeState.error ? <div className="status-banner status-banner-error">{removeState.error}</div> : null}
                {removeState.success ? <div className="status-banner status-banner-success">{removeState.success}</div> : null}
              </div>

              <div className="admin-form-divider" />

              <div className="admin-form-shell">
                <div className="admin-inline-title">Pending invites</div>
                {pendingInvites.length ? (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Role</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pendingInvites.map((invite) => (
                        <tr key={invite.id}>
                          <td>{invite.emailAddress}</td>
                          <td>{invite.role}</td>
                          <td>{invite.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="admin-form-note">No invites.</div>
                )}
              </div>
            </div>
          </FormSection>
        </section>
      ) : null}
    </div>
  )
}
