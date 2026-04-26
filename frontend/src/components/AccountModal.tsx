import React, { useEffect, useState } from 'react';
import { Divider, Form, Input, Modal, Select, message } from 'antd';
import {
  MailOutlined,
  LockOutlined,
  SafetyOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import {
  createAccount,
  updateAccount,
} from '@/api';
import type { Account, AccountInput, Tag } from '@/types';
import { getErrorMessage } from '@/utils/http';

const { TextArea } = Input;

interface AccountModalProps {
  visible: boolean;
  account: Account | null;
  tags?: Tag[];
  onClose: () => void;
  onSuccess: () => void;
}

const AccountModal: React.FC<AccountModalProps> = ({
  visible,
  account,
  tags = [],
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible) {
      if (account) {
        form.setFieldsValue({
          ...account,
          tag_ids: account.tags?.map((t) => t.id) ?? [],
        });
      } else {
        form.resetFields();
      }
    }
  }, [account, form, visible]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const submitValues: AccountInput = {
        email: values.email,
        password: values.password ?? '',
        recovery_email: values.recovery_email ?? '',
        totp_secret: values.totp_secret ?? '',
        notes: values.notes ?? '',
        tag_ids: values.tag_ids ?? [],
      };

      if (account) {
        // 保留原有的 family_group_id，避免编辑账号时把家庭组关联清掉
        submitValues.group_id = account.family_group_id ?? null;
        await updateAccount(account.id, submitValues);
        message.success('账号更新成功');
      } else {
        await createAccount(submitValues);
        message.success('账号添加成功');
      }

      onSuccess();
      onClose();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '保存失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={account ? '编辑账号' : '添加账号'}
      open={visible}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={loading}
      width={520}
      okText="保存"
      cancelText="取消"
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        style={{ marginTop: 16 }}
        requiredMark={false}
      >
        <Form.Item
          name="email"
          label="邮箱地址"
          rules={[{ required: true, message: '请输入邮箱地址' }]}
        >
          <Input
            prefix={<MailOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="example@gmail.com"
          />
        </Form.Item>

        <Form.Item
          name="password"
          label="密码"
        >
          <Input.Password
            prefix={<LockOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="账号密码"
          />
        </Form.Item>

        <Form.Item name="recovery_email" label="辅助邮箱">
          <Input
            prefix={<MailOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="用于账号恢复"
          />
        </Form.Item>

        <Form.Item name="totp_secret" label="2FA 密钥">
          <Input
            prefix={<SafetyOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="如: JBSWY3DPEHPK3PXP"
          />
        </Form.Item>

        <Divider style={{ margin: '8px 0 16px' }} />

        <Form.Item name="tag_ids" label="标签">
          <Select
            mode="multiple"
            placeholder={tags.length === 0 ? '尚未创建标签，请先在账号页点「管理标签」添加' : '选择标签'}
            allowClear
            showSearch
            suffixIcon={<TagsOutlined style={{ color: '#bfbfbf' }} />}
            options={tags.map((t) => ({ label: t.name, value: t.id }))}
            disabled={tags.length === 0}
          />
        </Form.Item>

        <Form.Item name="notes" label="备注">
          <TextArea rows={3} placeholder="其他信息..." />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default AccountModal;
