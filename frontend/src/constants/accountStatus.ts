export const ABNORMAL_POOL_STATUSES = ['unusable', 'retired'] as const

export type PoolStatus = '' | 'unusable' | 'retired'

export function isAbnormalPoolStatus(status: PoolStatus | undefined | null): boolean {
  return status ? (ABNORMAL_POOL_STATUSES as readonly string[]).includes(status) : false
}
