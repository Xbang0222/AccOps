import { Button, Input, Modal, Radio, Select, Space, Typography } from 'antd'

import type { AutomationOperationDefinition } from '@/features/automation/operationMeta'
import type { GroupMemberOption } from '../utils'

const { Text } = Typography

interface GroupOperationModalProps {
  activeOp: AutomationOperationDefinition | null
  availableAccountOptions: { label: string; value: string }[]
  availableAccountsLoading: boolean
  formValues: Record<string, string>
  memberOptions: GroupMemberOption[]
  selectedEmails: string[]
  swapManualEmails: string[]
  swapMode: 'pool' | 'manual'
  onAvailableAccountSearch: (value: string) => void
  onCancel: () => void
  onChangeFormValue: (name: string, value: string) => void
  onChangeSelectedEmails: (emails: string[]) => void
  onChangeSwapManualEmails: (emails: string[]) => void
  onChangeSwapMode: (mode: 'pool' | 'manual') => void
  onOk: () => void
  onSearchEmails: (value: string) => void
  onSelectAllMembers: () => void
}

export function GroupOperationModal({
  activeOp,
  availableAccountOptions,
  availableAccountsLoading,
  formValues,
  memberOptions,
  selectedEmails,
  swapManualEmails,
  swapMode,
  onAvailableAccountSearch,
  onCancel,
  onChangeFormValue,
  onChangeSelectedEmails,
  onChangeSwapManualEmails,
  onChangeSwapMode,
  onOk,
  onSearchEmails,
  onSelectAllMembers,
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
              下拉列表仅显示未加入家庭组的账号，也可直接输入外部邮箱
            </Text>
          </>
        ) : null}

        {activeOp?.key === 'family-remove' ? (
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder="选择要移除的成员"
            value={selectedEmails}
            onChange={onChangeSelectedEmails}
            options={memberOptions}
            optionFilterProp="label"
          />
        ) : null}

        {activeOp?.key === 'family-swap' ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  要移除的成员:
                </Text>
                <Button type="link" size="small" onClick={onSelectAllMembers} style={{ padding: 0, height: 'auto', fontSize: 12 }}>
                  全选
                </Button>
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
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                替换方式:
              </Text>
              <Radio.Group
                value={swapMode}
                onChange={(e) => onChangeSwapMode(e.target.value)}
                style={{ marginBottom: 8 }}
              >
                <Radio value="pool">号池自动选取</Radio>
                <Radio value="manual">手动指定</Radio>
              </Radio.Group>

              {swapMode === 'pool' ? (
                <Input
                  type="number"
                  min={1}
                  max={5}
                  placeholder="新子号数量（默认与移除数一致）"
                  value={formValues['new_count'] || ''}
                  onChange={(event) => onChangeFormValue('new_count', event.target.value)}
                />
              ) : (
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
              )}
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
