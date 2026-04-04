import React, { useCallback, useMemo, useState } from 'react'
import { App as AntApp, ConfigProvider, message } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { RouterProvider } from 'react-router-dom'

import LoginPage from '@/pages/LoginPage'
import { createRouter } from '@/router'
import '@/styles/global.css'
import theme from '@/theme'

const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))

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
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntApp>
        {token ? (
          <RouterProvider router={router} />
        ) : (
          <LoginPage onLoginSuccess={handleLoginSuccess} />
        )}
      </AntApp>
    </ConfigProvider>
  )
}

export default App
