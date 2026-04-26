import React from 'react'
import { Button, Card, Checkbox, Dropdown, Flex, Tag, Tooltip, Typography, theme as antTheme } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CopyOutlined,
  CrownOutlined,
  DownloadOutlined,
  FileTextOutlined,
  GoogleOutlined,
  LinkOutlined,
  LoadingOutlined,
  LoginOutlined,
  MoreOutlined,
  PhoneOutlined,
  PoweroffOutlined,
  SafetyCertificateOutlined,
  StopOutlined,
  TeamOutlined,
  UndoOutlined,
  UserDeleteOutlined,
  UserOutlined,
} from '@ant-design/icons'

import {
  getVisibleAutomationOperations,
  type AutomationOperationDefinition,
} from '@/features/automation/operationMeta'
import { getAutomationOperationIcon } from '@/features/automation/operationPresentation'
import { maskEmail } from '@/utils/mask'
import type { Account } from '@/types'
import { isAbnormalStatus } from '@/constants/accountStatus'
import { useAccountOpState } from '@/contexts/automationContext'

const { Text } = Typography

interface GroupAccountCardProps {
  account: Account
  isMain: boolean
  isMasked: boolean
  isSelected: boolean
  isRunning: boolean
  isBrowserLoading: boolean
  isCheckedForUpload: boolean
  onClearStatus: (accountId: number) => void
  onCopyOAuthJson: (accountId: number) => void
  onCopyText: (text: string, label: string) => void
  onCopyTOTP: (secret: string) => void
  onDownloadOAuth: (accountId: number) => void
  onMarkUnusable: (accountId: number) => void
  onOAuth: (accountId: number) => void
  onOperationClick: (accountId: number, operation: AutomationOperationDefinition) => void
  onPhoneVerify: (accountId: number, validationUrl: string) => void
  onRemoveFromGroup: (accountId: number) => void
  onSelect: (accountId: number) => void
  onToggleBrowser: (accountId: number, running: boolean) => void
  onToggleUploadSelect: (accountId: number) => void
}

