import { Button, Card, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, ReloadOutlined } from '@ant-design/icons'

import type { SmsActivationRecord, SmsProviderConfig } from '@/api/sms'

import { STATUS_MAP } from '../constants'

const { Text } = Typography

interface SmsHistoryCardProps {
  activeProvider?: SmsProviderConfig
  history: SmsActivationRecord[]
  historyLoading: boolean
  historyPage: number
  historyTotal: number
  onCopy: (text: string, label: string) => void
  onFinish: (record: SmsActivationRecord) => void
  onPageChange: (page: number) => void
  onRefresh: () => void
  onCancel: (record: SmsActivationRecord) => void
}

export function SmsHistoryCard({
  activeProvider,
  history,
  historyLoading,
  historyPage,
  historyTotal,
  onCopy,
  onFinish,
  onPageChange,
  onRefresh,
  onCancel,
}: SmsHistoryCardProps) {
  return (
    <Card
      size="small"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
      title="接码记录"
      extra={(
        <Space size={8}>
          {activeProvider ? <Tag color="green">${activeProvider.balance || '—'}</Tag> : null}
          <Button size="small" type="text" icon={<ReloadOutlined />} onClick={onRefresh} />
        </Space>
      )}
      styles={{ body: { flex: 1, padding: 0, overflow: 'hidden' } }}
    >
      <Table
        dataSource={history}
        rowKey="id"
        size="small"
        loading={historyLoading}
        scroll={{ y: 'calc(100vh - 220px)' }}
        pagination={{
          current: historyPage,
          total: historyTotal,
          pageSize: 15,
          size: 'small',
          showTotal: (total) => `共 ${total} 条`,
          onChange: onPageChange,
        }}
        columns={[
          {
            title: '号码',
            dataIndex: 'phone_number',
            width: 155,
            render: (value: string) => (
              <Tooltip title="点击复制">
                <Text style={{ cursor: 'pointer', fontFamily: 'monospace', fontSize: 12 }} onClick={() => onCopy(value, '号码')}>{value}</Text>
              </Tooltip>
            ),
          },
          {
            title: '验证码',
            dataIndex: 'sms_code',
            width: 95,
            render: (value: string) =>
              value ? (
                <Tag color="green" style={{ cursor: 'pointer', fontFamily: 'monospace' }} onClick={() => onCopy(value, '验证码')}>
                  {value}
                </Tag>
              ) : '-',
          },
          { title: '服务', dataIndex: 'service', width: 70, render: (value: string) => <Tag>{value}</Tag> },
          { title: '费用', dataIndex: 'cost', width: 70, render: (value: string) => value ? `$${value}` : '-' },
          {
            title: '状态',
            dataIndex: 'status',
            width: 95,
            render: (value: string) => {
              const status = STATUS_MAP[value] || { color: 'default', label: value }
              return <Tag color={status.color}>{status.label}</Tag>
            },
          },
          {
            title: '时间',
            dataIndex: 'created_at',
            width: 150,
            render: (value: string) => (value ? new Date(value).toLocaleString('zh-CN') : '-'),
          },
          {
            title: '操作',
            width: 100,
            render: (_value: unknown, record: SmsActivationRecord) => (
              <Space size={4}>
                {record.status === 'pending' ? (
                  <Tooltip title="取消">
                    <Button type="text" size="small" danger icon={<CloseCircleOutlined />} onClick={() => onCancel(record)} />
                  </Tooltip>
                ) : null}
                {record.status === 'code_received' ? (
                  <>
                    <Tooltip title="完成">
                      <Button type="text" size="small" icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />} onClick={() => onFinish(record)} />
                    </Tooltip>
                    <Tooltip title="取消">
                      <Button type="text" size="small" danger icon={<CloseCircleOutlined />} onClick={() => onCancel(record)} />
                    </Tooltip>
                  </>
                ) : null}
              </Space>
            ),
          },
        ]}
      />
    </Card>
  )
}
