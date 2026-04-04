import { Input, Modal, Select, Space } from 'antd'

import type { AutomationOperationDefinition } from '@/features/automation/operationMeta'
import type { GroupMemberOption } from '../utils'

interface GroupOperationModalProps {
  activeOp: AutomationOperationDefinition | null
  formValues: Record<string, string>
  memberOptions: GroupMemberOption[]
  replaceNewEmail: string
  replaceOldEmail: string
  selectedEmails: string[]
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
  formValues,
  memberOptions,
  replaceNewEmail,
  replaceOldEmail,
  selectedEmails,
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
          <Select
            mode="tags"
            style={{ width: '100%' }}
            placeholder="输入或粘贴邮箱，回车添加（支持逗号、换行分隔）"
            value={selectedEmails}
            onChange={onChangeSelectedEmails}
            onSearch={onSearchEmails}
            tokenSeparators={[',', ';', '\n', '\t', ' ']}
            open={false}
            suffixIcon={null}
            notFoundContent={null}
          />
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
            <Input
              placeholder="新成员邮箱（将被邀请）"
              value={replaceNewEmail}
              onChange={(event) => onChangeReplaceNewEmail(event.target.value)}
              onPressEnter={onOk}
            />
          </Space>
        ) : null}

        {activeOp && !['family-invite', 'family-remove', 'replace'].includes(activeOp.key) ? (
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
