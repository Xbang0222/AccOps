import { createBrowserRouter, Navigate } from 'react-router-dom';
import MainLayout from '@/layouts/MainLayout';
import DashboardPage from '@/pages/DashboardPage';
import AccountsPage from '@/pages/AccountsPage';
import GroupManagePage from '@/pages/GroupManagePage';
import GroupDetailPage from '@/pages/GroupDetailPage';
import SmsPage from '@/pages/SmsPage';
import SettingsPage from '@/pages/SettingsPage';

export const createRouter = (onLogout: () => void) =>
  createBrowserRouter([
    {
      path: '/',
      element: <MainLayout onLogout={onLogout} />,
      children: [
        { index: true, element: <Navigate to="/dashboard" replace /> },
        { path: 'dashboard', element: <DashboardPage /> },
        { path: 'accounts', element: <AccountsPage /> },
        { path: 'groups', element: <GroupManagePage /> },
        { path: 'groups/:groupId', element: <GroupDetailPage /> },
        { path: 'sms', element: <SmsPage /> },
        { path: 'settings', element: <SettingsPage /> },
        { path: '*', element: <Navigate to="/dashboard" replace /> },
      ],
    },
  ]);
