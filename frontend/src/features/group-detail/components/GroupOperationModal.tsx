import { Input, Modal, Select, Space, Typography } from 'antd'

import type { AutomationOperationDefinition } from '@/features/automation/operationMeta'
import type { GroupMemberOption } from '../utils'
import { SelectAllToggle } from './SelectAllToggle'

const { Text } = Typography

export interface GroupCapacityInfo {
  invite: number
  swapNew: number
}

export interface GroupSelectAllCallbacks {
  invite: () => void
  members: () => void
  swapManual: () => void
  clearSelectedEmails: () => void
  clearSwapManualEmails: () => void
}

interface GroupOperationModalProps {
  activeOp: AutomationOperationDefinition | null
  availableAccountOptions: { label: string; value: string }[]
  availableAccountsLoading: boolean
  formValues: Record<string, string>
  memberOptions: GroupMemberOption[]
  selectedEmails: string[]
  swapManualEmails: string[]
  capacity: GroupCapacityInfo
  selectAll: GroupSelectAllCallbacks
  onAvailableAccountSearch: (value: string) => void
  onCancel: () => void
  onChangeFormValue: (name: string, value: string) => void
  onChangeSelectedEmails: (emails: string[]) => void
  onChangeSwapManualEmails: (emails: string[]) => void
  onOk: () => void
  onSearchEmails: (value: string) => void
}

const toggleRowStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: 6,
}

export function GroupOperationModal({
  activeOp,
  availableAccountOptions,
  availableAccountsLoading,
  formValues,
  memberOptions,
  selectedEmails,
  swapManualEmails,
  capacity,
  selectAll,
  onAvailableAccountSearch,
  onCancel,
  onChangeFormValue,
  onChangeSelectedEmails,
  onChangeSwapManualEmails,
  onOk,
  onSearchEmails,
}: GroupOperationModalProps) {
  return (
    <Modal
      open={Boolean(activeOp)}
      title={activeOp?.label}
      onCancel={onCancel}
      onOk={onOk}
      okText="执行"
      cancelText="取消"
      okButtonProps={{ danger: activeOp?.danger }}
      width={420}
      destroyOnClose
    >
      <div style={{ marginTop: 12 }}>
        {activeOp?.key === 'family-invite' ? (
          <>
            <div style={toggleRowStyle}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                家庭组剩余 {capacity.invite} 个空位（上限 6 人）
              </Text>
              <SelectAllToggle
                options={availableAccountOptions}
                selected={selectedEmails}
                onSelectAll={selectAll.invite}
                onClear={selectAll.clearSelectedEmails}
                limit={capacity.invite}
              />
            </div>
            <Select
              mode="multiple"
              style={{ width: '100%' }}
              placeholder="搜索并选择账号，或直接输入邮箱回车添加"
              value={selectedEmails}
              onChange={onChangeSelectedEmails}
              onSearch={(value) => {
                onSearchEmails(value)
                onAvailableAccountSearch(value)
              }}
              options={availableAccountOptions}
              loading={availableAccountsLoading}
              filterOption={false}
              tokenSeparators={[',', ';', '\n', '\t']}
              showSearch
              notFoundContent={availableAccountsLoading ? '搜索中...' : '无匹配账号，可直接输入邮箱回车添加'}
            />
            <Text type="secondary" style={{ fontSize: 12, marginTop: 6, display: 'block' }}>
              下拉列表仅显示未加入家庭组的账号，全选仅选中当前下拉中显示的可用账号
            </Text>
          </>
        ) : null}

        {activeOp?.key === 'family-remove' ? (
          <>
            <div style={toggleRowStyle}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                选择要移除的成员
              </Text>
              <SelectAllToggle
                options={memberOptions}
                selected={selectedEmails}
                onSelectAll={selectAll.members}
                onClear={selectAll.clearSelectedEmails}
              />
            </div>
            <Select
              mode="multiple"
              style={{ width: '100%' }}
              placeholder="选择要移除的成员"
              value={selectedEmails}
              onChange={onChangeSelectedEmails}
              options={memberOptions}
              optionFilterProp="label"
            />
          </>
        ) : null}

        {activeOp?.key === 'family-swap' ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <div>
              <div style={toggleRowStyle}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  要移除的成员:
                </Text>
                <SelectAllToggle
                  options={memberOptions}
                  selected={selectedEmails}
                  onSelectAll={selectAll.members}
                  onClear={selectAll.clearSelectedEmails}
                />
              </div>
              <Select
                mode="multiple"
                style={{ width: '100%' }}
                placeholder="选择要移除的成员（不选则全部移除）"
                value={selectedEmails}
                onChange={onChangeSelectedEmails}
                options={memberOptions}
                optionFilterProp="label"
              />
            </div>
            <div>
              <div style={toggleRowStyle}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  新成员:
                </Text>
                <SelectAllToggle
                  options={availableAccountOptions}
                  selected={swapManualEmails}
                  onSelectAll={selectAll.swapManual}
                  onClear={selectAll.clearSwapManualEmails}
                  limit={capacity.swapNew}
                />
              </div>
              <Select
                mode="tags"
                style={{ width: '100%' }}
                placeholder="搜索并选择账号，或直接输入邮箱回车添加"
                value={swapManualEmails}
                onChange={onChangeSwapManualEmails}
                onSearch={onAvailableAccountSearch}
                options={availableAccountOptions}
                loading={availableAccountsLoading}
                filterOption={false}
                tokenSeparators={[',', ';', '\n', '\t']}
                showSearch
                notFoundContent={availableAccountsLoading ? '搜索中...' : '无匹配账号，可直接输入邮箱回车添加'}
              />
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              换号完成后会自动执行同步验证，确保数据库与实际状态一致
            </Text>
          </Space>
        ) : null}

        {activeOp && !['family-invite', 'family-remove', 'family-swap'].includes(activeOp.key) ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {activeOp.fields?.map((field) => (
              <Input
                key={field.name}
                placeholder={field.placeholder}
                value={formValues[field.name] || ''}
                onChange={(event) => onChangeFormValue(field.name, event.target.value)}
                onPressEnter={onOk}
              />
            ))}
          </Space>
        ) : null}
      </div>
    </Modal>
  )
}
