/** 自动化 WebSocket 的消息结构 */
export interface StepMsg {
  type: 'step' | 'result' | 'error'
  step?: number
  name?: string
  status?: string
  message?: string
  success?: boolean
  duration_ms?: number
  timestamp?: string
}

/** 单个账号当前自动化操作的运行时状态（跨页面共享） */
export interface AccountOpState {
  runningOpKey: string | null
  steps: StepMsg[]
  resultMsg: string
  resultSuccess: boolean | null
}

export function createAccountOpState(runningOpKey: string | null = null): AccountOpState {
  return {
    runningOpKey,
    steps: [],
    resultMsg: '',
    resultSuccess: null,
  }
}

export function updateAccountOpState(
  previous: Record<number, AccountOpState>,
  accountId: number,
  patch: Partial<AccountOpState>,
): Record<number, AccountOpState> {
  return {
    ...previous,
    [accountId]: {
      ...(previous[accountId] ?? createAccountOpState()),
      ...patch,
    },
  }
}
