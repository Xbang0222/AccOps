import { describe, expect, it } from 'vitest'

import type { Group } from '@/types'
import {
  createAccountOpState,
  updateAccountOpState,
} from '@/types/automation'
import {
  getGroupMemberOptions,
  getSortedGroupAccounts,
  parseEmailInput,
} from './utils'

describe('group-detail utils', () => {
  it('parses pasted emails and removes duplicates', () => {
    expect(
      parseEmailInput(' foo@gmail.com,bar@gmail.com\nfoo@gmail.com ; baz@gmail.com '),
    ).toEqual(['foo@gmail.com', 'bar@gmail.com', 'baz@gmail.com'])
  })

  it('returns empty array for single incomplete token', () => {
    expect(parseEmailInput('foo@gmail.com')).toEqual([])
    expect(parseEmailInput('foo')).toEqual([])
  })

  it('builds member options for the active account family', () => {
    const group: Group = {
      id: 1,
      name: 'test',
      accounts: [
        { id: 1, email: 'owner@gmail.com', password: '', family_group_id: 10 },
        { id: 2, email: 'member1@gmail.com', password: '', family_group_id: 10 },
        { id: 3, email: 'member2@gmail.com', password: '', family_group_id: 10 },
        { id: 4, email: 'other@gmail.com', password: '', family_group_id: 11 },
      ],
    }

    expect(getGroupMemberOptions(group, 1)).toEqual([
      { label: 'member1@gmail.com', value: 'member1@gmail.com' },
      { label: 'member2@gmail.com', value: 'member2@gmail.com' },
    ])
  })

  it('sorts main account first and pending members last', () => {
    const group: Group = {
      id: 1,
      name: 'test',
      main_account_id: 2,
      accounts: [
        { id: 1, email: 'pending@gmail.com', password: '', is_family_pending: true },
        { id: 2, email: 'owner@gmail.com', password: '' },
        { id: 3, email: 'member@gmail.com', password: '' },
      ],
    }

    expect(getSortedGroupAccounts(group).map((account) => account.email)).toEqual([
      'owner@gmail.com',
      'member@gmail.com',
      'pending@gmail.com',
    ])
  })

  it('updates account operation state incrementally', () => {
    const initial = { 1: createAccountOpState('login') }
    const next = updateAccountOpState(initial, 1, { resultMsg: 'done', resultSuccess: true })

    expect(next[1]).toEqual({
      runningOpKey: 'login',
      steps: [],
      resultMsg: 'done',
      resultSuccess: true,
    })
  })
})
