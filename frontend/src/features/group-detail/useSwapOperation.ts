import { useCallback, useState } from 'react'

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
  const [swapMode, setSwapMode] = useState<'pool' | 'manual'>('pool')
  const [swapManualEmails, setSwapManualEmails] = useState<string[]>([])

  const resetSwapState = useCallback(() => {
    setSwapMode('pool')
    setSwapManualEmails([])
  }, [])

  const handleSelectAllMembers = useCallback(() => {
    return memberOptions.map((option) => option.value)
  }, [memberOptions])

  const executeSwap = useCallback((
    accountId: number,
    selectedEmails: string[],
    formValues: Record<string, string>,
  ) => {
    const extra: Record<string, string> = {}
    if (selectedEmails.length > 0) {
      extra.remove_emails = selectedEmails.join(',')
    }
    if (swapMode === 'manual') {
      if (swapManualEmails.length === 0) {
        msg.warning('请指定至少一个新成员')
        return false
      }
      extra.specific_emails = swapManualEmails.join(',')
    } else {
      const newCount = parseInt(formValues['new_count'] || '0', 10)
      if (newCount > 0) {
        extra.new_count = String(newCount)
      }
    }
    executeViaWs(accountId, 'family-swap', extra, 'family-swap')
    return true
  }, [executeViaWs, msg, swapManualEmails, swapMode])

  return {
    executeSwap,
    handleSelectAllMembers,
    resetSwapState,
    setSwapManualEmails,
    setSwapMode,
    swapManualEmails,
    swapMode,
  }
}
