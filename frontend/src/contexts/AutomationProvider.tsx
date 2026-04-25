import { App } from 'antd'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { config } from '@/config'
import {
  createAccountOpState,
  updateAccountOpState,
  type AccountOpState,
  type StepMsg,
} from '@/types/automation'

import {
  AutomationControlContext,
  AutomationStateContext,
  type AutomationControlValue,
  type AutomationEventHandlers,
  type AutomationStateValue,
} from './automationContext'

const WS_URL = `${config.wsBaseUrl}/api/v1/ws/automation`

const DEFAULT_SUCCESS_MSG = '操作成功'
const DEFAULT_FAIL_MSG = '操作失败'
const DEFAULT_ERROR_MSG = '操作异常'
const WS_CONNECTION_FAILED_MSG = 'WebSocket 连接失败'

interface WsConnection {
  ws: WebSocket
  opKey: string
  accountId: number
}

function appendStep(current: AccountOpState, step: StepMsg): AccountOpState {
  const nextSteps = [...current.steps]
  if (step.status === 'running') {
    nextSteps.push(step)
    return { ...current, steps: nextSteps }
  }
  let idx = -1
  for (let j = nextSteps.length - 1; j >= 0; j--) {
    if (nextSteps[j].step === step.step) {
      idx = j
      break
    }
  }
  if (idx >= 0) nextSteps[idx] = step
  else nextSteps.push(step)
  return { ...current, steps: nextSteps }
}

export function AutomationProvider({ children }: { children: ReactNode }) {
  const { message: msg } = App.useApp()
  const [opStates, setOpStates] = useState<Record<number, AccountOpState>>({})
  const connectionsRef = useRef<Map<number, WsConnection>>(new Map())
  const listenersRef = useRef<Set<AutomationEventHandlers>>(new Set())

  useEffect(() => {
    const connections = connectionsRef.current
    return () => {
      for (const conn of connections.values()) {
        conn.ws.close()
      }
      connections.clear()
    }
  }, [])

  const patchOpState = useCallback((accountId: number, patch: Partial<AccountOpState>) => {
    setOpStates((previous) => updateAccountOpState(previous, accountId, patch))
  }, [])

  const subscribe = useCallback((handlers: AutomationEventHandlers) => {
    listenersRef.current.add(handlers)
    return () => {
      listenersRef.current.delete(handlers)
    }
  }, [])

  /** 把事件分发给所有当前订阅者；method 不存在时跳过 */
  const fanOut = useCallback(<K extends keyof AutomationEventHandlers>(
    method: K,
    invoke: (handler: NonNullable<AutomationEventHandlers[K]>) => void,
  ) => {
    for (const listener of listenersRef.current) {
      const fn = listener[method]
      if (fn) invoke(fn as NonNullable<AutomationEventHandlers[K]>)
    }
  }, [])

  const handleStep = useCallback(
    (accountId: number, trackKey: string, data: StepMsg) => {
      setOpStates((previous) => {
        const current = previous[accountId] ?? createAccountOpState(trackKey)
        return { ...previous, [accountId]: appendStep(current, data) }
      })
      fanOut('onStep', (fn) => fn(accountId, data))
    },
    [fanOut],
  )

  const handleResult = useCallback(
    (accountId: number, trackKey: string, data: StepMsg) => {
      const success = data.success ?? false
      const message = data.message ?? (success ? DEFAULT_SUCCESS_MSG : DEFAULT_FAIL_MSG)
      patchOpState(accountId, {
        runningOpKey: null,
        resultMsg: message,
        resultSuccess: success,
      })
      if (success) {
        msg.success(message)
        fanOut('onSuccess', (fn) => fn(trackKey, message, accountId))
      } else {
        msg.warning(message)
        fanOut('onFail', (fn) => fn(trackKey, message, accountId))
      }
    },
    [fanOut, msg, patchOpState],
  )

  const handleErrorMessage = useCallback(
    (accountId: number, trackKey: string, message: string) => {
      patchOpState(accountId, {
        runningOpKey: null,
        resultMsg: message,
        resultSuccess: false,
      })
      msg.error(message)
      fanOut('onError', (fn) => fn(trackKey, message, accountId))
    },
    [fanOut, msg, patchOpState],
  )

  /** 派发一条 WS 消息到对应处理器；不属于已知类型则忽略 */
  const dispatchWsMessage = useCallback(
    (accountId: number, trackKey: string, ws: WebSocket, data: StepMsg) => {
      if (data.type === 'step') {
        handleStep(accountId, trackKey, data)
        return
      }
      if (data.type === 'result') {
        handleResult(accountId, trackKey, data)
      } else if (data.type === 'error') {
        handleErrorMessage(accountId, trackKey, data.message ?? DEFAULT_ERROR_MSG)
      }
      ws.close()
      connectionsRef.current.delete(accountId)
    },
    [handleStep, handleResult, handleErrorMessage],
  )

  const execute = useCallback(
    (accountId: number, action: string, extra: Record<string, string> = {}, opKey?: string) => {
      const existing = connectionsRef.current.get(accountId)
      if (existing) {
        existing.ws.close()
        connectionsRef.current.delete(accountId)
      }

      const trackKey = opKey ?? action
      const token = localStorage.getItem('token') ?? ''
      const ws = new WebSocket(`${WS_URL}?token=${token}`)
      const conn: WsConnection = { ws, opKey: trackKey, accountId }
      connectionsRef.current.set(accountId, conn)

      setOpStates((previous) => ({
        ...previous,
        [accountId]: createAccountOpState(trackKey),
      }))

      ws.onopen = () => {
        ws.send(JSON.stringify({ action, account_id: accountId, ...extra }))
      }

      ws.onmessage = (event) => {
        let data: StepMsg
        try {
          data = JSON.parse(event.data) as StepMsg
        } catch {
          return
        }
        dispatchWsMessage(accountId, trackKey, ws, data)
      }

      ws.onerror = () => {
        handleErrorMessage(accountId, trackKey, WS_CONNECTION_FAILED_MSG)
        connectionsRef.current.delete(accountId)
      }

      ws.onclose = () => {
        connectionsRef.current.delete(accountId)
      }
    },
    [dispatchWsMessage, handleErrorMessage],
  )

  const cancel = useCallback((accountId?: number) => {
    if (accountId !== undefined) {
      const conn = connectionsRef.current.get(accountId)
      if (conn && conn.ws.readyState === WebSocket.OPEN) {
        conn.ws.send(JSON.stringify({ action: 'cancel' }))
      }
      return
    }
    for (const conn of connectionsRef.current.values()) {
      if (conn.ws.readyState === WebSocket.OPEN) {
        conn.ws.send(JSON.stringify({ action: 'cancel' }))
      }
    }
  }, [])

  const resetOpState = useCallback((accountId: number, runningOpKey: string) => {
    setOpStates((previous) => ({
      ...previous,
      [accountId]: createAccountOpState(runningOpKey),
    }))
  }, [])

  // control 部分稳定引用，不随 opStates 变化
  const controlValue = useMemo<AutomationControlValue>(
    () => ({ execute, cancel, subscribe, setOpState: patchOpState, resetOpState }),
    [execute, cancel, subscribe, patchOpState, resetOpState],
  )

  // state 部分随 opStates 变化触发订阅它的消费方重渲染
  const stateValue = useMemo<AutomationStateValue>(
    () => ({ opStates }),
    [opStates],
  )

  return (
    <AutomationControlContext.Provider value={controlValue}>
      <AutomationStateContext.Provider value={stateValue}>
        {children}
      </AutomationStateContext.Provider>
    </AutomationControlContext.Provider>
  )
}
