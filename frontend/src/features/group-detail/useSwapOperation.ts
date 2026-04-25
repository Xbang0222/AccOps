import { useCallback, useMemo, useState } from 'react'

import type { GroupMemberOption } from './utils'

interface UseSwapOperationOptions {
  executeViaWs: (accountId: number, action: string, extra: Record<string, string>, opKey?: string) => void
  memberOptions: GroupMemberOption[]
  msg: { warning: (content: string) => void }
}

export function useSwapOperation({
  executeViaWs,
  memberOptions,
  msg,
}: UseSwapOperationOptions) {
  const [swapManualEmails, setSwapManualEmails] = useState<string[]>([])

  const resetSwapState = useCallback(() => {
    setSwapManualEmails([])
  }, [])

  const handleSelectAllMembers = useCallback(() => {
    return memberOptions.map((option) => option.value)
  }, [memberOptions])

  const executeSwap = useCallback((
    accountId: number,
    selectedEmails: string[],
  ) => {
    const extra: Record<string, string> = {}
    if (selectedEmails.length > 0) {
      extra.remove_emails = selectedEmails.join(',')
    }
    if (swapManualEmails.length === 0) {
      msg.warning('请指定至少一个新成员')
      return false
    }
    extra.specific_emails = swapManualEmails.join(',')
    executeViaWs(accountId, 'family-swap', extra, 'family-swap')
    return true
  }, [executeViaWs, msg, swapManualEmails])

  return useMemo(
    () => ({
      executeSwap,
      handleSelectAllMembers,
      resetSwapState,
      setSwapManualEmails,
      swapManualEmails,
    }),
    [executeSwap, handleSelectAllMembers, resetSwapState, swapManualEmails],
  )
}
