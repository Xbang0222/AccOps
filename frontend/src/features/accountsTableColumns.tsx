import { Button, Flex, Space, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  CopyOutlined,
  CrownOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  LoadingOutlined,
  LockOutlined,
  LoginOutlined,
  PoweroffOutlined,
  TeamOutlined,
  UserOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'

import type { Account } from '@/types'
import { maskEmail } from '@/utils/mask'

const { Text } = Typography

const TAG_COLORS = [
  'blue', 'purple', 'cyan', 'geekblue', 'magenta', 'volcano', 'gold', 'green',
]

const tagColorMap = new Map<string, string>()

function getTagColor(tag: string) {
  if (!tagColorMap.has(tag)) {
    tagColorMap.set(tag, TAG_COLORS[tagColorMap.size % TAG_COLORS.length])
  }
  return tagColorMap.get(tag)!
}

interface CreateAccountTableColumnsOptions {
  browserLoading: Set<number>
  browserRunning: Set<number>
  masked: boolean
  onCopyFullAccount: (account: Account) => void
  onCopyText: (text: string, label: string) => void
  onCopyTotpCode: (secret: string) => void
  onDelete: (id: number) => void
  onEdit: (account: Account) => void
  onLaunchAndLogin: (account: Account) => void
  onStopBrowser: (accountId: number) => void
}

export function createAccountTableColumns({
  browserLoading,
  browserRunning,
  masked,
  onCopyFullAccount,
  onCopyText,
  onCopyTotpCode,
  onDelete,
  onEdit,
  onLaunchAndLogin,
  onStopBrowser,
}: CreateAccountTableColumnsOptions): ColumnsType<Account> {
  return [
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      ellipsis: true,
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
      title: '分组',
      key: 'group',
      width: 140,
      render: (_, record) => (
        <Flex gap={4} align="center" wrap>
          {record.group_name ? <Tag style={{ margin: 0, fontSize: 11 }}>{record.group_name}</Tag> : null}
          {record.family_group_id && (record.family_member_count ?? 0) > 0 ? (
            <Tag color="default" style={{ margin: 0, fontSize: 11 }}>
              <TeamOutlined style={{ marginRight: 2 }} />{Math.max((record.family_member_count ?? 0) - 1, 0)}/5
            </Tag>
          ) : null}
        </Flex>
      ),
    },
    {
      title: '角色',
      key: 'role',
      width: 80,
      render: (_, record) => {
        if (!record.family_group_id) {
          return <Text type="secondary" style={{ fontSize: 12 }}>-</Text>
        }
        if (record.is_family_pending) {
          return <Tag color="orange" style={{ margin: 0, fontSize: 11 }}><ClockCircleOutlined style={{ marginRight: 2 }} />待接受</Tag>
        }
        if (record.is_family_owner) {
          return <Tag color="gold" style={{ margin: 0, fontSize: 11 }}><CrownOutlined style={{ marginRight: 2 }} />管理</Tag>
        }
        return <Tag color="blue" style={{ margin: 0, fontSize: 11 }}><UserOutlined style={{ marginRight: 2 }} />成员</Tag>
      },
    },
    {
      title: '地区',
      dataIndex: 'country_cn',
      key: 'country',
      width: 80,
      render: (_: string | null, record: Account) => {
        const cn = record.country_cn
        const en = record.country
        if (!cn && !en) {
          return null
        }
        return <Tooltip title={en}><Text style={{ fontSize: 12 }}>{cn || en}</Text></Tooltip>
      },
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 140,
      render: (tags: string | null) =>
        tags ? (
          <Flex gap={4} wrap>
            {tags.split(',').map((tag, index) => (
              <Tag key={`${tag}-${index}`} color={getTagColor(tag.trim())} style={{ margin: 0, fontSize: 11 }}>
                {tag.trim()}
              </Tag>
            ))}
          </Flex>
        ) : null,
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
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 100,
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
      width: 210,
      fixed: 'right',
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
            <Tooltip title="编辑">
              <Button type="text" size="small" icon={<EditOutlined style={{ color: '#8c8c8c' }} />} onClick={() => onEdit(record)} />
            </Tooltip>
            <Tooltip title="删除">
              <Button type="text" size="small" icon={<DeleteOutlined style={{ color: '#ff4d4f' }} />} onClick={() => onDelete(record.id)} />
            </Tooltip>
          </Space>
        )
      },
    },
  ]
}
