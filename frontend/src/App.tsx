import React, { useCallback, useMemo, useState } from 'react'
import { App as AntApp, ConfigProvider, message } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { RouterProvider } from 'react-router-dom'

import { AutomationProvider } from '@/contexts/AutomationProvider'
import LoginPage from '@/pages/LoginPage'
import { createRouter } from '@/router'
import '@/styles/global.css'
import { getThemeConfig } from '@/theme'
import { ThemeProvider } from '@/contexts/ThemeProvider'
import { useThemeMode } from '@/hooks/useThemeMode'

function AppInner() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const { isDark } = useThemeMode()
  const themeConfig = useMemo(() => getThemeConfig(isDark), [isDark])

  const handleLoginSuccess = useCallback((newToken: string) => {
    setToken(newToken)
  }, [])

  const handleLogout = useCallback(() => {
    localStorage.removeItem('token')
    setToken(null)
    message.success('已退出登录')
  }, [])

  const router = useMemo(() => createRouter(handleLogout), [handleLogout])

  return (
    <ConfigProvider locale={zhCN} theme={themeConfig}>
      <AntApp>
        {token ? (
          <AutomationProvider>
            <RouterProvider router={router} />
          </AutomationProvider>
        ) : (
          <LoginPage onLoginSuccess={handleLoginSuccess} />
        )}
      </AntApp>
    </ConfigProvider>
  )
}

const App: React.FC = () => (
  <ThemeProvider>
    <AppInner />
  </ThemeProvider>
)

export default App
