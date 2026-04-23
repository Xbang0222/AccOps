import { describe, expect, it } from 'vitest'

import { getVisibleAutomationOperations } from './operationMeta'

describe('getVisibleAutomationOperations', () => {
  it('只允许未入组账号看到建组和接受邀请', () => {
    const operations = getVisibleAutomationOperations({
      family_group_id: null,
      is_family_owner: false,
      family_member_count: 0,
    })

    expect(operations.map((operation) => operation.key)).toEqual([
      'family-create',
      'family-accept',
    ])
  })

  it('允许管理员看到同步、邀请、移除和换号', () => {
    const operations = getVisibleAutomationOperations({
      family_group_id: 12,
      is_family_owner: true,
      family_member_count: 3,
    })

    expect(operations.map((operation) => operation.key)).toEqual([
      'family-discover',
      'family-invite',
      'family-remove',
      'family-swap',
    ])
  })

  it('在成员已满时隐藏邀请操作', () => {
    const operations = getVisibleAutomationOperations({
      family_group_id: 12,
      is_family_owner: true,
      family_member_count: 6,
    })

    expect(operations.some((operation) => operation.key === 'family-invite')).toBe(false)
  })

  it('普通成员没有可见的自动化操作', () => {
    const operations = getVisibleAutomationOperations({
      family_group_id: 12,
      is_family_owner: false,
      family_member_count: 4,
    })

    expect(operations.map((operation) => operation.key)).toEqual([])
  })
})
