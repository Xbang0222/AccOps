import { createContext, useContext, useEffect, useRef } from 'react'

import type { AccountOpState, StepMsg } from '@/types/automation'

/**
 * 自动化任务事件订阅者。
 *
 * 注意：Provider 内部已对每次任务结束（result / error / WS error）调用
 * `message.success / warning / error` 弹出全局 toast。订阅者应只做
 * **per-page 副作用**（如刷新本页数据），不应再次弹 toast，避免重复提示。
 */
export interface AutomationEventHandlers {
  onStep?: (accountId: number, step: StepMsg) => void
  onSuccess?: (opKey: string, message: string, accountId: number) => void
  onFail?: (opKey: string, message: string, accountId: number) => void
  onError?: (opKey: string, message: string, accountId: number) => void
}

/**
 * 命令式控制接口（稳定引用）。
 * Provider 用 useCallback 保证下方所有函数引用在生命周期内不变，
 * 因此消费方仅取这部分时不会因 opStates 变化触发重渲染。
 */
export interface AutomationControlValue {
  execute: (accountId: number, action: string, extra?: Record<string, string>, opKey?: string) => void
  cancel: (accountId?: number) => void
  subscribe: (handlers: AutomationEventHandlers) => () => void
  setOpState: (accountId: number, patch: Partial<AccountOpState>) => void
  resetOpState: (accountId: number, runningOpKey: string) => void
}

/**
 * 动态状态接口。
 * 任务步骤每到一条都会触发一次更新；只有真正读取 opStates 的消费方才订阅。
 */
export interface AutomationStateValue {
  opStates: Record<number, AccountOpState>
}

export const AutomationControlContext = createContext<AutomationControlValue | null>(null)
export const AutomationStateContext = createContext<AutomationStateValue | null>(null)

function useAutomationControl(): AutomationControlValue {
  const ctx = useContext(AutomationControlContext)
  if (!ctx) {
    throw new Error('useAutomation* must be used within <AutomationProvider>')
  }
  return ctx
}

function useAutomationState(): AutomationStateValue {
  const ctx = useContext(AutomationStateContext)
  if (!ctx) {
    throw new Error('useAutomation* must be used within <AutomationProvider>')
  }
  return ctx
}

/**
 * 命令式调用 + 订阅。不订阅 opStates，避免任务步骤变化时无谓重渲染。
 */
export function useAutomation(): AutomationControlValue {
  return useAutomationControl()
}

/**
 * 读取所有账号的运行时状态。仅在需要展示步骤/结果时使用。
 */
export function useAutomationOpStates(): Record<number, AccountOpState> {
  return useAutomationState().opStates
}

/**
 * 读取单个账号的运行时状态。
 */
export function useAccountOpState(accountId: number | null | undefined): AccountOpState | null {
  const { opStates } = useAutomationState()
  if (accountId === null || accountId === undefined) {
    return null
  }
  return opStates[accountId] ?? null
}

/**
 * 订阅自动化事件。组件挂载期间触发回调，卸载后自动取消订阅
 * （任务本身不受影响，继续在后端跑）。
 */
export function useAutomationEvents(handlers: AutomationEventHandlers): void {
  const { subscribe } = useAutomationControl()
  const handlersRef = useRef(handlers)

  useEffect(() => {
    handlersRef.current = handlers
  })

  useEffect(() => {
    const dispatcher: AutomationEventHandlers = {
      onStep: (accountId, step) => handlersRef.current.onStep?.(accountId, step),
      onSuccess: (opKey, message, accountId) => handlersRef.current.onSuccess?.(opKey, message, accountId),
      onFail: (opKey, message, accountId) => handlersRef.current.onFail?.(opKey, message, accountId),
      onError: (opKey, message, accountId) => handlersRef.current.onError?.(opKey, message, accountId),
    }
    return subscribe(dispatcher)
  }, [subscribe])
}
