export type AutomationOperationRole = 'any' | 'owner' | 'member' | 'no-group'

export interface AutomationOperationField {
  name: string
  placeholder: string
}

export interface AutomationOperationDefinition {
  key: 'family-discover' | 'family-create' | 'family-invite' | 'family-accept' | 'family-remove' | 'family-leave' | 'replace'
  label: string
  color: string
  needBrowser: boolean
  fields?: AutomationOperationField[]
  danger?: boolean
  role?: AutomationOperationRole
}

export interface AutomationAccountState {
  family_group_id?: number | null
  is_family_owner?: boolean
  family_member_count?: number | null
}

export const FAMILY_AUTOMATION_OPERATIONS: AutomationOperationDefinition[] = [
  {
    key: 'family-discover',
    label: '同步',
    color: '#1677ff',
    needBrowser: false,
    role: 'owner',
  },
  {
    key: 'family-create',
    label: '建组',
    color: '#722ed1',
    needBrowser: true,
    role: 'no-group',
  },
  {
    key: 'family-invite',
    label: '邀请',
    color: '#13c2c2',
    needBrowser: true,
    fields: [{ name: 'invite_email', placeholder: '被邀请人邮箱（多个用逗号或换行分隔）' }],
    role: 'owner',
  },
  {
    key: 'family-accept',
    label: '接受',
    color: '#52c41a',
    needBrowser: true,
    role: 'no-group',
  },
  {
    key: 'family-remove',
    label: '移除',
    color: '#ff4d4f',
    needBrowser: true,
    fields: [{ name: 'member_email', placeholder: '要移除的成员邮箱（多个用逗号或换行分隔）' }],
    danger: true,
    role: 'owner',
  },
  {
    key: 'family-leave',
    label: '退组',
    color: '#fa8c16',
    needBrowser: true,
    danger: true,
    role: 'member',
  },
  {
    key: 'replace',
    label: '替换',
    color: '#722ed1',
    needBrowser: true,
    fields: [
      { name: 'old_email', placeholder: '旧成员邮箱 (将被移除)' },
      { name: 'new_email', placeholder: '新成员邮箱 (将被邀请)' },
    ],
    role: 'owner',
  },
]

export function getVisibleAutomationOperations(
  account: AutomationAccountState,
): AutomationOperationDefinition[] {
  const hasGroup = Boolean(account.family_group_id)
  const isOwner = Boolean(account.is_family_owner)
  const isMember = hasGroup && !isOwner
  const isFull = (account.family_member_count ?? 0) >= 6

  return FAMILY_AUTOMATION_OPERATIONS.filter((operation) => {
    if (!operation.role || operation.role === 'any') {
      return true
    }

    if (operation.role === 'owner') {
      if (!isOwner) {
        return false
      }

      return !(isFull && operation.key === 'family-invite')
    }

    if (operation.role === 'member') {
      return isMember
    }

    if (operation.role === 'no-group') {
      return !hasGroup
    }

    return true
  })
}
