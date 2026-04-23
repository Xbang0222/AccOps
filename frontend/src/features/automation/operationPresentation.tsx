import {
  CheckCircleOutlined,
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
  'family-swap': <SwapOutlined />,
}

export function getAutomationOperationIcon(key: AutomationOperationDefinition['key']): ReactNode {
  return OPERATION_ICON_MAP[key]
}
