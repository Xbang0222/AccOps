import React, { useMemo } from 'react'
import { Button, Checkbox, Empty, Flex, Spin, Tag, Tooltip, Typography } from 'antd'
import { ArrowLeftOutlined, CloudUploadOutlined, EyeInvisibleOutlined, EyeOutlined, LoginOutlined, PoweroffOutlined, SafetyCertificateOutlined, TeamOutlined, UsergroupAddOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'

import { GroupAccountCard } from '@/features/group-detail/components/GroupAccountCard'
import { GroupOperationLogPanel } from '@/features/group-detail/components/GroupOperationLogPanel'
import { GroupOperationModal } from '@/features/group-detail/components/GroupOperationModal'
import { useGroupDetailController } from '@/features/group-detail/useGroupDetailController'

const { Text } = Typography

const GroupDetailPage: React.FC = () => {
  const { groupId: groupIdParam } = useParams<{ groupId: string }>()
  const navigate = useNavigate()
  const groupId = Number(groupIdParam)
  const controller = useGroupDetailController(groupId)

  const uploadableCount = useMemo(() => {
    const mainId = controller.group?.main_account_id ?? null
    return (controller.group?.accounts ?? [])
      .filter((a) => a.has_oauth_credential && a.id !== mainId)
      .length
  }, [controller.group?.accounts, controller.group?.main_account_id])

  const modalCapacity = useMemo(
    () => ({
      invite: controller.inviteCapacityLeft,
      swapNew: controller.swapNewCapacityLeft,
    }),
    [controller.inviteCapacityLeft, controller.swapNewCapacityLeft],
  )

  const modalSelectAll = useMemo(
    () => ({
      invite: controller.handleSelectAllInviteEmails,
      members: controller.handleSelectAllMembers,
      swapManual: controller.handleSelectAllSwapManualEmails,
      clearSelectedEmails: controller.handleClearSelectedEmails,
      clearSwapManualEmails: controller.handleClearSwapManualEmails,
    }),
    [
      controller.handleSelectAllInviteEmails,
      controller.handleSelectAllMembers,
      controller.handleSelectAllSwapManualEmails,
      controller.handleClearSelectedEmails,
      controller.handleClearSwapManualEmails,
    ],
  )

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
        {uploadableCount > 0 ? (
          <Tooltip title={controller.selectedForUpload.size >= uploadableCount ? '取消全选' : `全选所有子号 (${uploadableCount})`}>
            <Checkbox
              checked={controller.selectedForUpload.size > 0 && controller.selectedForUpload.size >= uploadableCount}
              indeterminate={controller.selectedForUpload.size > 0 && controller.selectedForUpload.size < uploadableCount}
              onChange={() => {
                if (controller.selectedForUpload.size >= uploadableCount) {
                  controller.handleClearUploadSelection()
                } else {
                  controller.handleSelectAllUploadable()
                }
              }}
              style={{ marginLeft: 4 }}
            />
          </Tooltip>
        ) : null}
        <div style={{ flex: 1 }} />
        <Tooltip title="一键启动所有子号浏览器">
          <Button
            size="small"
            type="text"
            icon={<LoginOutlined />}
            loading={controller.batchRunning === 'launch'}
            disabled={controller.batchRunning !== null && controller.batchRunning !== 'launch'}
            onClick={() => void controller.handleBatchLaunch()}
          />
        </Tooltip>
        <Tooltip title="一键接受所有待处理邀请">
          <Button
            size="small"
            type="text"
            icon={<UsergroupAddOutlined />}
            disabled={controller.batchRunning !== null}
            onClick={controller.handleBatchAccept}
          />
        </Tooltip>
        <Tooltip title="一键执行 OAuth 验证">
          <Button
            size="small"
            type="text"
            icon={<SafetyCertificateOutlined />}
            disabled={controller.batchRunning !== null}
            onClick={controller.handleBatchOAuth}
          />
        </Tooltip>
        {controller.selectedForUpload.size > 0 ? (
          <Tooltip title={`上传选中的 ${controller.selectedForUpload.size} 个 OAuth 凭证到 CLIProxy`}>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<CloudUploadOutlined />}
              disabled={controller.batchRunning !== null}
              loading={controller.uploadingToCliproxy}
              onClick={() => void controller.handleUploadToCliproxy()}
            >
              {controller.selectedForUpload.size}
            </Button>
          </Tooltip>
        ) : null}
        <Tooltip title="一键关闭所有子号浏览器">
          <Button
            size="small"
            type="text"
            icon={<PoweroffOutlined />}
            loading={controller.batchRunning === 'stop'}
            disabled={controller.batchRunning !== null && controller.batchRunning !== 'stop'}
            onClick={() => void controller.handleBatchStop()}
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
                  isCheckedForUpload={controller.selectedForUpload.has(account.id)}
                  onClearStatus={controller.handleClearStatus}
                  onCopyOAuthJson={controller.handleCopyOAuthJson}
                  onCopyText={controller.copyToClipboard}
                  onCopyTOTP={controller.copyTOTPCode}
                  onDownloadOAuth={controller.handleDownloadOAuth}
                  onMarkUnusable={controller.handleMarkUnusable}
                  onOAuth={controller.handleOAuth}
                  onOperationClick={controller.handleOperationClick}
                  onPhoneVerify={controller.handlePhoneVerify}
                  onRemoveFromGroup={controller.handleRemoveFromGroup}
                  onSelect={controller.setSelectedAccountId}
                  onToggleBrowser={controller.handleToggleBrowser}
                  onToggleUploadSelect={controller.handleToggleUploadSelect}
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
        onAvailableAccountSearch={controller.handleAvailableAccountSearch}
        onCancel={() => {
          controller.setActiveOp(null)
          controller.setActiveAccountId(null)
        }}
        onChangeFormValue={(name, value) => controller.setFormValues((previous) => ({ ...previous, [name]: value }))}
        onChangeSelectedEmails={controller.setSelectedEmails}
        onChangeSwapManualEmails={controller.setSwapManualEmails}
        onOk={controller.handleFieldModalOk}
        onSearchEmails={controller.handleEmailSearch}
        capacity={modalCapacity}
        selectAll={modalSelectAll}
      />
    </div>
  )
}

export default GroupDetailPage
