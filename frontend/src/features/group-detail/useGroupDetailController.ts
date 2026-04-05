import { App, Modal } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  clearBrowserData,
  createBrowserProfile,
  discoverFamily,
  downloadOAuthCredential,
  getAvailableAccounts,
  getBrowserProfiles,
  getGroup,
  getOAuthCredential,
  launchBrowser,
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

import {
  createAccountOpState,
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
  const [replaceOldEmail, setReplaceOldEmail] = useState('')
  const [replaceNewEmail, setReplaceNewEmail] = useState('')
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

  useEffect(() => {
    const accountId = wsAccountIdRef.current
    if (accountId === null || automation.runningOp === null) {
      return
    }

    setAccountOpPatch(accountId, { steps: automation.steps })
  }, [automation.runningOp, automation.steps, setAccountOpPatch])

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

  const handleClearBrowserData = useCallback((accountId: number) => {
    const profileId = profileMap[accountId]
    if (!profileId) {
      msg.error('未找到浏览器配置')
      return
    }

    Modal.confirm({
      title: '确认清除浏览器数据',
      content: '此操作将删除该账号的所有浏览器数据（cookies、缓存等），但保留配置。确定继续？',
      okText: '确认清除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await clearBrowserData(profileId)
          msg.success('浏览器数据已清除')
        } catch (error: unknown) {
          msg.error(getErrorMessage(error, '清除失败'))
        }
      },
    })
  }, [msg, profileMap])

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

  const openOperationModal = useCallback((accountId: number, operation: AutomationOperationDefinition) => {
    setFormValues({})
    setSelectedEmails([])
    setReplaceOldEmail('')
    setReplaceNewEmail('')
    setActiveOp(operation)
    setActiveAccountId(accountId)
    // 打开邀请或替换弹窗时预加载可用账号
    if (operation.key === 'family-invite' || operation.key === 'replace') {
      void loadAvailableAccounts()
    }
  }, [loadAvailableAccounts])

  const handleOperationClick = useCallback((accountId: number, operation: AutomationOperationDefinition) => {
    if (operation.key === 'family-discover') {
      void handleDiscover(accountId)
      return
    }

    if (operation.needBrowser && !browserRunning.has(accountId)) {
      msg.warning('请先启动浏览器')
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
    } else if (activeOp.key === 'replace') {
      if (!replaceOldEmail) {
        msg.warning('请选择要移除的成员')
        return
      }
      if (!replaceNewEmail.trim()) {
        msg.warning('请输入新成员邮箱')
        return
      }
      executeViaWs(
        activeAccountId,
        'family-replace',
        { old_email: replaceOldEmail, new_email: replaceNewEmail.trim() },
        'replace',
      )
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
  }, [activeAccountId, activeOp, executeViaWs, formValues, msg, replaceNewEmail, replaceOldEmail, selectedEmails])

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
    } catch {
      msg.error('移除失败')
    }
  }, [loadGroup, msg])

  const sortedAccounts = useMemo(() => getSortedGroupAccounts(group), [group])
  const memberOptions = useMemo(
    () => getGroupMemberOptions(group, activeAccountId),
    [activeAccountId, group],
  )
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
    browserLoading,
    browserRunning,
    formValues,
    group,
    handleAvailableAccountSearch,
    handleClearBrowserData,
    handleCopyOAuthJson,
    handleDownloadOAuth,
    handleEmailSearch,
    handleFieldModalOk,
    handleOAuth,
    handleOperationClick,
    handlePhoneVerify,
    handleRemoveFromGroup,
    handleToggleBrowser,
    loadGroup,
    loading,
    masked,
    memberOptions,
    opStates,
    profileMap,
    replaceNewEmail,
    replaceOldEmail,
    selectedAccount,
    selectedAccountId,
    selectedEmails,
    selectedOpState,
    setActiveAccountId,
    setActiveOp,
    setFormValues,
    setMasked,
    setReplaceNewEmail,
    setReplaceOldEmail,
    setSelectedAccountId,
    setSelectedEmails,
    sortedAccounts,
    copyToClipboard,
    copyTOTPCode,
  }
}
