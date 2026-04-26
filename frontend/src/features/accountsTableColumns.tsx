import { Button, Flex, Space, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  ClockCircleOutlined,
  CopyOutlined,
  CrownOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  KeyOutlined,
  LoadingOutlined,
  LockOutlined,
  LoginOutlined,
  PoweroffOutlined,
  StopOutlined,
  UndoOutlined,
  UserOutlined,
} from '@ant-design/icons'

import type { Account } from '@/types'
import { isAbnormalPoolStatus } from '@/constants/accountStatus'
import { maskEmail } from '@/utils/mask'

const { Text } = Typography

// AntD Table size='small' 的 rowSelection 复选框列实测渲染宽度（16px checkbox + 左右各 8px padding）
export const SELECTION_COLUMN_WIDTH = 32

interface CreateAccountTableColumnsOptions {
  browserLoading: Set<number>
  browserRunning: Set<number>
  masked: boolean
  onClearStatus: (id: number) => void
  onCopyFullAccount: (account: Account) => void
  onCopyText: (text: string, label: string) => void
  onCopyTotpCode: (secret: string) => void
  onDelete: (id: number) => void
  onEdit: (account: Account) => void
  onExportAccount: (account: Account) => void
  onLaunchAndLogin: (account: Account) => void
  onMarkUnusable: (id: number) => void
  onStopBrowser: (accountId: number) => void
}

