import type { SmsCountryPrice } from '@/api/sms'

export const PROVIDER_TYPES = [
  { value: 'herosms', label: 'HeroSMS' },
  { value: 'smsbus', label: 'SMS-Bus' },
]

/** 同时进行中的接码任务上限（成本安全闸） */
export const MAX_CONCURRENT_BUY = 5

/** 单一国家「购买」按钮去抖时间，避免双击重复扣费（毫秒） */
export const BUY_BUTTON_DEBOUNCE_MS = 1500

/** 接码状态轮询间隔（毫秒） */
export const SMS_POLL_INTERVAL_MS = 5000

/** 页面加载时尝试恢复的待处理记录上限 */
export const REHYDRATE_PENDING_LIMIT = 20

export const STATUS_MAP: Record<string, { color: string; label: string }> = {
  pending: { color: 'processing', label: '等待验证码' },
  code_received: { color: 'success', label: '已收到' },
  finished: { color: 'default', label: '已完成' },
  cancelled: { color: 'warning', label: '已取消' },
  error: { color: 'error', label: '错误' },
}

export interface SmsCountryOption {
  value: number | string
  label: string
}

export type SmsCountrySortBy = 'count' | 'price'

export function toCountryOptions(countries: SmsCountryPrice[]): SmsCountryOption[] {
  return countries
    .filter((country) => country.count > 0)
    .map((country) => ({
      value: country.country_id,
      label: `${country.country_name}${country.phone_code ? ` (${country.phone_code})` : ''} - $${country.price} (${country.count})`,
    }))
}
