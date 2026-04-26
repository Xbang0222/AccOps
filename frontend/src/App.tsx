import React, { useCallback, useMemo, useState } from 'react'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { RouterProvider } from 'react-router-dom'

import ErrorBoundary from '@/components/ErrorBoundary'
import { AutomationProvider } from '@/contexts/AutomationProvider'
import LoginPage from '@/pages/LoginPage'
import { createRouter } from '@/router'
import '@/styles/global.css'
import { getThemeConfig } from '@/theme'
import { ThemeProvider } from '@/contexts/ThemeProvider'
import { useThemeMode } from '@/hooks/useThemeMode'

interface AppContentProps {
  token: string | null
  onLogout: () => void
  onLoginSuccess: (newToken: string) => void
}

// AppContent 被渲染在 <AntApp> 内, 因此可通过 App.useApp() 拿到主题感知的 message 实例
function AppContent({ token, onLogout, onLoginSuccess }: AppContentProps) {
  const { message } = AntApp.useApp()

  const handleLogout = useCallback(() => {
    onLogout()
    message.success('已退出登录')
  }, [message, onLogout])

  const router = useMemo(() => createRouter(handleLogout), [handleLogout])

  return token ? (
    <AutomationProvider>
      <RouterProvider router={router} />
    </AutomationProvider>
  ) : (
    <LoginPage onLoginSuccess={onLoginSuccess} />
  )
}

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
  }, [])

  return (
    <ConfigProvider locale={zhCN} theme={themeConfig}>
      <AntApp>
        <AppContent
          token={token}
          onLogout={handleLogout}
          onLoginSuccess={handleLoginSuccess}
        />
      </AntApp>
    </ConfigProvider>
  )
}

const App: React.FC = () => (
  <ErrorBoundary>
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  </ErrorBoundary>
)

export default App
