'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useActionState, useEffect } from 'react'

import {
  deleteCustomerAction,
  inviteClientAdminAction,
  removeClientAdminAction,
  setCustomerInactiveAction,
  type CustomerMutationState,
  type InviteAdminState,
  type RemoveAdminState,
} from '../app/admin/actions'
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
  name: string
  slug: string | null
  customerId: string | null
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
  const [inactiveState, inactiveAction, inactivePending] = useActionState(
    setCustomerInactiveAction,
    initialCustomerMutationState,
  )
  const [deleteState, deleteAction, deletePending] = useActionState(
    deleteCustomerAction,
    initialCustomerMutationState,
  )
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeSection = searchParams.get('section') === 'admin-users' ? 'admin-users' : 'general'

  useEffect(() => {
    if (!inviteState.success && !removeState.success && !inactiveState.success) {
      return
    }

    router.refresh()
  }, [inactiveState.success, inviteState.success, removeState.success, router])

  useEffect(() => {
    if (!deleteState.success) {
      return
    }

    router.push('/super-admin')
    router.refresh()
  }, [deleteState.success, router])

  return (
    <div className="panel-stack">
      {activeSection === 'general' ? (
        <div className="panel-stack">
          <section className="card">
            <SuperAdminCustomerHeader
              icon="jurisdiction-details"
              eyebrow="Jurisdiction Details"
              title={customer.name}
              description="Review the jurisdiction profile, lifecycle controls, and account context."
            />
          </section>

          <div className="admin-list">
            <div className="admin-list-heading">General</div>
            <div style={{ color: 'var(--muted)' }}>
              Jurisdiction details and lifecycle controls for {customer.name}.
            </div>
            <dl className="detail-list">
              <div>
                <dt>Jurisdiction name</dt>
                <dd>{customer.name}</dd>
              </div>
              <div>
                <dt>Organization ID</dt>
                <dd>{customer.customerId || 'Organization ID unavailable'}</dd>
              </div>
              <div>
                <dt>Slug</dt>
                <dd>{customer.slug || 'No slug configured'}</dd>
              </div>
              <div>
                <dt>Admin users</dt>
                <dd>{adminMembers.length}</dd>
              </div>
              <div>
                <dt>Pending invites</dt>
                <dd>{pendingInvites.length}</dd>
              </div>
            </dl>
          </div>

          <div className="admin-list">
            <div className="admin-list-heading">Jurisdiction controls</div>
            <div className="panel-stack">
              <form action={inactiveAction} className="admin-action-row">
                <input type="hidden" name="organizationId" value={customer.id} />
                <input type="hidden" name="customerName" value={customer.name} />
                <div>
                  <div style={{ fontWeight: 700 }}>Set jurisdiction inactive</div>
                  <div style={{ color: 'var(--muted)' }}>
                    Disable tenant resolution for this jurisdiction without removing the Clerk organization.
                  </div>
                </div>
                <button className="button secondary" type="submit" disabled={inactivePending}>
                  {inactivePending ? 'Updating…' : 'Set Inactive'}
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
            {inactiveState.error ? (
              <div className="status-banner status-banner-error">{inactiveState.error}</div>
            ) : null}
            {inactiveState.success ? (
              <div className="status-banner status-banner-success">{inactiveState.success}</div>
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
