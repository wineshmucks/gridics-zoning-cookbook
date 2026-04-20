'use server'

import { getClerkManagementClient } from '../../lib/clerk'
import {
  buildAssistantDisclaimerScopeKey,
  mergeAcceptedAssistantDisclaimerMetadata,
} from '../../lib/assistant-disclaimer'

type ClerkUserLike = {
  unsafeMetadata?: unknown
}

export async function acceptAssistantDisclaimerAction(scopeId: string) {
  const normalizedScopeId = buildAssistantDisclaimerScopeKey(scopeId)
  if (!normalizedScopeId) {
    return { ok: false as const, persisted: false as const }
  }

  const clerkModule = await import('@clerk/nextjs/server')
  const authState = await clerkModule.auth()
  const userId = typeof authState?.userId === 'string' && authState.userId.trim() ? authState.userId : null

  if (!userId) {
    return { ok: true as const, persisted: false as const }
  }

  const client = await getClerkManagementClient()
  const usersApi = client.users as unknown as {
    getUser: (id: string) => Promise<ClerkUserLike>
    updateUserMetadata?: (
      id: string,
      payload: { unsafeMetadata?: Record<string, unknown>; publicMetadata?: Record<string, unknown> },
    ) => Promise<unknown>
    updateUser?: (
      id: string,
      payload: { unsafeMetadata?: Record<string, unknown>; publicMetadata?: Record<string, unknown> },
    ) => Promise<unknown>
  }

  const user = await usersApi.getUser(userId)
  const mergedUnsafeMetadata = mergeAcceptedAssistantDisclaimerMetadata(
    user?.unsafeMetadata,
    normalizedScopeId,
  )

  if (typeof usersApi.updateUserMetadata === 'function') {
    await usersApi.updateUserMetadata(userId, {
      unsafeMetadata: mergedUnsafeMetadata,
    })
  } else if (typeof usersApi.updateUser === 'function') {
    await usersApi.updateUser(userId, {
      unsafeMetadata: mergedUnsafeMetadata,
    })
  } else {
    return { ok: false as const, persisted: false as const }
  }

  return { ok: true as const, persisted: true as const }
}
