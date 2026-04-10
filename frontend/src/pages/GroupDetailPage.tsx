import React, { useState, useCallback } from 'react'
import { App, Button, Empty, Flex, Modal, Select, Spin, Tag, Tooltip, Typography } from 'antd'
import { ArrowLeftOutlined, DatabaseOutlined, EyeInvisibleOutlined, EyeOutlined, StopOutlined, TeamOutlined, UndoOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import { getAvailableAccounts, getPoolAccounts, addToPool, removeFromPool, markPoolUnusable, clearPoolStatus } from '@/api'
import { GroupAccountCard } from '@/features/group-detail/components/GroupAccountCard'
import { GroupOperationLogPanel } from '@/features/group-detail/components/GroupOperationLogPanel'
import { GroupOperationModal } from '@/features/group-detail/components/GroupOperationModal'
import { useGroupDetailController } from '@/features/group-detail/useGroupDetailController'
import type { Account } from '@/types'

const { Text } = Typography

const GroupDetailPage: React.FC = () => {
  const { groupId: groupIdParam } = useParams<{ groupId: string }>()
  const navigate = useNavigate()
  const groupId = Number(groupIdParam)
  const controller = useGroupDetailController(groupId)
  const { message: msg } = App.useApp()

  // 号池管理状态
  const [poolVisible, setPoolVisible] = useState(false)
  const [poolAccounts, setPoolAccounts] = useState<Account[]>([])
  const [poolLoading, setPoolLoading] = useState(false)
  const [addPoolVisible, setAddPoolVisible] = useState(false)
  const [globalAvailable, setGlobalAvailable] = useState<{ label: string; value: number }[]>([])
  const [selectedPoolIds, setSelectedPoolIds] = useState<number[]>([])

  const loadPool = useCallback(async () => {
    setPoolLoading(true)
    try {
      const { data } = await getPoolAccounts(groupId)
      setPoolAccounts(data.accounts)
    } catch { /* noop */ }
    finally { setPoolLoading(false) }
  }, [groupId])

  const handleOpenPool = useCallback(() => {
    setPoolVisible(true)
    void loadPool()
  }, [loadPool])

  const handleAddToPool = useCallback(async () => {
    if (selectedPoolIds.length === 0) return
    try {
      await addToPool(groupId, selectedPoolIds)
      msg.success(`已添加 ${selectedPoolIds.length} 个账号到号池`)
      setSelectedPoolIds([])
      setAddPoolVisible(false)
      void loadPool()
    } catch { msg.error('添加失败') }
  }, [groupId, loadPool, msg, selectedPoolIds])

  const handleRemoveFromPool = useCallback(async (accountIds: number[]) => {
    try {
      await removeFromPool(groupId, accountIds)
      msg.success('已从号池移除')
      void loadPool()
    } catch { msg.error('移除失败') }
  }, [groupId, loadPool, msg])

  const handleMarkUnusable = useCallback(async (accountId: number) => {
    try {
      await markPoolUnusable(accountId)
      msg.success('已标记为无法使用')
      void loadPool()
    } catch { msg.error('标记失败') }
  }, [loadPool, msg])

  const handleClearPoolStatus = useCallback(async (accountId: number) => {
    try {
      await clearPoolStatus(accountId)
      msg.success('已恢复正常状态')
      void loadPool()
    } catch { msg.error('操作失败') }
  }, [loadPool, msg])

  const handleOpenAddPool = useCallback(async () => {
    setAddPoolVisible(true)
    try {
      const { data } = await getAvailableAccounts()
      setGlobalAvailable(data.accounts.map((a) => ({ label: a.email, value: a.id })))
    } catch { /* noop */ }
  }, [])

  if (controller.loading && !controller.group) {
    return (
      <Flex justify="center" align="center" style={{ height: '100%' }}>
        <Spin size="large" />
      </Flex>
    )
  }

  if (!controller.group) {
    return (
      <Flex vertical align="center" justify="center" style={{ height: '100%' }}>
        <Empty description="分组不存在" />
        <Button type="link" onClick={() => navigate('/groups')}>返回列表</Button>
      </Flex>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Flex align="center" gap={12} style={{ marginBottom: 12, flexShrink: 0 }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/groups')} />
        <TeamOutlined style={{ color: '#722ed1', fontSize: 20 }} />
        <Text strong style={{ fontSize: 16 }}>{controller.group.name}</Text>
        <Tag color="default" style={{ fontSize: 12 }}>
          {Math.max((controller.group.accounts ?? []).length - 1, 0)} 个子号
        </Tag>
        {controller.group.notes ? <Text type="secondary" style={{ fontSize: 12 }}>{controller.group.notes}</Text> : null}
        <div style={{ flex: 1 }} />
        <Tooltip title="号池管理">
          <Button
            type="text"
            icon={<DatabaseOutlined />}
            onClick={handleOpenPool}
          />
        </Tooltip>
        <Tooltip title={controller.masked ? '显示邮箱' : '隐藏邮箱'}>
          <Button
            type="text"
            icon={controller.masked ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            onClick={() => controller.setMasked((previous) => !previous)}
          />
        </Tooltip>
      </Flex>

      <div style={{ flex: 1, display: 'flex', gap: 12, minHeight: 0 }}>
        <div style={{ width: 380, flexShrink: 0, overflowY: 'auto' }}>
          <Spin spinning={controller.loading}>
            {controller.sortedAccounts.length > 0 ? (
              controller.sortedAccounts.map((account) => (
                <GroupAccountCard
                  key={account.id}
                  account={account}
                  isMain={account.id === controller.group?.main_account_id}
                  isMasked={controller.masked}
                  isSelected={controller.selectedAccountId === account.id}
                  isRunning={controller.browserRunning.has(account.id)}
                  isBrowserLoading={controller.browserLoading.has(account.id)}
                  profileId={controller.profileMap[account.id]}
                  opState={controller.opStates[account.id]}
                  onClearBrowserData={controller.handleClearBrowserData}
                  onCopyOAuthJson={controller.handleCopyOAuthJson}
                  onCopyText={controller.copyToClipboard}
                  onCopyTOTP={controller.copyTOTPCode}
                  onDownloadOAuth={controller.handleDownloadOAuth}
                  onOAuth={controller.handleOAuth}
                  onOperationClick={controller.handleOperationClick}
                  onPhoneVerify={controller.handlePhoneVerify}
                  onRemoveFromGroup={controller.handleRemoveFromGroup}
                  onSelect={controller.setSelectedAccountId}
                  onToggleBrowser={controller.handleToggleBrowser}
                />
              ))
            ) : (
              <Empty description="暂无成员" style={{ marginTop: 60 }} />
            )}
          </Spin>
        </div>

        <GroupOperationLogPanel
          account={controller.selectedAccount}
          opState={controller.selectedOpState}
          onCancel={() => controller.automation.cancel(controller.selectedAccountId ?? undefined)}
        />
      </div>

      <GroupOperationModal
        activeOp={controller.activeOp}
        availableAccountOptions={controller.availableAccountOptions}
        availableAccountsLoading={controller.availableAccountsLoading}
        formValues={controller.formValues}
        memberOptions={controller.memberOptions}
        selectedEmails={controller.selectedEmails}
        swapManualEmails={controller.swapManualEmails}
        swapMode={controller.swapMode}
        onAvailableAccountSearch={controller.handleAvailableAccountSearch}
        onCancel={() => {
          controller.setActiveOp(null)
          controller.setActiveAccountId(null)
        }}
        onChangeFormValue={(name, value) => controller.setFormValues((previous) => ({ ...previous, [name]: value }))}
        onChangeSelectedEmails={controller.setSelectedEmails}
        onChangeSwapManualEmails={controller.setSwapManualEmails}
        onChangeSwapMode={controller.setSwapMode}
        onOk={controller.handleFieldModalOk}
        onSearchEmails={controller.handleEmailSearch}
        onSelectAllMembers={controller.handleSelectAllMembers}
      />

      {/* 号池管理弹窗 */}
      <Modal
        title={`号池管理 — ${controller.group.name}`}
        open={poolVisible}
        onCancel={() => setPoolVisible(false)}
        footer={[
          <Button key="login" onClick={() => {
            if (controller.group?.main_account_id) {
              controller.automation.execute(
                controller.group.main_account_id,
                'pool-batch-login',
                {},
                'pool-batch-login',
              )
              setPoolVisible(false)
            }
          }}>批量登录</Button>,
          <Button key="add" type="primary" onClick={handleOpenAddPool}>添加账号到号池</Button>,
          <Button key="close" onClick={() => setPoolVisible(false)}>关闭</Button>,
        ]}
        width={560}
      >
        <Spin spinning={poolLoading}>
          {poolAccounts.length > 0 ? (
            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
              {poolAccounts.map((a) => {
                const useCount = a.pool_use_count ?? 0
                const poolStatus = a.pool_status || ''
                const isRetired = poolStatus === 'retired'
                const isUnusable = poolStatus === 'unusable'
                const lastUsed = a.pool_last_used_at
                const isUsedToday = lastUsed
                  && new Date(lastUsed).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
                    === new Date().toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })

                let statusTag: React.ReactNode
                if (isUnusable) {
                  statusTag = <Tag color="red" style={{ margin: 0, fontSize: 11 }}>无法使用</Tag>
                } else if (isRetired) {
                  statusTag = <Tag color="default" style={{ margin: 0, fontSize: 11 }}>废弃号</Tag>
                } else if (useCount >= 2) {
                  statusTag = <Tag color="default" style={{ margin: 0, fontSize: 11 }}>废弃号 (2/2)</Tag>
                } else if (isUsedToday && useCount > 0) {
                  statusTag = <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>今日可复用 ({useCount}/2)</Tag>
                } else if (useCount > 0) {
                  statusTag = <Tag color="default" style={{ margin: 0, fontSize: 11 }}>废弃号</Tag>
                } else {
                  statusTag = <Tag color="green" style={{ margin: 0, fontSize: 11 }}>可用</Tag>
                }

                return (
                  <Flex key={a.id} justify="space-between" align="center" style={{ padding: '6px 0', borderBottom: '1px solid #f0f0f0' }}>
                    <Text style={{ fontSize: 13 }}>{a.email}</Text>
                    <Flex gap={4} align="center">
                      {statusTag}
                      {!isUnusable && !isRetired && useCount < 2 ? (
                        <Tooltip title="标记为无法使用">
                          <Button size="small" type="text" icon={<StopOutlined style={{ color: '#ff4d4f' }} />} onClick={() => handleMarkUnusable(a.id)} />
                        </Tooltip>
                      ) : null}
                      {(isUnusable || isRetired) ? (
                        <Tooltip title="恢复正常">
                          <Button size="small" type="text" icon={<UndoOutlined style={{ color: '#52c41a' }} />} onClick={() => handleClearPoolStatus(a.id)} />
                        </Tooltip>
                      ) : null}
                      <Button size="small" type="text" danger onClick={() => handleRemoveFromPool([a.id])}>移除</Button>
                    </Flex>
                  </Flex>
                )
              })}
            </div>
          ) : (
            <Empty description="号池为空，请添加备用账号" style={{ margin: '20px 0' }} />
          )}
        </Spin>
      </Modal>

      {/* 添加到号池弹窗 */}
      <Modal
        title="添加账号到号池"
        open={addPoolVisible}
        onCancel={() => { setAddPoolVisible(false); setSelectedPoolIds([]); }}
        onOk={handleAddToPool}
        okText="添加"
        cancelText="取消"
        width={450}
      >
        <Select
          mode="multiple"
          style={{ width: '100%' }}
          placeholder="搜索并选择账号"
          value={selectedPoolIds}
          onChange={setSelectedPoolIds}
          options={globalAvailable}
          optionFilterProp="label"
          showSearch
        />
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          仅显示未分配到任何号池且不在家庭组中的账号
        </Text>
      </Modal>
    </div>
  )
}

export default GroupDetailPage