export function createAccountTableColumns({
  browserLoading,
  browserRunning,
  masked,
  onClearStatus,
  onCopyFullAccount,
  onCopyText,
  onCopyTotpCode,
  onDelete,
  onEdit,
  onExportAccount,
  onLaunchAndLogin,
  onMarkUnusable,
  onStopBrowser,
}: CreateAccountTableColumnsOptions): ColumnsType<Account> {
  return [
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      width: 280,
      ellipsis: true,
      sorter: true,
      render: (email: string, record) => (
        <Flex align="center" gap={6}>
          <Text style={{ cursor: 'pointer', fontSize: 13 }} onClick={() => onCopyText(email, '邮箱')}>
            {masked ? maskEmail(email) : email}
          </Text>
          {record.subscription_status === 'ultra' ? (
            <Tag color="purple" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px', cursor: 'default' }}>
              Ultra
            </Tag>
          ) : null}
          {record.subscription_status === 'ultra' && record.subscription_expiry ? (
            <Tag color="default" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px', cursor: 'default' }}>
              重置于 {record.subscription_expiry}
            </Tag>
          ) : null}
          {record.is_family_owner ? <CrownOutlined style={{ color: '#faad14', fontSize: 12 }} /> : null}
          {record.is_family_pending ? <ClockCircleOutlined style={{ color: '#fa8c16', fontSize: 12 }} /> : null}
        </Flex>
      ),
    },
    {
      title: '标签',
      key: 'tags',
      width: 180,
      render: (_, record) => {
        const list = record.tags ?? []
        if (list.length === 0) {
          return <Text type="secondary" style={{ fontSize: 12 }}>-</Text>
        }
        return (
          <Flex gap={4} wrap>
            {list.map((t) => (
              <Tag key={t.id} style={{ margin: 0, fontSize: 11 }}>{t.name}</Tag>
            ))}
          </Flex>
        )
      },
    },
    {
      title: '家庭组',
      key: 'role',
      width: 110,
      render: (_, record) => {
        if (!record.family_group_id) {
          return <Text type="secondary" style={{ fontSize: 12 }}>-</Text>
        }
        if (record.is_family_pending) {
          return <Tag color="orange" style={{ margin: 0, fontSize: 11 }}><ClockCircleOutlined style={{ marginRight: 2 }} />待接受</Tag>
        }
        const memberCount = record.family_member_count ?? 0
        const memberLabel = memberCount > 0 ? ` ${Math.max(memberCount - 1, 0)}/5` : ''
        if (record.is_family_owner) {
          return <Tag color="gold" style={{ margin: 0, fontSize: 11 }}><CrownOutlined style={{ marginRight: 2 }} />管理{memberLabel}</Tag>
        }
        return <Tag color="blue" style={{ margin: 0, fontSize: 11 }}><UserOutlined style={{ marginRight: 2 }} />成员</Tag>
      },
    },
    {
      title: '备注',
      dataIndex: 'notes',
      key: 'notes',
      width: 160,
      ellipsis: true,
      render: (notes: string | null) =>
        notes ? <Text type="secondary" style={{ fontSize: 12 }}>{notes}</Text> : null,
    },
    {
      title: '状态',
      dataIndex: 'retired_at',
      key: 'use_status',
      width: 100,
      render: (_: unknown, record: Account) => {
        const poolStatus = record.pool_status || ''
        if (poolStatus === 'unusable') {
          return <Tag color="red" style={{ margin: 0, fontSize: 11 }}>无法使用</Tag>
        }
        if (poolStatus === 'retired') {
          return <Tag color="default" style={{ margin: 0, fontSize: 11 }}>废弃号</Tag>
        }
        return null
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 100,
      sorter: true,
      render: (value: string | null) => {
        if (!value) {
          return null
        }
        const date = new Date(value)
        return (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}{' '}
            {date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
          </Text>
        )
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 272,
      render: (_, record) => {
        const isRunning = browserRunning.has(record.id)
        const isBrowserLoading = browserLoading.has(record.id)

        return (
          <Space size={0}>
            <Tooltip title={isBrowserLoading ? '处理中' : isRunning ? '关闭浏览器' : '启动并登录'}>
              <Button
                type="text"
                size="small"
                disabled={isBrowserLoading}
                icon={
                  isBrowserLoading ? (
                    <LoadingOutlined style={{ color: '#1677ff' }} />
                  ) : isRunning ? (
                    <PoweroffOutlined style={{ color: '#ff4d4f' }} />
                  ) : (
                    <LoginOutlined style={{ color: '#4285f4' }} />
                  )
                }
                onClick={() => (isRunning ? onStopBrowser(record.id) : onLaunchAndLogin(record))}
              />
            </Tooltip>
            {record.password ? (
              <Tooltip title="复制密码">
                <Button type="text" size="small" icon={<LockOutlined style={{ color: '#faad14' }} />} onClick={() => onCopyText(record.password, '密码')} />
              </Tooltip>
            ) : null}
            {record.totp_secret ? (
              <Tooltip title="复制 2FA 验证码">
                <Button type="text" size="small" icon={<KeyOutlined style={{ color: '#52c41a' }} />} onClick={() => onCopyTotpCode(record.totp_secret!)} />
              </Tooltip>
            ) : null}
            <Tooltip title="复制全部信息">
              <Button type="text" size="small" icon={<CopyOutlined style={{ color: '#1677ff' }} />} onClick={() => onCopyFullAccount(record)} />
            </Tooltip>
            <Tooltip title="导出此账号 (.txt)">
              <Button type="text" size="small" icon={<DownloadOutlined style={{ color: '#13c2c2' }} />} onClick={() => onExportAccount(record)} />
            </Tooltip>
            <Tooltip title="编辑">
              <Button type="text" size="small" icon={<EditOutlined style={{ color: '#8c8c8c' }} />} onClick={() => onEdit(record)} />
            </Tooltip>
            {isAbnormalPoolStatus(record.pool_status) ? (
              <Tooltip title="恢复正常">
                <Button type="text" size="small" icon={<UndoOutlined style={{ color: '#52c41a' }} />} onClick={() => onClearStatus(record.id)} />
              </Tooltip>
            ) : (
              <Tooltip title="标记无法使用">
                <Button type="text" size="small" icon={<StopOutlined style={{ color: '#ff4d4f', opacity: 0.6 }} />} onClick={() => onMarkUnusable(record.id)} />
              </Tooltip>
            )}
            <Tooltip title="删除">
              <Button type="text" size="small" icon={<DeleteOutlined style={{ color: '#ff4d4f' }} />} onClick={() => onDelete(record.id)} />
            </Tooltip>
          </Space>
        )
      },
    },
  ]
}
