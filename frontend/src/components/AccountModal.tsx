import React, { useEffect, useState } from 'react';
import { Divider, Form, Input, Modal, message } from 'antd';
import {
  MailOutlined,
  LockOutlined,
  SafetyOutlined,
  FolderOutlined,
} from '@ant-design/icons';
import {
  createAccount,
  updateAccount,
} from '@/api';
import type { Account } from '@/types';
import { getErrorMessage } from '@/utils/http';

const { TextArea } = Input;

interface AccountModalProps {
  visible: boolean;
  account: Account | null;
  onClose: () => void;
  onSuccess: () => void;
}

const AccountModal: React.FC<AccountModalProps> = ({
  visible,
  account,
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible) {
      if (account) {
        form.setFieldsValue(account);
      } else {
        form.resetFields();
      }
    }
  }, [account, form, visible]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const submitValues = { ...values };

      if (account) {
        // 保留原有的 family_group_id，避免编辑账号时把分组关联清掉
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
      destroyOnClose
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

        <Form.Item name="group_name" label="分组">
          <Input
            prefix={<FolderOutlined style={{ color: '#bfbfbf' }} />}
            placeholder="如: 工作、个人"
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
