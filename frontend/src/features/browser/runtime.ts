import type { BrowserProfile } from '@/api/browser'

export interface BrowserRuntimeState {
  profileMap: Record<number, number>
  runningAccountIds: Set<number>
}

export function buildBrowserRuntimeState(profiles: BrowserProfile[]): BrowserRuntimeState {
  const profileMap: Record<number, number> = {}
  const runningAccountIds = new Set<number>()

  for (const profile of profiles) {
    if (!profile.account_id) {
      continue
    }

    profileMap[profile.account_id] = profile.id
    if (profile.status === 'running') {
      runningAccountIds.add(profile.account_id)
    }
  }

  return { profileMap, runningAccountIds }
}

export function updateLoadingAccountSet(
  previous: Set<number>,
  accountId: number,
  loading: boolean,
): Set<number> {
  const next = new Set(previous)
  if (loading) {
    next.add(accountId)
  } else {
    next.delete(accountId)
  }

  return next
}

export function updateRunningAccountSet(
  previous: Set<number>,
  accountId: number,
  running: boolean,
): Set<number> {
  const next = new Set(previous)
  if (running) {
    next.add(accountId)
  } else {
    next.delete(accountId)
  }

  return next
}
