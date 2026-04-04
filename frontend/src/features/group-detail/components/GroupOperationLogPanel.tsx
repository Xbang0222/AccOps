import { Button, Flex, Tag, Typography } from 'antd'
import { GoogleOutlined, LoadingOutlined, StopOutlined } from '@ant-design/icons'

import type { Account } from '@/types'
import type { AccountOpState } from '../utils'

const { Text } = Typography

interface GroupOperationLogPanelProps {
  account: Account | null
  opState: AccountOpState | null
  onCancel: () => void
}

export function GroupOperationLogPanel({
  account,
  opState,
  onCancel,
}: GroupOperationLogPanelProps) {
  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        background: '#fff',
        minHeight: 0,
      }}
    >
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', flexShrink: 0 }}>
        {account ? (
          <Flex align="center" gap={6}>
            <GoogleOutlined style={{ color: '#4285f4', fontSize: 14 }} />
            <Text strong style={{ fontSize: 13 }}>{account.email}</Text>
            {opState?.runningOpKey ? <Tag color="processing" style={{ margin: 0 }}>{opState.runningOpKey}</Tag> : null}
            {opState?.runningOpKey ? (
              <Button size="small" danger icon={<StopOutlined />} onClick={onCancel}>
                取消
              </Button>
            ) : null}
          </Flex>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>点击左侧卡片查看日志</Text>
        )}
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 12px',
          fontFamily: "'SF Mono', Consolas, monospace",
          fontSize: 12,
          lineHeight: '20px',
        }}
      >
        {opState ? (
          <>
            {opState.steps.length === 0 && opState.runningOpKey ? (
              <Flex align="center" gap={6}>
                <LoadingOutlined style={{ color: '#1677ff', fontSize: 12 }} />
                <Text type="secondary" style={{ fontSize: 12 }}>等待执行...</Text>
              </Flex>
            ) : null}

            {opState.steps.map((step, index) => (
              <div key={`${step.name}-${index}`} style={{ marginBottom: 2 }}>
                <span
                  style={{
                    color:
                      step.status === 'fail'
                        ? '#ff4d4f'
                        : step.status === 'ok'
                          ? '#52c41a'
                          : step.status === 'skip'
                            ? '#faad14'
                            : '#333',
                    fontWeight: 500,
                  }}
                >
                  {step.name}
                </span>
                {step.message ? (
                  /^https?:\/\//.test(step.message) ? (
                    <a
                      href={step.message}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ marginLeft: 8, fontSize: 11, color: '#1677ff', wordBreak: 'break-all' }}
                      title={step.message}
                    >
                      {step.message.length > 60 ? `${step.message.slice(0, 60)}...` : step.message}
                    </a>
                  ) : (
                    <span style={{ color: '#999', marginLeft: 8 }}>{step.message}</span>
                  )
                ) : null}
                {step.duration_ms ? <span style={{ color: '#bbb', marginLeft: 6 }}>({step.duration_ms}ms)</span> : null}
              </div>
            ))}

            {opState.resultMsg && !opState.runningOpKey ? (
              <div
                style={{
                  marginTop: 8,
                  padding: '6px 10px',
                  borderRadius: 6,
                  fontSize: 12,
                  background: opState.resultSuccess ? '#f6ffed' : '#fff2f0',
                  border: `1px solid ${opState.resultSuccess ? '#b7eb8f' : '#ffa39e'}`,
                }}
              >
                {opState.resultMsg}
              </div>
            ) : null}
          </>
        ) : (
          <Flex justify="center" align="center" style={{ height: '100%' }}>
            <Text type="secondary" style={{ color: '#d9d9d9' }}>暂无日志</Text>
          </Flex>
        )}
      </div>
    </div>
  )
}
