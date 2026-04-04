import { Flex, Spin } from 'antd';
import { Suspense, lazy, type ReactNode } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';

const MainLayout = lazy(() => import('@/layouts/MainLayout'));
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const AccountsPage = lazy(() => import('@/pages/AccountsPage'));
const GroupManagePage = lazy(() => import('@/pages/GroupManagePage'));
const GroupDetailPage = lazy(() => import('@/pages/GroupDetailPage'));
const SmsPage = lazy(() => import('@/pages/SmsPage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));

function renderLazy(element: ReactNode) {
  return (
    <Suspense
      fallback={(
        <Flex justify="center" align="center" style={{ minHeight: '50vh' }}>
          <Spin size="large" />
        </Flex>
      )}
    >
      {element}
    </Suspense>
  );
}

export const createRouter = (onLogout: () => void) =>
  createBrowserRouter([
    {
      path: '/',
      element: renderLazy(<MainLayout onLogout={onLogout} />),
      children: [
        { index: true, element: <Navigate to="/dashboard" replace /> },
        { path: 'dashboard', element: renderLazy(<DashboardPage />) },
        { path: 'accounts', element: renderLazy(<AccountsPage />) },
        { path: 'groups', element: renderLazy(<GroupManagePage />) },
        { path: 'groups/:groupId', element: renderLazy(<GroupDetailPage />) },
        { path: 'sms', element: renderLazy(<SmsPage />) },
        { path: 'settings', element: renderLazy(<SettingsPage />) },
        { path: '*', element: <Navigate to="/dashboard" replace /> },
      ],
    },
  ]);
