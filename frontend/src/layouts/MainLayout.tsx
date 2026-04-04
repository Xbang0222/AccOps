import React, { useState } from 'react';
import { Layout, Menu, Button, Typography, Tooltip, Segmented } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  SafetyCertificateOutlined,
  DashboardOutlined,
  IdcardOutlined,
  TeamOutlined,
  LogoutOutlined,
  SettingOutlined,
  PhoneOutlined,
  DesktopOutlined,
  SunOutlined,
  MoonOutlined,
} from '@ant-design/icons';
import { theme as antTheme } from 'antd';
import { useThemeMode, type ThemeMode } from '@/hooks/useThemeMode';
import './MainLayout.css';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

interface MainLayoutProps {
  onLogout: () => void;
}

const menuItems = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: 'accounts', icon: <IdcardOutlined />, label: '账号管理' },
  { key: 'groups', icon: <TeamOutlined />, label: '分组管理' },
  { key: 'sms', icon: <PhoneOutlined />, label: '接码管理' },
  { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
];

const pageTitles: Record<string, string> = {
  dashboard: '仪表盘',
  accounts: '账号管理',
  groups: '分组管理',
  sms: '接码管理',
  settings: '系统设置',
};

const menuKeyToPath: Record<string, string> = {
  dashboard: '/dashboard',
  accounts: '/accounts',
  groups: '/groups',
  sms: '/sms',
  settings: '/settings',
};

const themeModeOptions = [
  { label: <DesktopOutlined />, value: 'system' },
  { label: <SunOutlined />, value: 'light' },
  { label: <MoonOutlined />, value: 'dark' },
];

const MainLayout: React.FC<MainLayoutProps> = ({ onLogout }) => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token: themeToken } = antTheme.useToken();
  const { mode, isDark, setMode } = useThemeMode();

  const pathSegment = location.pathname.split('/')[1] || 'dashboard';
  const selectedKey = Object.keys(menuKeyToPath).includes(pathSegment) ? pathSegment : 'dashboard';
  const pageTitle = pageTitles[selectedKey] || '仪表盘';

  const handleMenuClick = ({ key }: { key: string }) => {
    const path = menuKeyToPath[key];
    if (path) navigate(path);
  };

  const borderColor = themeToken.colorBorderSecondary;

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme={isDark ? 'dark' : 'light'}
        width={200}
        style={{
          borderRight: `1px solid ${borderColor}`,
          height: '100vh',
          overflow: 'auto',
        }}
      >
        <div className="logo-header" style={{ borderBottomColor: borderColor }}>
          <div className="logo-dot">
            <SafetyCertificateOutlined style={{ fontSize: 16, color: '#fff' }} />
          </div>
          {!collapsed && (
            <Text strong style={{ fontSize: 15, whiteSpace: 'nowrap' }}>
              账号管理
            </Text>
          )}
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          onClick={handleMenuClick}
          items={menuItems}
          style={{ border: 'none', marginTop: 8 }}
        />
      </Sider>

      <Layout style={{ height: '100vh', overflow: 'hidden' }}>
        <Header
          className="main-header"
          style={{
            background: themeToken.colorBgContainer,
            borderBottomColor: borderColor,
          }}
        >
          <div className="header-left">
            <Text strong style={{ fontSize: 16 }}>
              {pageTitle}
            </Text>
          </div>
          <div className="header-right">
            <Segmented
              size="small"
              options={themeModeOptions}
              value={mode}
              onChange={(v) => setMode(v as ThemeMode)}
            />
            <Tooltip title="退出登录">
              <Button
                type="text"
                icon={<LogoutOutlined />}
                onClick={onLogout}
                style={{ color: themeToken.colorTextTertiary }}
              >
                退出
              </Button>
            </Tooltip>
          </div>
        </Header>

        <Content className="content-wrapper">
          <div
            className="site-layout-content"
            style={{
              background: themeToken.colorBgContainer,
              boxShadow: isDark
                ? '0 1px 4px rgba(0, 0, 0, 0.2)'
                : '0 1px 4px rgba(0, 0, 0, 0.04)',
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
