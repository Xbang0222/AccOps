import { App } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  clearAccountStatus,
  createBrowserProfile,
  discoverFamily,
  downloadOAuthCredential,
  getAvailableAccounts,
  getBrowserProfiles,
  getGroup,
  getOAuthCredential,
  launchBrowser,
  markAccountUnusable,
  removeAccountFromGroup,
  stopBrowser,
} from '@/api'
import type { AutomationOperationDefinition } from '@/features/automation/operationMeta'
import { createDefaultBrowserProfile } from '@/features/browser/browserProfileDefaults'
import {
  buildBrowserRuntimeState,
  updateLoadingAccountSet,
  updateRunningAccountSet,
} from '@/features/browser/runtime'
import { useAutomationWs } from '@/hooks/useAutomationWs'
import type { Group } from '@/types'
import { getErrorMessage } from '@/utils/http'
import { generateTOTP } from '@/utils/totp'

import { useSwapOperation } from './useSwapOperation'
import {
  createAccountOpState,
  FAMILY_GROUP_CAPACITY,
  FAMILY_GROUP_MAX_SUB_MEMBERS,
  getGroupMemberOptions,
  getSortedGroupAccounts,
  parseEmailInput,
  updateAccountOpState,
} from './utils'

export function useGroupDetailController(groupId: number) {
  const { message: msg } = App.useApp()

  const [group, setGroup] = useState<Group | null>(null)
  const [loading, setLoading] = useState(false)
  const [masked, setMasked] = useState(false)
  const [browserRunning, setBrowserRunning] = useState<Set<number>>(new Set())
  const [browserLoading, setBrowserLoading] = useState<Set<number>>(new Set())
  const [profileMap, setProfileMap] = useState<Record<number, number>>({})
  const [opStates, setOpStates] = useState<Record<number, ReturnType<typeof createAccountOpState>>>({})
  const [activeOp, setActiveOp] = useState<AutomationOperationDefinition | null>(null)
  const [activeAccountId, setActiveAccountId] = useState<number | null>(null)
  const [formValues, setFormValues] = useState<Record<string, string>>({})
  const [selectedEmails, setSelectedEmails] = useState<string[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)
  const [availableAccountOptions, setAvailableAccountOptions] = useState<{ label: string; value: string }[]>([])
  const [availableAccountsLoading, setAvailableAccountsLoading] = useState(false)
  const availableSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const wsAccountIdRef = useRef<number | null>(null)

  const loadGroup = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await getGroup(groupId)
      setGroup(data)
    } catch {
      msg.error('加载分组详情失败')
    } finally {
      setLoading(false)
    }
  }, [groupId, msg])

  const loadBrowserStatus = useCallback(async () => {
    try {
      const { data } = await getBrowserProfiles()
      const runtimeState = buildBrowserRuntimeState(data.profiles)
      setProfileMap(runtimeState.profileMap)
      setBrowserRunning(runtimeState.runningAccountIds)
    } catch {
      // noop
    }
  }, [])

  useEffect(() => {
    void loadGroup()
    void loadBrowserStatus()
  }, [loadBrowserStatus, loadGroup])

  // 清理防抖 timer
  useEffect(() => {
    return () => {
      if (availableSearchTimer.current) {
        clearTimeout(availableSearchTimer.current)
      }
    }
  }, [])

  const setAccountOpPatch = useCallback((accountId: number, patch: Partial<ReturnType<typeof createAccountOpState>>) => {
    setOpStates((previous) => updateAccountOpState(previous, accountId, patch))
  }, [])

  const automation = useAutomationWs({
    onStep: (accountId, step) => {
      setOpStates((previous) => {
        const current = previous[accountId]
        if (!current) return previous
        const updatedSteps = [...(current.steps ?? [])]
        if (step.status === 'running') {
          updatedSteps.push(step)
        } else {
          let idx = -1
          for (let j = updatedSteps.length - 1; j >= 0; j--) {
            if (updatedSteps[j].step === step.step) { idx = j; break }
          }
          if (idx >= 0) updatedSteps[idx] = step
          else updatedSteps.push(step)
        }
        return { ...previous, [accountId]: { ...current, steps: updatedSteps } }
      })
    },
    onSuccess: (_opKey, message, accountId) => {
      const id = accountId ?? wsAccountIdRef.current
      if (id !== null) {
        setAccountOpPatch(id, {
          runningOpKey: null,
          resultMsg: message,
          resultSuccess: true,
        })
      }
      msg.success(message)
      void loadGroup()
    },
    onFail: (_opKey, message, accountId) => {
      const id = accountId ?? wsAccountIdRef.current
      if (id !== null) {
        setAccountOpPatch(id, {
          runningOpKey: null,
          resultMsg: message,
          resultSuccess: false,
        })
      }
      msg.warning(message)
    },
    onError: (_opKey, message, accountId) => {
      const id = accountId ?? wsAccountIdRef.current
      if (id !== null) {
        setAccountOpPatch(id, {
          runningOpKey: null,
          resultMsg: message,
          resultSuccess: false,
        })
      }
      msg.error(message)
    },
  })
  const { execute } = automation

  const executeViaWs = useCallback(
    (accountId: number, action: string, extra: Record<string, string> = {}, opKey?: string) => {
      const trackingKey = opKey ?? action
      setSelectedAccountId(accountId)
      wsAccountIdRef.current = accountId
      setOpStates((previous) => ({
        ...previous,
        [accountId]: createAccountOpState(trackingKey),
      }))
      execute(accountId, action, extra, opKey)
    },
    [execute],
  )

  const toggleBrowserLoading = useCallback((accountId: number, loadingState: boolean) => {
    setBrowserLoading((previous) => updateLoadingAccountSet(previous, accountId, loadingState))
  }, [])

  const handleLaunchBrowser = useCallback(async (accountId: number) => {
    setSelectedAccountId(accountId)
    toggleBrowserLoading(accountId, true)

    try {
      let profileId = profileMap[accountId]
      if (!profileId) {
        const account = (group?.accounts ?? []).find((item) => item.id === accountId)
        const result = await createBrowserProfile(
          createDefaultBrowserProfile(accountId, account?.email ?? ''),
        )
        profileId = result.data.id
        setProfileMap((previous) => ({ ...previous, [accountId]: profileId }))
      }

      await launchBrowser(profileId)
      setBrowserRunning((previous) => updateRunningAccountSet(previous, accountId, true))
      msg.success('浏览器已启动，开始自动登录...')
      executeViaWs(accountId, 'login', {}, 'login')
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '启动失败'))
    } finally {
      toggleBrowserLoading(accountId, false)
    }
  }, [executeViaWs, group?.accounts, msg, profileMap, toggleBrowserLoading])

  const handleStopBrowser = useCallback(async (accountId: number) => {
    const profileId = profileMap[accountId]
    if (!profileId) {
      return
    }

    toggleBrowserLoading(accountId, true)
    try {
      await stopBrowser(profileId)
      setBrowserRunning((previous) => updateRunningAccountSet(previous, accountId, false))
      msg.success('浏览器已停止')
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '停止失败'))
    } finally {
      toggleBrowserLoading(accountId, false)
    }
  }, [msg, profileMap, toggleBrowserLoading])

  const handleToggleBrowser = useCallback((accountId: number, running: boolean) => {
    if (running) {
      automation.cancel(accountId)
      void handleStopBrowser(accountId)
      return
    }

    void handleLaunchBrowser(accountId)
  }, [automation, handleLaunchBrowser, handleStopBrowser])

  const handleDiscover = useCallback(async (accountId: number) => {
    setOpStates((previous) => ({
      ...previous,
      [accountId]: createAccountOpState('family-discover'),
    }))

    try {
      const { data } = await discoverFamily(accountId)
      if (data.success) {
        msg.success(data.message || '同步成功')
        await loadGroup()
      } else if (data.cookies_expired) {
        msg.warning(data.message || 'Cookies 已过期，请重新登录')
      } else {
        msg.warning(data.message || '同步失败')
      }
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '同步请求失败'))
    } finally {
      setAccountOpPatch(accountId, { runningOpKey: null })
    }
  }, [loadGroup, msg, setAccountOpPatch])

  const loadAvailableAccounts = useCallback(async (search: string = '') => {
    setAvailableAccountsLoading(true)
    try {
      const { data } = await getAvailableAccounts(search)
      setAvailableAccountOptions(
        data.accounts.map((a) => ({ label: a.email, value: a.email })),
      )
    } catch {
      // noop
    } finally {
      setAvailableAccountsLoading(false)
    }
  }, [])

  const handleAvailableAccountSearch = useCallback((value: string) => {
    if (availableSearchTimer.current) {
      clearTimeout(availableSearchTimer.current)
    }
    availableSearchTimer.current = setTimeout(() => {
      void loadAvailableAccounts(value)
    }, 300)
  }, [loadAvailableAccounts])

  const memberOptions = useMemo(
    () => getGroupMemberOptions(group, activeAccountId),
    [activeAccountId, group],
  )

  const swap = useSwapOperation({
    executeViaWs,
    memberOptions,
    msg,
  })

  const openOperationModal = useCallback((accountId: number, operation: AutomationOperationDefinition) => {
    setFormValues({})
    setSelectedEmails([])
    swap.resetSwapState()
    setActiveOp(operation)
    setActiveAccountId(accountId)
    // 打开邀请或换号弹窗时预加载可用账号
    if (operation.key === 'family-invite' || operation.key === 'family-swap') {
      void loadAvailableAccounts()
    }
  }, [loadAvailableAccounts, swap])

  const handleOperationClick = useCallback((accountId: number, operation: AutomationOperationDefinition) => {
    if (operation.key === 'family-discover') {
      void handleDiscover(accountId)
      return
    }

    if (operation.needBrowser && !browserRunning.has(accountId)) {
      msg.warning('请先启动浏览器')
      return
    }

    // 换号走弹窗
    if (operation.key === 'family-swap') {
      openOperationModal(accountId, operation)
      return
    }

    if (!operation.fields) {
      executeViaWs(accountId, operation.key, {}, operation.key)
      return
    }

    openOperationModal(accountId, operation)
  }, [browserRunning, executeViaWs, handleDiscover, msg, openOperationModal])

  const handlePhoneVerify = useCallback((accountId: number, validationUrl: string) => {
    if (!browserRunning.has(accountId)) {
      msg.warning('请先启动浏览器')
      return
    }

    executeViaWs(accountId, 'phone-verify', { validation_url: validationUrl }, 'phone-verify')
  }, [browserRunning, executeViaWs, msg])

  const handleFieldModalOk = useCallback(() => {
    if (!activeOp || activeAccountId === null) {
      return
    }

    if (activeOp.key === 'family-invite') {
      if (selectedEmails.length === 0) {
        msg.warning('请输入至少一个邮箱')
        return
      }
      executeViaWs(activeAccountId, 'family-batch-invite', { invite_emails: selectedEmails.join(',') }, 'family-invite')
    } else if (activeOp.key === 'family-remove') {
      if (selectedEmails.length === 0) {
        msg.warning('请选择至少一个成员')
        return
      }
      executeViaWs(activeAccountId, 'family-batch-remove', { member_emails: selectedEmails.join(',') }, 'family-remove')
    } else if (activeOp.key === 'family-swap') {
      if (!swap.executeSwap(activeAccountId, selectedEmails)) {
        return
      }
    } else {
      for (const field of activeOp.fields ?? []) {
        if (!formValues[field.name]?.trim()) {
          msg.warning(`请输入${field.placeholder}`)
          return
        }
      }

      const extra = Object.fromEntries(
        (activeOp.fields ?? []).map((field) => [field.name, formValues[field.name].trim()]),
      )
      executeViaWs(activeAccountId, activeOp.key, extra, activeOp.key)
    }

    setActiveOp(null)
    setActiveAccountId(null)
  }, [activeAccountId, activeOp, executeViaWs, formValues, msg, selectedEmails, swap])

  const handleEmailSearch = useCallback((value: string) => {
    const emails = parseEmailInput(value)
    if (emails.length === 0) {
      return
    }

    setSelectedEmails((previous) => Array.from(new Set([...previous, ...emails])))
  }, [])

  const copyToClipboard = useCallback((text: string, label: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      msg.success(`${label}已复制`)
    })
  }, [msg])

  const copyTOTPCode = useCallback((secret: string) => {
    try {
      const { code } = generateTOTP(secret)
      void navigator.clipboard.writeText(code).then(() => {
        msg.success(`2FA 验证码已复制: ${code}`)
      })
    } catch {
      msg.error('生成验证码失败')
    }
  }, [msg])

  const handleOAuth = useCallback((accountId: number) => {
    if (!browserRunning.has(accountId)) {
      msg.warning('请先启动浏览器')
      return
    }

    executeViaWs(accountId, 'oauth', {}, 'oauth')
  }, [browserRunning, executeViaWs, msg])

  const handleCopyOAuthJson = useCallback(async (accountId: number) => {
    try {
      const { data } = await getOAuthCredential(accountId)
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      msg.success('OAuth JSON 已复制到剪贴板')
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '获取 OAuth 凭证失败'))
    }
  }, [msg])

  const handleDownloadOAuth = useCallback(async (accountId: number) => {
    try {
      const { blob, filename } = await downloadOAuthCredential(accountId)
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = filename
      link.click()
      URL.revokeObjectURL(link.href)
      msg.success('下载成功')
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '下载失败'))
    }
  }, [msg])

  const handleRemoveFromGroup = useCallback(async (accountId: number) => {
    try {
      await removeAccountFromGroup(accountId)
      msg.success('账号已从分组移除')
      await loadGroup()
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '移除失败'))
    }
  }, [loadGroup, msg])

  const handleMarkUnusable = useCallback(async (accountId: number) => {
    try {
      await markAccountUnusable(accountId)
      msg.success('已标记为无法使用')
      await loadGroup()
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '标记失败'))
    }
  }, [loadGroup, msg])

  const handleClearStatus = useCallback(async (accountId: number) => {
    try {
      await clearAccountStatus(accountId)
      msg.success('已恢复正常状态')
      await loadGroup()
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '操作失败'))
    }
  }, [loadGroup, msg])

  const sortedAccounts = useMemo(() => getSortedGroupAccounts(group), [group])

  const [batchRunning, setBatchRunning] = useState<string | null>(null)

  const handleBatchLaunch = useCallback(async () => {
    const targets = sortedAccounts.filter((a) => !browserRunning.has(a.id))
    if (targets.length === 0) {
      msg.info('所有账号浏览器已启动')
      return
    }
    setBatchRunning('launch')
    try {
      for (const account of targets) {
        await handleLaunchBrowser(account.id)
      }
    } finally {
      setBatchRunning(null)
    }
  }, [browserRunning, handleLaunchBrowser, msg, sortedAccounts])

  const handleBatchStop = useCallback(async () => {
    const targets = sortedAccounts.filter((a) => browserRunning.has(a.id))
    if (targets.length === 0) {
      msg.info('没有运行中的浏览器')
      return
    }
    setBatchRunning('stop')
    try {
      for (const account of targets) {
        automation.cancel(account.id)
        await handleStopBrowser(account.id)
      }
    } finally {
      setBatchRunning(null)
    }
  }, [automation, browserRunning, handleStopBrowser, msg, sortedAccounts])

  const handleBatchOAuth = useCallback(() => {
    const targets = sortedAccounts.filter((a) => browserRunning.has(a.id))
    if (targets.length === 0) {
      msg.warning('请先启动浏览器')
      return
    }
    for (const account of targets) {
      handleOAuth(account.id)
    }
  }, [browserRunning, handleOAuth, msg, sortedAccounts])

  const handleSelectAllMembers = useCallback(() => {
    setSelectedEmails(swap.handleSelectAllMembers())
  }, [swap])

  const handleClearSelectedEmails = useCallback(() => {
    setSelectedEmails([])
  }, [])

  const inviteCapacityLeft = useMemo(() => {
    const currentCount = group?.accounts?.length ?? 0
    return Math.max(0, FAMILY_GROUP_CAPACITY - currentCount)
  }, [group?.accounts])

  const swapNewCapacityLeft = useMemo(() => {
    const currentCount = group?.accounts?.length ?? 0
    const afterRemoval = currentCount - selectedEmails.length
    return Math.max(0, Math.min(FAMILY_GROUP_MAX_SUB_MEMBERS, FAMILY_GROUP_CAPACITY - afterRemoval))
  }, [group?.accounts, selectedEmails.length])

  const handleSelectAllInviteEmails = useCallback(() => {
    const limit = Math.min(inviteCapacityLeft, availableAccountOptions.length)
    if (limit <= 0) {
      msg.warning('家庭组已满（上限 6 人）')
      return
    }
    setSelectedEmails(availableAccountOptions.slice(0, limit).map((option) => option.value))
  }, [availableAccountOptions, inviteCapacityLeft, msg])

  const handleSelectAllSwapManualEmails = useCallback(() => {
    const limit = Math.min(swapNewCapacityLeft, availableAccountOptions.length)
    if (limit <= 0) {
      msg.warning('已达到家庭组上限，请先增加要移除的成员')
      return
    }
    swap.setSwapManualEmails(availableAccountOptions.slice(0, limit).map((option) => option.value))
  }, [availableAccountOptions, msg, swap, swapNewCapacityLeft])

  const handleClearSwapManualEmails = useCallback(() => {
    swap.setSwapManualEmails([])
  }, [swap])
  const selectedAccount = useMemo(
    () => (group?.accounts ?? []).find((account) => account.id === selectedAccountId) ?? null,
    [group?.accounts, selectedAccountId],
  )
  const selectedOpState = selectedAccountId ? (opStates[selectedAccountId] ?? null) : null

  return {
    activeOp,
    automation,
    availableAccountOptions,
    availableAccountsLoading,
    batchRunning,
    browserLoading,
    browserRunning,
    formValues,
    group,
    handleAvailableAccountSearch,
    handleBatchLaunch,
    handleBatchOAuth,
    handleBatchStop,
    handleClearSelectedEmails,
    handleClearStatus,
    handleClearSwapManualEmails,
    handleCopyOAuthJson,
    handleDownloadOAuth,
    handleEmailSearch,
    handleFieldModalOk,
    handleMarkUnusable,
    handleOAuth,
    handleOperationClick,
    handlePhoneVerify,
    handleRemoveFromGroup,
    handleSelectAllInviteEmails,
    handleSelectAllMembers,
    handleSelectAllSwapManualEmails,
    handleToggleBrowser,
    inviteCapacityLeft,
    swapNewCapacityLeft,
    loadGroup,
    loading,
    masked,
    memberOptions,
    opStates,
    profileMap,
    selectedAccount,
    selectedAccountId,
    selectedEmails,
    selectedOpState,
    setActiveAccountId,
    setActiveOp,
    setFormValues,
    setMasked,
    setSelectedAccountId,
    setSelectedEmails,
    setSwapManualEmails: swap.setSwapManualEmails,
    sortedAccounts,
    swapManualEmails: swap.swapManualEmails,
    copyToClipboard,
    copyTOTPCode,
  }
}
