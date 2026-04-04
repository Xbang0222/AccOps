import { App } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  cancelSmsActivation,
  checkSmsStatus,
  createSmsProvider,
  finishSmsActivation,
  getSettings,
  getSmsBalance,
  getSmsHistory,
  getSmsPricesByService,
  getSmsProviders,
  getSmsServices,
  requestNumber,
  updateSmsProvider,
} from '@/api'
import type { SmsActivationRecord, SmsCountryPrice, SmsProviderConfig } from '@/api/sms'
import { getErrorMessage } from '@/utils/http'

import { PROVIDER_TYPES, toCountryOptions, type SmsCountrySortBy } from './constants'
import { filterAndSortCountries, getActiveSmsProvider } from './utils'

export interface ActiveSmsActivation {
  activation_id: string
  phone_number: string
  cost: string
  status: string
  code: string
  provider_id: number
  service: string
}

export function useSmsPageController() {
  const { message: msg } = App.useApp()
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const [configOpen, setConfigOpen] = useState(false)
  const [configType, setConfigType] = useState('herosms')
  const [configApiKey, setConfigApiKey] = useState('')
  const [configTesting, setConfigTesting] = useState(false)
  const [configTestResult, setConfigTestResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [configSaving, setConfigSaving] = useState(false)
  const [providers, setProviders] = useState<SmsProviderConfig[]>([])
  const [defaultProviderId, setDefaultProviderId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [configCountry, setConfigCountry] = useState<number | string>(2)
  const [configService, setConfigService] = useState('go')
  const [configCountries, setConfigCountries] = useState<{ value: number | string; label: string }[]>([])
  const [configCountryLoading, setConfigCountryLoading] = useState(false)

  const [services, setServices] = useState<{ code: string; name: string }[]>([])
  const [countrySearch, setCountrySearch] = useState('')
  const [countryPrices, setCountryPrices] = useState<SmsCountryPrice[]>([])
  const [countryLoading, setCountryLoading] = useState(false)
  const [countrySortBy, setCountrySortBy] = useState<SmsCountrySortBy>('count')

  const [buyLoading, setBuyLoading] = useState<string | null>(null)
  const [activeActivation, setActiveActivation] = useState<ActiveSmsActivation | null>(null)
  const [polling, setPolling] = useState(false)

  const [history, setHistory] = useState<SmsActivationRecord[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [historyLoading, setHistoryLoading] = useState(false)

  const loadHistory = useCallback(async (page: number) => {
    setHistoryLoading(true)
    try {
      const { data } = await getSmsHistory(page, 15)
      setHistory(data.records)
      setHistoryTotal(data.total)
      setHistoryPage(page)
    } catch {
      // noop
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const loadServices = useCallback(async (providerId: number) => {
    try {
      const { data } = await getSmsServices(providerId)
      setServices(Array.isArray(data) ? data : [])
    } catch {
      // noop
    }
  }, [])

  const loadCountryPrices = useCallback(async (service: string, providerId: number) => {
    setCountryLoading(true)
    try {
      const { data } = await getSmsPricesByService(service, providerId)
      setCountryPrices(Array.isArray(data) ? data : [])
    } catch {
      setCountryPrices([])
    } finally {
      setCountryLoading(false)
    }
  }, [])

  const loadConfigCountries = useCallback(async (service: string, providerId: number) => {
    setConfigCountryLoading(true)
    setConfigCountries([])
    try {
      const { data } = await getSmsPricesByService(service, providerId)
      setConfigCountries(toCountryOptions(Array.isArray(data) ? data : []))
    } catch {
      // noop
    } finally {
      setConfigCountryLoading(false)
    }
  }, [])

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [providersResponse, settingsResponse] = await Promise.all([getSmsProviders(), getSettings()])
      setProviders(providersResponse.data)
      const nextDefaultProviderId = settingsResponse.data.default_sms_provider_id
        ? Number(settingsResponse.data.default_sms_provider_id)
        : null
      setDefaultProviderId(nextDefaultProviderId)

      const activeProvider = getActiveSmsProvider(providersResponse.data, nextDefaultProviderId)
      if (activeProvider?.api_key) {
        void loadServices(activeProvider.id)
        void loadCountryPrices(activeProvider.default_service || 'go', activeProvider.id)
      }
    } catch {
      // noop
    } finally {
      setLoading(false)
    }
  }, [loadCountryPrices, loadServices])

  useEffect(() => {
    void loadAll()
    void loadHistory(1)
    return () => {
      if (pollTimer.current) {
        clearInterval(pollTimer.current)
      }
    }
  }, [loadAll, loadHistory])

  const activeProvider = useMemo(
    () => getActiveSmsProvider(providers, defaultProviderId),
    [defaultProviderId, providers],
  )

  const sortedCountries = useMemo(
    () => filterAndSortCountries(countryPrices, countrySearch, countrySortBy),
    [countryPrices, countrySearch, countrySortBy],
  )

  const openConfig = useCallback(() => {
    const existing = providers.find((provider) => provider.provider_type === configType)
    setConfigApiKey(existing?.api_key || '')
    setConfigCountry(existing?.default_country ?? 2)
    setConfigService(existing?.default_service || 'go')
    setConfigTestResult(null)
    setConfigOpen(true)

    if (existing?.api_key && existing.default_service) {
      void loadConfigCountries(existing.default_service, existing.id)
    } else {
      setConfigCountries([])
    }
  }, [configType, loadConfigCountries, providers])

  const handleConfigTypeChange = useCallback((type: string) => {
    setConfigType(type)
    setConfigTestResult(null)
    const existing = providers.find((provider) => provider.provider_type === type)
    setConfigApiKey(existing?.api_key || '')
    setConfigCountry(existing?.default_country ?? 2)
    setConfigService(existing?.default_service || 'go')
    if (existing?.api_key && existing.default_service) {
      void loadConfigCountries(existing.default_service, existing.id)
    } else {
      setConfigCountries([])
    }
  }, [loadConfigCountries, providers])

  const handleConfigServiceChange = useCallback((service: string) => {
    setConfigService(service)
    const existing = providers.find((provider) => provider.provider_type === configType)
    if (existing?.api_key) {
      void loadConfigCountries(service, existing.id)
    }
  }, [configType, loadConfigCountries, providers])

  const handleTestApiKey = useCallback(async () => {
    if (!configApiKey.trim()) {
      msg.warning('请输入 API Key')
      return
    }

    setConfigTesting(true)
    setConfigTestResult(null)
    try {
      const existing = providers.find((provider) => provider.provider_type === configType)
      const provider = existing
        ? (await updateSmsProvider(existing.id, { api_key: configApiKey })).data
        : (
            await createSmsProvider({
              name: PROVIDER_TYPES.find((item) => item.value === configType)?.label || configType,
              provider_type: configType,
              api_key: configApiKey,
            })
          ).data

      const { data: balanceData } = await getSmsBalance(provider.id)
      setConfigTestResult({ ok: true, msg: `有效，余额: $${balanceData.balance}` })

      const { data: nextProviders } = await getSmsProviders()
      setProviders(nextProviders)
      void loadServices(provider.id)
      void loadConfigCountries(configService, provider.id)
    } catch (error: unknown) {
      setConfigTestResult({ ok: false, msg: getErrorMessage(error, '测试失败') })
    } finally {
      setConfigTesting(false)
    }
  }, [configApiKey, configService, configType, loadConfigCountries, loadServices, msg, providers])

  const handleSaveConfig = useCallback(async () => {
    if (!configApiKey.trim()) {
      msg.warning('请输入 API Key')
      return
    }

    setConfigSaving(true)
    try {
      const existing = providers.find((provider) => provider.provider_type === configType)
      const payload = {
        api_key: configApiKey,
        default_country: Number(configCountry),
        default_service: String(configService),
      }
      if (existing) {
        await updateSmsProvider(existing.id, payload)
      } else {
        await createSmsProvider({
          name: PROVIDER_TYPES.find((item) => item.value === configType)?.label || configType,
          provider_type: configType,
          ...payload,
        })
      }

      msg.success('配置已保存')
      setConfigOpen(false)
      void loadAll()
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '保存失败'))
    } finally {
      setConfigSaving(false)
    }
  }, [configApiKey, configCountry, configService, configType, loadAll, msg, providers])

  const startPolling = useCallback((activationId: string, providerId: number) => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
    }

    setPolling(true)
    pollTimer.current = setInterval(async () => {
      try {
        const { data } = await checkSmsStatus(activationId, providerId)
        if (data.code) {
          setActiveActivation((previous) => previous ? { ...previous, status: 'code_received', code: data.code } : null)
          if (pollTimer.current) {
            clearInterval(pollTimer.current)
          }
          setPolling(false)
          msg.success(`验证码: ${data.code}`)
          void loadHistory(1)
        } else if (data.status === 'CANCEL') {
          setActiveActivation((previous) => previous ? { ...previous, status: 'cancelled' } : null)
          if (pollTimer.current) {
            clearInterval(pollTimer.current)
          }
          setPolling(false)
          void loadHistory(1)
        }
      } catch {
        // noop
      }
    }, 5000)
  }, [loadHistory, msg])

  const handleBuyNumber = useCallback(async (serviceCode: string, countryId: number) => {
    if (!activeProvider) {
      msg.warning('请先配置提供商')
      return
    }

    const loadingKey = `${countryId}`
    setBuyLoading(loadingKey)
    try {
      const { data } = await requestNumber({
        provider_id: activeProvider.id,
        service: serviceCode,
        country: countryId,
      })
      setActiveActivation({
        activation_id: data.activation_id,
        phone_number: data.phone_number,
        cost: data.cost,
        status: 'pending',
        code: '',
        provider_id: activeProvider.id,
        service: serviceCode,
      })
      msg.success(`号码: ${data.phone_number}`)
      startPolling(data.activation_id, activeProvider.id)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '购买失败'))
    } finally {
      setBuyLoading(null)
    }
  }, [activeProvider, msg, startPolling])

  const handleFinish = useCallback(async () => {
    if (!activeActivation) {
      return
    }

    try {
      await finishSmsActivation(activeActivation.activation_id, activeActivation.provider_id)
      setActiveActivation((previous) => previous ? { ...previous, status: 'finished' } : null)
      msg.success('已完成')
      void loadHistory(1)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '失败'))
    }
  }, [activeActivation, loadHistory, msg])

  const handleCancel = useCallback(async () => {
    if (!activeActivation) {
      return
    }

    try {
      await cancelSmsActivation(activeActivation.activation_id, activeActivation.provider_id)
      setActiveActivation((previous) => previous ? { ...previous, status: 'cancelled' } : null)
      if (pollTimer.current) {
        clearInterval(pollTimer.current)
      }
      setPolling(false)
      msg.success('已取消')
      void loadHistory(1)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '失败'))
    }
  }, [activeActivation, loadHistory, msg])

  const handleHistoryCancel = useCallback(async (record: SmsActivationRecord) => {
    try {
      await cancelSmsActivation(record.activation_id, record.provider_id ?? undefined)
      msg.success('已取消')
      if (activeActivation?.activation_id === record.activation_id) {
        setActiveActivation((previous) => previous ? { ...previous, status: 'cancelled' } : null)
        if (pollTimer.current) {
          clearInterval(pollTimer.current)
        }
        setPolling(false)
      }
      void loadHistory(historyPage)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '取消失败'))
    }
  }, [activeActivation?.activation_id, historyPage, loadHistory, msg])

  const handleHistoryFinish = useCallback(async (record: SmsActivationRecord) => {
    try {
      await finishSmsActivation(record.activation_id, record.provider_id ?? undefined)
      msg.success('已完成')
      if (activeActivation?.activation_id === record.activation_id) {
        setActiveActivation((previous) => previous ? { ...previous, status: 'finished' } : null)
      }
      void loadHistory(historyPage)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '完成失败'))
    }
  }, [activeActivation?.activation_id, historyPage, loadHistory, msg])

  const copyText = useCallback((text: string, label: string) => {
    void navigator.clipboard.writeText(text).then(() => msg.success(`${label}已复制`))
  }, [msg])

  return {
    activeActivation,
    activeProvider,
    buyLoading,
    configApiKey,
    configCountries,
    configCountry,
    configCountryLoading,
    configOpen,
    configSaving,
    configService,
    configTestResult,
    configTesting,
    configType,
    countryLoading,
    countrySearch,
    countrySortBy,
    defaultService: activeProvider?.default_service || 'go',
    handleBuyNumber,
    handleCancel,
    handleConfigServiceChange,
    handleConfigTypeChange,
    handleFinish,
    handleHistoryCancel,
    handleHistoryFinish,
    handleSaveConfig,
    handleTestApiKey,
    history,
    historyLoading,
    historyPage,
    historyTotal,
    loadHistory,
    loading,
    openConfig,
    polling,
    providers,
    services,
    setActiveActivation,
    setConfigApiKey,
    setConfigCountry,
    setConfigOpen,
    setConfigService,
    setCountrySearch,
    setCountrySortBy,
    sortedCountries,
    copyText,
  }
}
