import { describe, expect, it } from 'vitest'

import type { SmsActivationRecord, SmsCountryPrice, SmsProviderConfig } from '@/api/sms'

import {
  type ActiveSmsActivation,
  addActivation,
  filterAndSortCountries,
  getActiveSmsProvider,
  hasInsufficientBalance,
  isAtConcurrentCap,
  patchActivation,
  rehydrateFromHistory,
  removeActivation,
} from './utils'

function makeActivation(id: string, status = 'pending'): ActiveSmsActivation {
  return {
    activation_id: id,
    phone_number: `+1${id}`,
    cost: '0.50',
    status,
    code: '',
    provider_id: 1,
    service: 'go',
  }
}

function makeHistoryRecord(id: string, providerId: number | null = 1): SmsActivationRecord {
  return {
    id: Number(id) || 0,
    activation_id: id,
    provider_id: providerId,
    phone_number: `+1${id}`,
    service: 'go',
    country: 1,
    country_name: 'United States',
    operator: '',
    cost: '0.50',
    sms_code: '',
    sms_text: '',
    status: 'pending',
    account_id: null,
    account_email: '',
    notes: '',
    created_at: '',
    updated_at: '',
  }
}

const providers: SmsProviderConfig[] = [
  { id: 1, name: 'a', provider_type: 'herosms', api_key: 'x', default_country: 2, default_service: 'go', balance: '1', notes: '', created_at: '', updated_at: '' },
  { id: 2, name: 'b', provider_type: 'smsbus', api_key: 'y', default_country: 3, default_service: 'tg', balance: '2', notes: '', created_at: '', updated_at: '' },
]

const countries: SmsCountryPrice[] = [
  { country_id: 1, country_name: 'United States', phone_code: '+1', price: '1.50', count: 20 },
  { country_id: 2, country_name: 'Japan', phone_code: '+81', price: '0.80', count: 5 },
  { country_id: 3, country_name: 'France', phone_code: '+33', price: '2.00', count: 0 },
]

describe('sms utils', () => {
  it('prefers configured default provider', () => {
    expect(getActiveSmsProvider(providers, 2)?.name).toBe('b')
  })

  it('falls back to first provider', () => {
    expect(getActiveSmsProvider(providers, null)?.name).toBe('a')
  })

  it('filters and sorts countries by count', () => {
    expect(filterAndSortCountries(countries, '', 'count').map((country) => country.country_name)).toEqual([
      'United States',
      'Japan',
    ])
  })

  it('filters and sorts countries by price and search', () => {
    expect(filterAndSortCountries(countries, '81', 'price').map((country) => country.country_name)).toEqual([
      'Japan',
    ])
  })
})

describe('sms activations registry', () => {
  it('addActivation 同 id 二次添加保持原对象（幂等）', () => {
    const initial = { a: makeActivation('a', 'code_received') }
    const next = addActivation(initial, makeActivation('a', 'pending'))
    expect(next).toBe(initial)
    expect(next.a.status).toBe('code_received')
  })

  it('addActivation 新 id 追加并保持其他 entry 不动', () => {
    const initial = { a: makeActivation('a') }
    const next = addActivation(initial, makeActivation('b'))
    expect(Object.keys(next).sort()).toEqual(['a', 'b'])
    expect(next.a).toBe(initial.a)
  })

  it('patchActivation id 不存在时返回同一引用', () => {
    const initial = { a: makeActivation('a') }
    const next = patchActivation(initial, 'missing', { status: 'finished' })
    expect(next).toBe(initial)
  })

  it('patchActivation 局部更新只动目标 entry', () => {
    const initial = { a: makeActivation('a'), b: makeActivation('b') }
    const next = patchActivation(initial, 'a', { status: 'code_received', code: '1234' })
    expect(next).not.toBe(initial)
    expect(next.a.status).toBe('code_received')
    expect(next.a.code).toBe('1234')
    expect(next.b).toBe(initial.b)
  })

  it('removeActivation id 不存在时返回同一引用', () => {
    const initial = { a: makeActivation('a') }
    const next = removeActivation(initial, 'missing')
    expect(next).toBe(initial)
  })

  it('removeActivation 移除存在的 id', () => {
    const initial = { a: makeActivation('a'), b: makeActivation('b') }
    const next = removeActivation(initial, 'a')
    expect(Object.keys(next)).toEqual(['b'])
  })

  it('rehydrateFromHistory 跳过已存在的 id', () => {
    const initial = { a: makeActivation('a', 'code_received') }
    const next = rehydrateFromHistory(initial, [makeHistoryRecord('a'), makeHistoryRecord('b')], 1)
    expect(next.a.status).toBe('code_received')
    expect(next.b.status).toBe('pending')
  })

  it('rehydrateFromHistory 全部已存在时返回同一引用', () => {
    const initial = { a: makeActivation('a') }
    const next = rehydrateFromHistory(initial, [makeHistoryRecord('a')], 1)
    expect(next).toBe(initial)
  })

  it('rehydrateFromHistory 用 fallbackProviderId 兜底', () => {
    const next = rehydrateFromHistory({}, [makeHistoryRecord('a', null)], 99)
    expect(next.a.provider_id).toBe(99)
  })

  it('isAtConcurrentCap 只数 pending 状态', () => {
    const state = {
      a: makeActivation('a', 'pending'),
      b: makeActivation('b', 'code_received'),
      c: makeActivation('c', 'finished'),
      d: makeActivation('d', 'pending'),
    }
    expect(isAtConcurrentCap(state, 2)).toBe(true)
    expect(isAtConcurrentCap(state, 3)).toBe(false)
    expect(isAtConcurrentCap({}, 1)).toBe(false)
  })

  it('hasInsufficientBalance 边界处理', () => {
    expect(hasInsufficientBalance('0.5', '1.0')).toBe(true)
    expect(hasInsufficientBalance('1.0', '0.5')).toBe(false)
    expect(hasInsufficientBalance('1.0', '1.0')).toBe(false)
    expect(hasInsufficientBalance(undefined, '1.0')).toBe(false)
    expect(hasInsufficientBalance('1.0', undefined)).toBe(false)
    expect(hasInsufficientBalance('', '1.0')).toBe(false)
    expect(hasInsufficientBalance('abc', '1.0')).toBe(false)
    expect(hasInsufficientBalance('1.0', 'xyz')).toBe(false)
  })
})
