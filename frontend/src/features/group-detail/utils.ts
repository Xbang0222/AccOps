import type { AutomationOperationDefinition } from '@/features/automation/operationMeta'
import type { StepMsg } from '@/hooks/useAutomationWs'
import type { Account, Group } from '@/types'

export const FAMILY_GROUP_CAPACITY = 6
export const FAMILY_GROUP_MAX_SUB_MEMBERS = 5

export interface AccountOpState {
  runningOpKey: string | null
  steps: StepMsg[]
  resultMsg: string
  resultSuccess: boolean | null
}

export interface GroupMemberOption {
  label: string
  value: string
}

export function createAccountOpState(runningOpKey: string | null = null): AccountOpState {
  return {
    runningOpKey,
    steps: [],
    resultMsg: '',
    resultSuccess: null,
  }
}

export function updateAccountOpState(
  previous: Record<number, AccountOpState>,
  accountId: number,
  patch: Partial<AccountOpState>,
): Record<number, AccountOpState> {
  return {
    ...previous,
    [accountId]: {
      ...(previous[accountId] ?? createAccountOpState()),
      ...patch,
    },
  }
}

export function parseEmailInput(value: string): string[] {
  if (!/[,;\n\r\s]/.test(value)) {
    return []
  }

  return Array.from(
    new Set(
      value
        .split(/[,;\n\r\s]+/)
        .map((email) => email.trim())
        .filter((email) => email.includes('@')),
    ),
  )
}

export function getGroupMemberOptions(
  group: Group | null,
  activeAccountId: number | null,
): GroupMemberOption[] {
  if (!group || activeAccountId === null) {
    return []
  }

  const accounts = group.accounts ?? []
  const activeAccount = accounts.find((account) => account.id === activeAccountId)
  if (!activeAccount) {
    return []
  }

  return accounts
    .filter(
      (account) =>
        account.id !== activeAccountId &&
        account.family_group_id === activeAccount.family_group_id,
    )
    .map((account) => ({
      label: account.email,
      value: account.email,
    }))
}

export function getSortedGroupAccounts(group: Group | null): Account[] {
  if (!group) {
    return []
  }

  const accounts = group.accounts ?? []
  const mainAccount = accounts.find((account) => account.id === group.main_account_id)
  const members = accounts
    .filter((account) => account.id !== group.main_account_id)
    .sort(
      (left, right) =>
        Number(Boolean(left.is_family_pending)) - Number(Boolean(right.is_family_pending)),
    )

  return mainAccount ? [mainAccount, ...members] : members
}

export function isOperationFieldModal(
  operation: AutomationOperationDefinition | null,
): operation is AutomationOperationDefinition {
  return Boolean(operation)
}
