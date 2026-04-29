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

import {
  BUY_BUTTON_DEBOUNCE_MS,
  MAX_CONCURRENT_BUY,
  PROVIDER_TYPES,
  REHYDRATE_PENDING_LIMIT,
  SMS_POLL_INTERVAL_MS,
  toCountryOptions,
  type SmsCountrySortBy,
} from './constants'
import {
  type ActiveSmsActivation,
  addActivation,
  countPending,
  filterAndSortCountries,
  getActiveSmsProvider,
  hasInsufficientBalance,
  patchActivation,
  rehydrateFromHistory,
  removeActivation,
} from './utils'

// 兼容旧 import 路径：组件仍从 useSmsPageController re-export 导入
export type { ActiveSmsActivation } from './utils'

export function useSmsPageController() {
  const { message: msg } = App.useApp()

  const pollTimersRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())
  const buyDebounceRef = useRef<Map<string, number>>(new Map())
  // inflight 同步计数器：从 handleBuyNumber 进入到 setActiveActivations 落地之间，
  // setState→useEffect 同步 ref 是异步的；如果用户毫秒级连点多个国家，
  // 仅靠 activeActivationsRef 会全部读到旧值绕过 cap。inflight 计数器是同步 +/-，
  // 跟 ref 中已 pending 的数相加才能可靠拦截超买。
  const inflightBuyRef = useRef(0)
  const activeProviderRef = useRef<SmsProviderConfig | undefined>(undefined)
  const historyPageRef = useRef(1)
  const activeActivationsRef = useRef<Record<string, ActiveSmsActivation>>({})
  const countryPricesRef = useRef<SmsCountryPrice[]>([])
  // StrictMode 双挂载守卫：dev 下 useEffect 会跑 2 次，避免重复发 history/rehydrate 请求
  const mountedRef = useRef(false)

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

  const [activeActivations, setActiveActivations] = useState<Record<string, ActiveSmsActivation>>({})
  const [pollingSet, setPollingSet] = useState<Set<string>>(new Set())
  const [buyLoadingSet, setBuyLoadingSet] = useState<Set<string>>(new Set())

  const [history, setHistory] = useState<SmsActivationRecord[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [historyLoading, setHistoryLoading] = useState(false)

  // 同步 ref，使内部 callback 不需要 deps 持续重建
  useEffect(() => {
    historyPageRef.current = historyPage
  }, [historyPage])
  useEffect(() => {
    activeActivationsRef.current = activeActivations
  }, [activeActivations])
  useEffect(() => {
    countryPricesRef.current = countryPrices
  }, [countryPrices])

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
      return activeProvider
    } catch {
      return undefined
    } finally {
      setLoading(false)
    }
  }, [loadCountryPrices, loadServices])

  const stopPolling = useCallback((activationId: string) => {
    const timer = pollTimersRef.current.get(activationId)
    if (timer) {
      clearInterval(timer)
      pollTimersRef.current.delete(activationId)
    }
    setPollingSet((prev) => {
      if (!prev.has(activationId)) {
        return prev
      }
      const next = new Set(prev)
      next.delete(activationId)
      return next
    })
  }, [])

  const startPolling = useCallback((activationId: string, providerId: number) => {
    // 幂等：仅替换同 id 的旧 timer，不影响其他号
    const existing = pollTimersRef.current.get(activationId)
    if (existing) {
      clearInterval(existing)
    }

    setPollingSet((prev) => {
      if (prev.has(activationId)) {
        return prev
      }
      const next = new Set(prev)
      next.add(activationId)
      return next
    })

    const timer = setInterval(async () => {
      try {
        const { data } = await checkSmsStatus(activationId, providerId)
        if (data.code) {
          setActiveActivations((prev) =>
            patchActivation(prev, activationId, { status: 'code_received', code: data.code }),
          )
          stopPolling(activationId)
          msg.success(`验证码: ${data.code}`)
          void loadHistory(historyPageRef.current)
        } else if (data.status === 'CANCEL') {
          setActiveActivations((prev) => patchActivation(prev, activationId, { status: 'cancelled' }))
          stopPolling(activationId)
          void loadHistory(historyPageRef.current)
        }
      } catch {
        // noop
      }
    }, SMS_POLL_INTERVAL_MS)

    pollTimersRef.current.set(activationId, timer)
  }, [loadHistory, msg, stopPolling])

  const rehydratePending = useCallback(async () => {
    try {
      const { data } = await getSmsHistory(1, REHYDRATE_PENDING_LIMIT, 'pending')
      const provider = activeProviderRef.current
      if (!provider || data.records.length === 0) {
        return
      }
      setActiveActivations((prev) => rehydrateFromHistory(prev, data.records, provider.id))
      for (const record of data.records) {
        startPolling(record.activation_id, record.provider_id ?? provider.id)
      }
    } catch {
      // noop
    }
  }, [startPolling])

  // 挂载：加载配置 → 加载历史 → 恢复 pending；卸载：清所有 timer
  useEffect(() => {
    if (mountedRef.current) {
      // StrictMode dev 下二次挂载：跳过重复 fetch；timer cleanup 仍由首次挂载的 cleanup 完成
      return
    }
    mountedRef.current = true
    let cancelled = false
    void (async () => {
      const provider = await loadAll()
      // 双重保险：useEffect 里的 ref 同步还没跑就要给 rehydratePending 用，
      // 这里直接同步赋值；line 273 的 useEffect 会在后续 render 继续维护
      activeProviderRef.current = provider
      if (cancelled) return
      await loadHistory(1)
      if (cancelled) return
      await rehydratePending()
    })()
    const timers = pollTimersRef.current
    return () => {
      cancelled = true
      for (const timer of timers.values()) {
        clearInterval(timer)
      }
      timers.clear()
    }
    // 仅挂载时跑一次；后续依赖通过 ref 读取
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const activeProvider = useMemo(
    () => getActiveSmsProvider(providers, defaultProviderId),
    [defaultProviderId, providers],
  )

  // 同步 activeProvider 到 ref（rehydratePending 需要）
  useEffect(() => {
    activeProviderRef.current = activeProvider
  }, [activeProvider])

  const sortedCountries = useMemo(
    () => filterAndSortCountries(countryPrices, countrySearch, countrySortBy),
    [countryPrices, countrySearch, countrySortBy],
  )

  const activeActivationList = useMemo(
    () => Object.values(activeActivations),
    [activeActivations],
  )

  const concurrentCount = useMemo(
    () => activeActivationList.filter((a) => a.status === 'pending').length,
    [activeActivationList],
  )

  // 显示用：已 pending + 正在请求中（buyLoadingSet）合并计数，
  // 让 UI 在 inflight 窗口内也显示「已达上限」，与 handleBuyNumber 的同步检查口径一致
  const projectedCount = concurrentCount + buyLoadingSet.size
  const atConcurrentCap = projectedCount >= MAX_CONCURRENT_BUY

  const defaultService = useMemo(
    () => activeProvider?.default_service || 'go',
    [activeProvider?.default_service],
  )

  const isPolling = useCallback(
    (activationId: string) => pollingSet.has(activationId),
    [pollingSet],
  )

  const isBuyLoading = useCallback(
    (countryId: number) => buyLoadingSet.has(`${countryId}`),
    [buyLoadingSet],
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

  const handleBuyNumber = useCallback(async (serviceCode: string, countryId: number) => {
    if (!activeProvider) {
      msg.warning('请先配置提供商')
      return
    }

    // 1. 防抖（同国家 1.5s 内吞掉重复点击）
    const key = `${countryId}`
    const now = Date.now()
    const expiry = buyDebounceRef.current.get(key) ?? 0
    if (now < expiry) {
      return
    }
    buyDebounceRef.current.set(key, now + BUY_BUTTON_DEBOUNCE_MS)

    // 2. 并发上限：inflight（已发出未落库的）+ 已 pending 的活动 数 ≥ cap 就拒绝
    //    单靠 activeActivationsRef 会被 setState→ref 同步的异步窗口绕过。
    const projected = inflightBuyRef.current + countPending(activeActivationsRef.current)
    if (projected >= MAX_CONCURRENT_BUY) {
      msg.warning(`同时进行的接码任务已达上限 (${MAX_CONCURRENT_BUY})`)
      return
    }

    // 3. 余额拦截
    const country = countryPricesRef.current.find((item) => item.country_id === countryId)
    if (hasInsufficientBalance(activeProvider.balance, country?.price)) {
      msg.warning(`余额不足 ($${activeProvider.balance})，无法购买`)
      return
    }

    inflightBuyRef.current += 1
    setBuyLoadingSet((prev) => {
      const next = new Set(prev)
      next.add(key)
      return next
    })
    try {
      const { data } = await requestNumber({
        provider_id: activeProvider.id,
        service: serviceCode,
        country: countryId,
      })
      setActiveActivations((prev) =>
        addActivation(prev, {
          activation_id: data.activation_id,
          phone_number: data.phone_number,
          cost: data.cost,
          status: 'pending',
          code: '',
          provider_id: activeProvider.id,
          service: serviceCode,
        }),
      )
      msg.success(`号码: ${data.phone_number}`)
      startPolling(data.activation_id, activeProvider.id)
      void loadHistory(1)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '购买失败'))
    } finally {
      inflightBuyRef.current -= 1
      setBuyLoadingSet((prev) => {
        if (!prev.has(key)) return prev
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }, [activeProvider, loadHistory, msg, startPolling])

  const handleFinish = useCallback(async (activationId: string) => {
    const activation = activeActivationsRef.current[activationId]
    if (!activation) return

    try {
      await finishSmsActivation(activation.activation_id, activation.provider_id)
      setActiveActivations((prev) => patchActivation(prev, activationId, { status: 'finished' }))
      stopPolling(activationId)
      msg.success('已完成')
      void loadHistory(historyPageRef.current)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '失败'))
    }
  }, [loadHistory, msg, stopPolling])

  const handleCancel = useCallback(async (activationId: string) => {
    const activation = activeActivationsRef.current[activationId]
    if (!activation) return

    try {
      await cancelSmsActivation(activation.activation_id, activation.provider_id)
      setActiveActivations((prev) => patchActivation(prev, activationId, { status: 'cancelled' }))
      stopPolling(activationId)
      msg.success('已取消')
      void loadHistory(historyPageRef.current)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '失败'))
    }
  }, [loadHistory, msg, stopPolling])

  const handleClear = useCallback((activationId: string) => {
    stopPolling(activationId)
    setActiveActivations((prev) => removeActivation(prev, activationId))
  }, [stopPolling])

  const handleHistoryCancel = useCallback(async (record: SmsActivationRecord) => {
    try {
      await cancelSmsActivation(record.activation_id, record.provider_id ?? undefined)
      msg.success('已取消')
      if (activeActivationsRef.current[record.activation_id]) {
        setActiveActivations((prev) => patchActivation(prev, record.activation_id, { status: 'cancelled' }))
        stopPolling(record.activation_id)
      }
      void loadHistory(historyPageRef.current)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '取消失败'))
    }
  }, [loadHistory, msg, stopPolling])

  const handleHistoryFinish = useCallback(async (record: SmsActivationRecord) => {
    try {
      await finishSmsActivation(record.activation_id, record.provider_id ?? undefined)
      msg.success('已完成')
      if (activeActivationsRef.current[record.activation_id]) {
        setActiveActivations((prev) => patchActivation(prev, record.activation_id, { status: 'finished' }))
        stopPolling(record.activation_id)
      }
      void loadHistory(historyPageRef.current)
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '完成失败'))
    }
  }, [loadHistory, msg, stopPolling])

  const copyText = useCallback((text: string, label: string) => {
    void navigator.clipboard.writeText(text).then(() => msg.success(`${label}已复制`))
  }, [msg])

  return {
    activeActivations,
    activeActivationList,
    activeProvider,
    atConcurrentCap,
    concurrentCount: projectedCount,
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
    copyText,
    defaultService,
    handleBuyNumber,
    handleCancel,
    handleClear,
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
    isBuyLoading,
    isPolling,
    loadHistory,
    loading,
    openConfig,
    providers,
    services,
    setConfigApiKey,
    setConfigCountry,
    setConfigOpen,
    setConfigService,
    setCountrySearch,
    setCountrySortBy,
    sortedCountries,
  }
}
