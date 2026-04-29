import type { SmsActivationRecord, SmsCountryPrice, SmsProviderConfig } from '@/api/sms'

import type { SmsCountrySortBy } from './constants'

export interface ActiveSmsActivation {
  activation_id: string
  phone_number: string
  cost: string
  status: string
  code: string
  provider_id: number
  service: string
}

export function getActiveSmsProvider(
  providers: SmsProviderConfig[],
  defaultProviderId: number | null,
): SmsProviderConfig | undefined {
  if (defaultProviderId) {
    return providers.find((provider) => provider.id === defaultProviderId)
  }
  return providers[0]
}

export function filterAndSortCountries(
  countries: SmsCountryPrice[],
  search: string,
  sortBy: SmsCountrySortBy,
): SmsCountryPrice[] {
  const filtered = search
    ? countries.filter(
        (country) =>
          country.country_name.toLowerCase().includes(search.toLowerCase()) ||
          (country.phone_code ?? '').includes(search),
      )
    : countries

  return [...filtered]
    .sort((left, right) =>
      sortBy === 'price'
        ? parseFloat(left.price) - parseFloat(right.price)
        : right.count - left.count,
    )
    .filter((country) => country.count > 0)
}

// ── 接码激活并发管理纯函数 ─────────────────────────

/** 加入新激活；若同 id 已存在则保持原对象（幂等，避免覆盖已收码状态） */
export function addActivation(
  state: Record<string, ActiveSmsActivation>,
  next: ActiveSmsActivation,
): Record<string, ActiveSmsActivation> {
  if (state[next.activation_id]) {
    return state
  }
  return { ...state, [next.activation_id]: next }
}

/** 局部更新激活；id 不存在时返回同一引用 */
export function patchActivation(
  state: Record<string, ActiveSmsActivation>,
  id: string,
  patch: Partial<ActiveSmsActivation>,
): Record<string, ActiveSmsActivation> {
  const existing = state[id]
  if (!existing) {
    return state
  }
  return { ...state, [id]: { ...existing, ...patch } }
}

/** 移除激活；id 不存在时返回同一引用 */
export function removeActivation(
  state: Record<string, ActiveSmsActivation>,
  id: string,
): Record<string, ActiveSmsActivation> {
  if (!state[id]) {
    return state
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { [id]: _omit, ...rest } = state
  return rest
}

/** 用历史记录补齐 active state；已存在的 id 保留原对象 */
export function rehydrateFromHistory(
  state: Record<string, ActiveSmsActivation>,
  records: SmsActivationRecord[],
  fallbackProviderId: number,
): Record<string, ActiveSmsActivation> {
  let next = state
  let mutated = false
  for (const record of records) {
    if (next[record.activation_id]) {
      continue
    }
    if (!mutated) {
      next = { ...state }
      mutated = true
    }
    next[record.activation_id] = {
      activation_id: record.activation_id,
      phone_number: record.phone_number,
      cost: record.cost,
      status: 'pending',
      code: record.sms_code ?? '',
      provider_id: record.provider_id ?? fallbackProviderId,
      service: record.service,
    }
  }
  return next
}

/** 仅计 status === 'pending' 的活动数 */
export function countPending(state: Record<string, ActiveSmsActivation>): number {
  let pending = 0
  for (const value of Object.values(state)) {
    if (value.status === 'pending') {
      pending += 1
    }
  }
  return pending
}

/** 是否已达并发上限（仅计 status === 'pending'） */
export function isAtConcurrentCap(
  state: Record<string, ActiveSmsActivation>,
  cap: number,
): boolean {
  return countPending(state) >= cap
}

/** 余额是否不足以支付预估价格；任一无法解析返回 false（不阻拦） */
export function hasInsufficientBalance(
  balance: string | undefined,
  price: string | undefined,
): boolean {
  if (!balance || !price) {
    return false
  }
  const balanceNum = parseFloat(balance)
  const priceNum = parseFloat(price)
  if (Number.isNaN(balanceNum) || Number.isNaN(priceNum)) {
    return false
  }
  return balanceNum < priceNum
}
