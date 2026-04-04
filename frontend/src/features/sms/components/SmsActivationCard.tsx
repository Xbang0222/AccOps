import { Button, Card, Space, Tag, Typography, Flex } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, CopyOutlined, LoadingOutlined } from '@ant-design/icons'

import type { ActiveSmsActivation } from '../useSmsPageController'

const { Text } = Typography

interface SmsActivationCardProps {
  activation: ActiveSmsActivation
  polling: boolean
  onCancel: () => void
  onClear: () => void
  onCopy: (text: string, label: string) => void
  onFinish: () => void
}

export function SmsActivationCard({
  activation,
  polling,
  onCancel,
  onClear,
  onCopy,
  onFinish,
}: SmsActivationCardProps) {
  return (
    <Card size="small" style={{ marginBottom: 12, flexShrink: 0 }} styles={{ body: { padding: '8px 16px' } }}>
      <Flex gap={16} align="center" wrap>
        <Flex gap={6} align="center">
          <Text type="secondary">号码:</Text>
          <Text strong copyable style={{ fontFamily: 'monospace' }}>{activation.phone_number}</Text>
          {activation.cost ? <Tag color="blue">${activation.cost}</Tag> : null}
          <Tag>{activation.service}</Tag>
        </Flex>
        <Flex gap={6} align="center">
          <Text type="secondary">验证码:</Text>
          {activation.code ? (
            <Tag
              color="green"
              style={{ fontSize: 16, padding: '2px 12px', cursor: 'pointer', fontFamily: 'monospace' }}
              onClick={() => onCopy(activation.code, '验证码')}
            >
              {activation.code} <CopyOutlined style={{ marginLeft: 6 }} />
            </Tag>
          ) : polling ? (
            <Space size={4}><LoadingOutlined style={{ color: '#1677ff' }} /><Text type="secondary">等待中...</Text></Space>
          ) : (
            <Text type="secondary">-</Text>
          )}
        </Flex>
        <Space size={4} style={{ marginLeft: 'auto' }}>
          {activation.status === 'code_received' ? (
            <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={onFinish}>完成</Button>
          ) : null}
          {['pending', 'code_received'].includes(activation.status) ? (
            <Button size="small" danger icon={<CloseCircleOutlined />} onClick={onCancel}>取消</Button>
          ) : null}
          {['finished', 'cancelled'].includes(activation.status) ? (
            <Button size="small" onClick={onClear}>清除</Button>
          ) : null}
        </Space>
      </Flex>
    </Card>
  )
}
