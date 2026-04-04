import {
  CheckCircleOutlined,
  LogoutOutlined,
  SwapOutlined,
  SyncOutlined,
  TeamOutlined,
  UserAddOutlined,
  UserDeleteOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'

import type { AutomationOperationDefinition } from './operationMeta'

const OPERATION_ICON_MAP: Record<AutomationOperationDefinition['key'], ReactNode> = {
  'family-discover': <SyncOutlined />,
  'family-create': <TeamOutlined />,
  'family-invite': <UserAddOutlined />,
  'family-accept': <CheckCircleOutlined />,
  'family-remove': <UserDeleteOutlined />,
  'family-leave': <LogoutOutlined />,
  replace: <SwapOutlined />,
}

const PANEL_BACKGROUND_MAP: Record<AutomationOperationDefinition['key'], string> = {
  'family-discover': '#e6f4ff',
  'family-create': '#f9f0ff',
  'family-invite': '#e6fffb',
  'family-accept': '#f6ffed',
  'family-remove': '#fff2f0',
  'family-leave': '#fff7e6',
  replace: '#f9f0ff',
}

export function getAutomationOperationIcon(key: AutomationOperationDefinition['key']): ReactNode {
  return OPERATION_ICON_MAP[key]
}

export function getAutomationOperationPanelBackground(
  key: AutomationOperationDefinition['key'],
): string {
  return PANEL_BACKGROUND_MAP[key]
}