export function GroupAccountCard({
  account,
  isMain,
  isMasked,
  isSelected,
  isRunning,
  isBrowserLoading,
  isCheckedForUpload,
  onClearStatus,
  onCopyOAuthJson,
  onCopyText,
  onCopyTOTP,
  onDownloadOAuth,
  onMarkUnusable,
  onOAuth,
  onOperationClick,
  onPhoneVerify,
  onRemoveFromGroup,
  onSelect,
  onToggleBrowser,
  onToggleUploadSelect,
}: GroupAccountCardProps) {
  const { token } = antTheme.useToken()
  const opState = useAccountOpState(account.id)
  const isPending = Boolean(account.is_family_pending)
  const visibleOps = isPending ? [] : getVisibleAutomationOperations(account)
  const isThisAccountRunning = Boolean(opState?.runningOpKey)
  const runningOpKey = opState?.runningOpKey ?? null
  const memberCount = account.family_member_count ?? 0

  return (
    <div
      key={account.id}
      style={{ marginBottom: 6, cursor: 'pointer' }}
      onClick={() => onSelect(account.id)}
    >
      <Card
        size="small"
        className="hover-card"
        style={{
          borderRadius: 8,
          border: isSelected
            ? '2px solid #1677ff'
            : isPending
              ? '1px dashed #ffd591'
              : isMain
                ? '1px solid #ffd666'
                : isRunning
                  ? '1px solid #91caff'
                  : `1px solid ${token.colorBorderSecondary}`,
          transition: 'all 0.2s',
          opacity: isPending ? 0.8 : 1,
        }}
        styles={{ body: { padding: '8px 10px 6px' } }}
      >
        <Flex justify="space-between" align="flex-start" style={{ marginBottom: 4 }}>
          <Flex align="center" gap={6} style={{ flex: 1, minWidth: 0 }}>
            <Tooltip title={account.has_oauth_credential ? '' : '无 OAuth 凭证'}>
              <Checkbox
                checked={isCheckedForUpload}
                disabled={!account.has_oauth_credential}
                onChange={() => onToggleUploadSelect(account.id)}
                onClick={(event) => event.stopPropagation()}
                style={{ flexShrink: 0 }}
              />
            </Tooltip>
            <GoogleOutlined style={{ color: '#4285f4', fontSize: 14, flexShrink: 0 }} />
            <Tooltip title="点击复制邮箱">
              <Text
                strong
                ellipsis
                style={{ fontSize: 12, maxWidth: '100%', cursor: 'pointer' }}
                onClick={(event) => {
                  event.stopPropagation()
                  onCopyText(account.email, '邮箱')
                }}
              >
                {isMasked ? maskEmail(account.email) : account.email}
              </Text>
            </Tooltip>
          </Flex>
          <Dropdown
            menu={{
              items: isMain
                ? []
                : [{
                    key: 'remove-from-group',
                    icon: <UserDeleteOutlined />,
                    label: '从分组移除',
                    danger: true,
                    onClick: () => onRemoveFromGroup(account.id),
                  }],
            }}
            trigger={['click']}
          >
            <Button
              type="text"
              size="small"
              icon={<MoreOutlined style={{ color: '#8c8c8c' }} />}
              style={{ flexShrink: 0 }}
              onClick={(event) => event.stopPropagation()}
            />
          </Dropdown>
        </Flex>

        <Flex gap={4} align="center" wrap style={{ marginBottom: 4 }}>
          {isMain ? (
            <Tag color="gold" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
              <CrownOutlined style={{ marginRight: 2 }} />创建者
            </Tag>
          ) : isPending ? (
            <Tag color="orange" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
              <ClockCircleOutlined style={{ marginRight: 2 }} />待接受
            </Tag>
          ) : (
            <Tag color="blue" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
              <UserOutlined style={{ marginRight: 2 }} />成员
            </Tag>
          )}
          {isMain && memberCount > 0 ? (
            <Tag color="default" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>
              <TeamOutlined style={{ marginRight: 2 }} />{Math.max(memberCount - 1, 0)}/5
            </Tag>
          ) : null}
          {account.subscription_status === 'ultra' ? (
            <Tag color="purple" style={{ margin: 0, fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>Ultra</Tag>
          ) : null}
          {isRunning ? (
            <Tag color="blue" style={{ margin: '0 0 0 auto', fontSize: 10, lineHeight: '16px', padding: '0 4px' }}>运行中</Tag>
          ) : null}
          {isThisAccountRunning ? <LoadingOutlined style={{ color: '#1677ff', fontSize: 11, marginLeft: 'auto' }} /> : null}
        </Flex>

        <Flex gap={3} wrap onClick={(event) => event.stopPropagation()}>
          {isPending ? (
            <>
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
                  onClick={() => onToggleBrowser(account.id, isRunning)}
                  style={{ padding: '0 4px' }}
                />
              </Tooltip>
              {account.totp_secret ? (
                <Tooltip title="复制 2FA">
                  <Button type="text" size="small" icon={<CopyOutlined style={{ color: '#52c41a' }} />} onClick={() => onCopyTOTP(account.totp_secret!)} style={{ padding: '0 4px' }} />
                </Tooltip>
              ) : null}
              {account.password ? (
                <Tooltip title="复制密码">
                  <Button type="text" size="small" icon={<CopyOutlined style={{ color: '#faad14' }} />} onClick={() => onCopyText(account.password, '密码')} style={{ padding: '0 4px' }} />
                </Tooltip>
              ) : null}
              {isAbnormalStatus(account.status) ? (
                <Tooltip title="恢复正常">
                  <Button type="text" size="small" icon={<UndoOutlined style={{ color: '#52c41a' }} />} onClick={() => onClearStatus(account.id)} style={{ padding: '0 4px' }} />
                </Tooltip>
              ) : (
                <Tooltip title="标记无法使用">
                  <Button type="text" size="small" icon={<StopOutlined style={{ color: '#ff4d4f', opacity: 0.6 }} />} onClick={() => onMarkUnusable(account.id)} style={{ padding: '0 4px' }} />
                </Tooltip>
              )}
              <Tooltip title="接受邀请">
                <Button
                  type="text"
                  size="small"
                  disabled={isThisAccountRunning || !isRunning}
                  onClick={() => onOperationClick(account.id, {
                    key: 'family-accept',
                    label: '接受',
                    color: '#52c41a',
                    needBrowser: true,
                    role: 'no-group',
                  })}
                  style={{ padding: '0 4px' }}
                  icon={<CheckCircleOutlined style={{ color: !isThisAccountRunning && isRunning ? '#52c41a' : '#d9d9d9' }} />}
                />
              </Tooltip>
            </>
          ) : (
            <>
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
                  onClick={() => onToggleBrowser(account.id, isRunning)}
                  style={{ padding: '0 4px' }}
                />
              </Tooltip>
              {account.totp_secret ? (
                <Tooltip title="复制 2FA">
                  <Button type="text" size="small" icon={<CopyOutlined style={{ color: '#52c41a' }} />} onClick={() => onCopyTOTP(account.totp_secret!)} style={{ padding: '0 4px' }} />
                </Tooltip>
              ) : null}
              {account.password ? (
                <Tooltip title="复制密码">
                  <Button type="text" size="small" icon={<CopyOutlined style={{ color: '#faad14' }} />} onClick={() => onCopyText(account.password, '密码')} style={{ padding: '0 4px' }} />
                </Tooltip>
              ) : null}
              {isAbnormalStatus(account.status) ? (
                <Tooltip title="恢复正常">
                  <Button type="text" size="small" icon={<UndoOutlined style={{ color: '#52c41a' }} />} onClick={() => onClearStatus(account.id)} style={{ padding: '0 4px' }} />
                </Tooltip>
              ) : (
                <Tooltip title="标记无法使用">
                  <Button type="text" size="small" icon={<StopOutlined style={{ color: '#ff4d4f', opacity: 0.6 }} />} onClick={() => onMarkUnusable(account.id)} style={{ padding: '0 4px' }} />
                </Tooltip>
              )}
              <Tooltip title="OAuth 授权">
                <Button
                  type="text"
                  size="small"
                  disabled={isThisAccountRunning || !isRunning}
                  icon={
                    isThisAccountRunning && runningOpKey === 'oauth' ? (
                      <LoadingOutlined style={{ color: '#1677ff' }} />
                    ) : (
                      <SafetyCertificateOutlined style={{ color: isThisAccountRunning || !isRunning ? '#d9d9d9' : '#722ed1' }} />
                    )
                  }
                  onClick={() => onOAuth(account.id)}
                  style={{ padding: '0 4px' }}
                />
              </Tooltip>
              {account.has_oauth_credential ? (
                <>
                  <Tooltip title="复制 OAuth JSON"><Button type="text" size="small" icon={<FileTextOutlined style={{ color: '#1890ff' }} />} onClick={() => onCopyOAuthJson(account.id)} style={{ padding: '0 4px' }} /></Tooltip>
                  <Tooltip title="下载 OAuth 凭证"><Button type="text" size="small" icon={<DownloadOutlined style={{ color: '#13c2c2' }} />} onClick={() => onDownloadOAuth(account.id)} style={{ padding: '0 4px' }} /></Tooltip>
                </>
              ) : null}
              {account.validation_url ? (
                <>
                  <Tooltip title="复制验证链接"><Button type="text" size="small" icon={<LinkOutlined style={{ color: '#ff4d4f' }} />} onClick={() => onCopyText(account.validation_url!, '验证链接')} style={{ padding: '0 4px' }} /></Tooltip>
                  <Tooltip title="自动接码验证">
                    <Button
                      type="text"
                      size="small"
                      disabled={isThisAccountRunning || !isRunning}
                      icon={
                        isThisAccountRunning && runningOpKey === 'phone-verify' ? (
                          <LoadingOutlined style={{ color: '#1677ff' }} />
                        ) : (
                          <PhoneOutlined style={{ color: isThisAccountRunning || !isRunning ? '#d9d9d9' : '#fa8c16' }} />
                        )
                      }
                      onClick={() => onPhoneVerify(account.id, account.validation_url!)}
                      style={{ padding: '0 4px' }}
                    />
                  </Tooltip>
                </>
              ) : null}
              {visibleOps.map((operation) => {
                const needsBrowser = operation.needBrowser !== false
                const disabled = isThisAccountRunning || (needsBrowser && !isRunning)
                const isThisOpRunning = isThisAccountRunning && runningOpKey === operation.key
                const operationIcon = getAutomationOperationIcon(operation.key)

                return (
                  <Tooltip key={operation.key} title={operation.label}>
                    <Button
                      type="text"
                      size="small"
                      disabled={disabled && !isThisOpRunning}
                      onClick={() => onOperationClick(account.id, operation)}
                      style={{ padding: '0 4px' }}
                      icon={
                        isThisOpRunning ? (
                          <LoadingOutlined style={{ color: '#1677ff' }} />
                        ) : React.isValidElement(operationIcon) ? (
                          React.cloneElement(
                            operationIcon as React.ReactElement<{ style?: React.CSSProperties }>,
                            { style: { color: disabled ? '#d9d9d9' : operation.color } },
                          )
                        ) : (
                          operationIcon
                        )
                      }
                    />
                  </Tooltip>
                )
              })}
            </>
          )}
        </Flex>
      </Card>
    </div>
  )
}
