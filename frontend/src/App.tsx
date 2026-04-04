import React, { useState, useMemo } from 'react';
import { ConfigProvider, message, App as AntApp } from 'antd';
import { RouterProvider } from 'react-router-dom';
import zhCN from 'antd/locale/zh_CN';
import LoginPage from '@/pages/LoginPage';
import { createRouter } from '@/router';
import theme from '@/theme';
import '@/styles/global.css';

const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));

  const handleLoginSuccess = (newToken: string) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    message.success('已退出登录');
  };

  const router = useMemo(() => createRouter(handleLogout), [token]);

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
  );
};

export default App;
