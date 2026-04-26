export const ABNORMAL_STATUSES = ['unusable', 'retired'] as const

export type AccountStatus = '' | 'unusable' | 'retired'

export function isAbnormalStatus(status: AccountStatus | undefined | null): boolean {
  return status ? (ABNORMAL_STATUSES as readonly string[]).includes(status) : false
}
