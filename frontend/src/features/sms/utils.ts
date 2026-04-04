import type { SmsCountryPrice, SmsProviderConfig } from '@/api/sms'

import type { SmsCountrySortBy } from './constants'

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
