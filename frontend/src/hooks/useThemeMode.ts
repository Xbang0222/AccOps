import { useContext } from 'react'

import { ThemeContext, type ThemeContextValue, type ThemeMode } from '@/contexts/themeContext'

export type { ThemeContextValue, ThemeMode }

export function useThemeMode(): ThemeContextValue {
  return useContext(ThemeContext)
}
