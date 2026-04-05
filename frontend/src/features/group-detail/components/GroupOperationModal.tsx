import { AutoComplete, Input, Modal, Select, Space, Typography } from 'antd'

import type { AutomationOperationDefinition } from '@/features/automation/operationMeta'
import type { GroupMemberOption } from '../utils'

const { Text } = Typography

interface GroupOperationModalProps {
  activeOp: AutomationOperationDefinition | null
  availableAccountOptions: { label: string; value: string }[]
  availableAccountsLoading: boolean
  formValues: Record<string, string>
  memberOptions: GroupMemberOption[]
  replaceNewEmail: string
  replaceOldEmail: string
  selectedEmails: string[]
  onAvailableAccountSearch: (value: string) => void
  onCancel: () => void
  onChangeFormValue: (name: string, value: string) => void
  onChangeReplaceNewEmail: (value: string) => void
  onChangeReplaceOldEmail: (value: string) => void
  onChangeSelectedEmails: (emails: string[]) => void
  onOk: () => void
  onSearchEmails: (value: string) => void
}

export function GroupOperationModal({
  activeOp,
  availableAccountOptions,
  availableAccountsLoading,
  formValues,
  memberOptions,
  replaceNewEmail,
  replaceOldEmail,
  selectedEmails,
  onAvailableAccountSearch,
  onCancel,
  onChangeFormValue,
  onChangeReplaceNewEmail,
  onChangeReplaceOldEmail,
  onChangeSelectedEmails,
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

        {activeOp?.key === 'replace' ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Select
              style={{ width: '100%' }}
              placeholder="选择要移除的旧成员"
              value={replaceOldEmail || undefined}
              onChange={onChangeReplaceOldEmail}
              options={memberOptions}
              optionFilterProp="label"
              showSearch
            />
            <AutoComplete
              style={{ width: '100%' }}
              placeholder="搜索并选择新成员，或直接输入邮箱"
              value={replaceNewEmail || undefined}
              onChange={onChangeReplaceNewEmail}
              onSearch={onAvailableAccountSearch}
              options={availableAccountOptions}
            />
          </Space>
        ) : null}

        {activeOp?.key === 'family-rotate' ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                要移除的子号（从当前成员中选择）:
              </Text>
              <Select
                mode="multiple"
                style={{ width: '100%' }}
                placeholder="选择要移除的子号"
                value={selectedEmails}
                onChange={onChangeSelectedEmails}
                options={memberOptions}
                optionFilterProp="label"
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>
                新子号数量（从可用池自动选取）:
              </Text>
              <Input
                type="number"
                min={1}
                max={5}
                placeholder="新子号数量"
                value={formValues['new_count'] || ''}
                onChange={(event) => onChangeFormValue('new_count', event.target.value)}
              />
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              需要主号浏览器运行中；新子号需之前登录过（有 cookies）
            </Text>
          </Space>
        ) : null}

        {activeOp && !['family-invite', 'family-remove', 'replace', 'family-rotate'].includes(activeOp.key) ? (
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
