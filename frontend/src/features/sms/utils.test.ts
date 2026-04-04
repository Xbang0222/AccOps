import { describe, expect, it } from 'vitest'

import type { SmsCountryPrice, SmsProviderConfig } from '@/api/sms'

import { filterAndSortCountries, getActiveSmsProvider } from './utils'

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
