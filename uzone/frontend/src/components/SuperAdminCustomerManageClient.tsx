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
import { SuperAdminCustomerHeader } from './SuperAdminCustomerIcons'

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
  logoPath: string | null
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
}: {
  customer: SelectedCustomer
  adminMembers: AdminMember[]
  pendingInvites: PendingInvite[]
}) {
  const [inviteState, inviteAction, invitePending] = useActionState(
    inviteClientAdminAction,
    initialInviteState,
  )
  const [removeState, removeAction, removePending] = useActionState(
    removeClientAdminAction,
    initialRemoveState,
  )
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

  return (
    <div className="panel-stack">
      {activeSection === 'general' ? (
        <div className="panel-stack">
          <section className="card">
            <SuperAdminCustomerHeader
              icon="jurisdiction-details"
              eyebrow="Jurisdiction Details"
              title={customer.name}
              description="Review the jurisdiction profile, account context, and whether this jurisdiction is live for public tenant resolution."
            />
            <div style={{ marginTop: 14 }}>
              <span className={`status-pill ${statusTone}`}>{statusLabel}</span>
            </div>
          </section>

          <div className="admin-list">
            <div className="admin-list-heading">General</div>
            <div style={{ color: 'var(--muted)' }}>
              Jurisdiction details and lifecycle controls for {customer.name}.
            </div>
            <form action={generalAction} className="admin-form">
              <input type="hidden" name="organizationId" value={customer.id} />
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
                <span>Jurisdiction logo</span>
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
              {previewLogoUrl ? (
                <div className="jurisdiction-logo-preview">
                  <img src={previewLogoUrl} alt={`${customer.name} logo preview`} className="jurisdiction-logo-preview-image" />
                  <div style={{ color: 'var(--muted)' }}>
                    {selectedLogoPreviewUrl ? 'New logo preview selected.' : 'Current uploaded logo.'}{' '}
                    {currentLogoUrl ? (
                      <a href={currentLogoUrl} target="_blank" rel="noreferrer">
                        Open full image
                      </a>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div style={{ color: 'var(--muted)' }}>
                  No jurisdiction logo uploaded yet. The default building icon will be used.
                </div>
              )}
              {customer.logoPath ? (
                <div className="admin-action-row">
                  <input type="hidden" name="customerName" value={customer.name} />
                  <div style={{ color: 'var(--muted)' }}>
                    Remove the uploaded logo and revert the header to the default building icon.
                  </div>
                  <button
                    className="button secondary"
                    type="submit"
                    formAction={removeLogoAction}
                    disabled={removeLogoPending}
                  >
                    {removeLogoPending ? 'Removing…' : 'Remove Logo'}
                  </button>
                </div>
              ) : null}
              <dl className="detail-list">
                <div>
                  <dt>Organization ID</dt>
                  <dd>{customer.clientId || customer.customerId || 'Organization ID unavailable'}</dd>
                </div>
                <div>
                  <dt>Slug</dt>
                  <dd>{customer.slug || 'No slug configured'}</dd>
                </div>
                <div>
                  <dt>Public alias</dt>
                  <dd>{customer.pathAlias || 'No public alias configured'}</dd>
                </div>
                <div>
                  <dt>Admin users</dt>
                  <dd>{adminMembers.length}</dd>
                </div>
                <div>
                  <dt>Pending invites</dt>
                  <dd>{pendingInvites.length}</dd>
                </div>
                <div>
                  <dt>Current status</dt>
                  <dd>
                    <span className={`status-pill ${statusTone}`}>{statusLabel}</span>
                  </dd>
                </div>
              </dl>
              <button className="button" type="submit" disabled={generalPending}>
                {generalPending ? 'Saving…' : 'Save Details'}
              </button>
            </form>
            {generalState.error ? (
              <div className="status-banner status-banner-error">{generalState.error}</div>
            ) : null}
            {generalState.success ? (
              <div className="status-banner status-banner-success">{generalState.success}</div>
            ) : null}
            {removeLogoState.error ? (
              <div className="status-banner status-banner-error">{removeLogoState.error}</div>
            ) : null}
            {removeLogoState.success ? (
              <div className="status-banner status-banner-success">{removeLogoState.success}</div>
            ) : null}
          </div>

          <div className="admin-list">
            <div className="admin-list-heading">Jurisdiction controls</div>
            <div className="panel-stack">
              <form action={statusAction} className="admin-form">
                <input type="hidden" name="organizationId" value={customer.id} />
                <input type="hidden" name="customerName" value={customer.name} />
                <div className="admin-action-row">
                  <div>
                    <div style={{ fontWeight: 700 }}>Public availability</div>
                    <div style={{ color: 'var(--muted)' }}>
                      Active jurisdictions appear in the public selector and resolve tenant configuration. Inactive ones stay in admin but are hidden from the public flow.
                    </div>
                  </div>
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <span>Status</span>
                    <select
                      name="isActive"
                      defaultValue={customer.isActive === false ? 'false' : 'true'}
                    >
                      <option value="true">Active</option>
                      <option value="false">Inactive</option>
                    </select>
                  </label>
                </div>
                <button className="button secondary" type="submit" disabled={statusPending}>
                  {statusPending ? 'Updating…' : 'Save Status'}
                </button>
              </form>

              <form action={deleteAction} className="admin-action-row">
                <input type="hidden" name="organizationId" value={customer.id} />
                <input type="hidden" name="customerName" value={customer.name} />
                <div>
                  <div style={{ fontWeight: 700 }}>Delete jurisdiction</div>
                  <div style={{ color: 'var(--muted)' }}>
                    Remove the Clerk organization and delete its tenant mapping.
                  </div>
                </div>
                <button className="button secondary" type="submit" disabled={deletePending}>
                  {deletePending ? 'Deleting…' : 'Delete'}
                </button>
              </form>
            </div>
            {statusState.error ? (
              <div className="status-banner status-banner-error">{statusState.error}</div>
            ) : null}
            {statusState.success ? (
              <div className="status-banner status-banner-success">{statusState.success}</div>
            ) : null}
            {deleteState.error ? (
              <div className="status-banner status-banner-error">{deleteState.error}</div>
            ) : null}
            {deleteState.success ? (
              <div className="status-banner status-banner-success">{deleteState.success}</div>
            ) : null}
          </div>
        </div>
      ) : null}

      {activeSection === 'admin-users' ? (
        <div className="panel-stack">
          <section className="card">
            <SuperAdminCustomerHeader
              icon="admin-users"
              eyebrow="Admin Users"
              title={customer.name}
              description="Manage admin access, invitations, and active assignments for this jurisdiction."
            />
          </section>

          <div className="admin-list">
            <div className="admin-list-heading">Invite admin user</div>
            <form action={inviteAction} className="admin-form">
              <input type="hidden" name="organizationId" value={customer.id} />
              <label className="field">
                <span>Email address</span>
                <input
                  name="emailAddress"
                  type="email"
                  placeholder="planning-admin@example.gov"
                  required
                />
              </label>
              <button className="button" type="submit" disabled={invitePending}>
                {invitePending ? 'Sending…' : 'Send Admin Invite'}
              </button>
              {inviteState.error ? (
                <div className="status-banner status-banner-error">{inviteState.error}</div>
              ) : null}
              {inviteState.success ? (
                <div className="status-banner status-banner-success">{inviteState.success}</div>
              ) : null}
            </form>
          </div>

          <div className="admin-list">
            <div className="admin-list-heading">Admin users</div>
            {adminMembers.length ? (
              <div className="panel-stack">
                {adminMembers.map((member) => (
                  <div key={member.userId} className="admin-list-item admin-action-row">
                    <div>
                      <div style={{ fontWeight: 700 }}>{member.name}</div>
                      <div style={{ color: 'var(--muted)' }}>
                        {member.identifier} · {member.role}
                      </div>
                    </div>
                    <form action={removeAction}>
                      <input type="hidden" name="organizationId" value={customer.id} />
                      <input type="hidden" name="userId" value={member.userId} />
                      <button className="button secondary" type="submit" disabled={removePending}>
                        Remove Admin
                      </button>
                    </form>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--muted)' }}>No admin users are assigned yet.</div>
            )}
            {removeState.error ? (
              <div className="status-banner status-banner-error">{removeState.error}</div>
            ) : null}
            {removeState.success ? (
              <div className="status-banner status-banner-success">{removeState.success}</div>
            ) : null}
          </div>

          <div className="admin-list">
            <div className="admin-list-heading">Pending admin invites</div>
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
              <div style={{ color: 'var(--muted)' }}>No pending admin invites.</div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
