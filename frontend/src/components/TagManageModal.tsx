import React, { useCallback, useEffect, useState } from 'react';
import {
  App,
  Button,
  Empty,
  Flex,
  Input,
  List,
  Modal,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  TagsOutlined,
} from '@ant-design/icons';

import { createTag, deleteTag, getTags, updateTag } from '@/api';
import type { Tag as TagType } from '@/types';
import { getErrorMessage } from '@/utils/http';

const { Text } = Typography;

const TAG_NAME_MAX_LENGTH = 32;

interface TagManageModalProps {
  visible: boolean;
  onClose: () => void;
  onChange?: () => void;
}

const TagManageModal: React.FC<TagManageModalProps> = ({
  visible,
  onClose,
  onChange,
}) => {
  const { message: msg, modal } = App.useApp();
  const [tags, setTags] = useState<TagType[]>([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState('');

  const loadTags = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getTags();
      setTags(data.tags);
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '加载标签失败'));
    } finally {
      setLoading(false);
    }
  }, [msg]);

  useEffect(() => {
    if (visible) {
      void loadTags();
      setNewName('');
      setEditingId(null);
    }
  }, [visible, loadTags]);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      msg.warning('请输入标签名称');
      return;
    }
    setCreating(true);
    try {
      await createTag(name);
      msg.success('标签创建成功');
      setNewName('');
      await loadTags();
      onChange?.();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '创建失败'));
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (tag: TagType) => {
    setEditingId(tag.id);
    setEditingName(tag.name);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditingName('');
  };

  const handleSaveEdit = async (tag: TagType) => {
    const name = editingName.trim();
    if (!name) {
      msg.warning('标签名称不能为空');
      return;
    }
    if (name === tag.name) {
      cancelEdit();
      return;
    }
    try {
      await updateTag(tag.id, name);
      msg.success('标签更新成功');
      cancelEdit();
      await loadTags();
      onChange?.();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '更新失败'));
    }
  };

  const handleDelete = (tag: TagType) => {
    const count = tag.accounts_count ?? 0;
    const content = count > 0
      ? `该标签当前关联了 ${count} 个账号，删除后这些账号会自动失去关联（账号本身不会被删除）。`
      : '该标签当前未关联任何账号，可以放心删除。';
    modal.confirm({
      title: `删除标签「${tag.name}」？`,
      content,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteTag(tag.id);
          msg.success('标签已删除');
          await loadTags();
          onChange?.();
        } catch (error: unknown) {
          msg.error(getErrorMessage(error, '删除失败'));
        }
      },
    });
  };

  return (
    <Modal
      title={(
        <Flex align="center" gap={8}>
          <TagsOutlined />
          <span>管理标签</span>
        </Flex>
      )}
      open={visible}
      onCancel={onClose}
      footer={(
        <Button onClick={onClose}>关闭</Button>
      )}
      width={480}
      destroyOnHidden
    >
      <Flex gap={8} style={{ marginTop: 8, marginBottom: 16 }}>
        <Input
          placeholder="新标签名称，如：VIP / 待处理"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={handleCreate}
          allowClear
          maxLength={TAG_NAME_MAX_LENGTH}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreate}
          loading={creating}
        >
          添加
        </Button>
      </Flex>

      <List
        loading={loading}
        size="small"
        bordered
        locale={{
          emptyText: <Empty description="还没有标签，先添加一个" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
        }}
        dataSource={tags}
        renderItem={(tag) => {
          const isEditing = editingId === tag.id;
          return (
            <List.Item
              actions={isEditing ? [
                <Tooltip key="save" title="保存">
                  <Button type="text" size="small" icon={<CheckOutlined style={{ color: '#52c41a' }} />} onClick={() => handleSaveEdit(tag)} />
                </Tooltip>,
                <Tooltip key="cancel" title="取消">
                  <Button type="text" size="small" icon={<CloseOutlined />} onClick={cancelEdit} />
                </Tooltip>,
              ] : [
                <Tooltip key="edit" title="重命名">
                  <Button type="text" size="small" icon={<EditOutlined />} onClick={() => startEdit(tag)} />
                </Tooltip>,
                <Tooltip key="delete" title="删除">
                  <Button type="text" size="small" icon={<DeleteOutlined style={{ color: '#ff4d4f' }} />} onClick={() => handleDelete(tag)} />
                </Tooltip>,
              ]}
            >
              {isEditing ? (
                <Input
                  value={editingName}
                  onChange={(e) => setEditingName(e.target.value)}
                  onPressEnter={() => handleSaveEdit(tag)}
                  size="small"
                  autoFocus
                  maxLength={TAG_NAME_MAX_LENGTH}
                  style={{ maxWidth: 240 }}
                />
              ) : (
                <Flex align="center" gap={8}>
                  <Tag style={{ margin: 0 }}>{tag.name}</Tag>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {(tag.accounts_count ?? 0) > 0
                      ? `${tag.accounts_count} 个账号`
                      : '未使用'}
                  </Text>
                </Flex>
              )}
            </List.Item>
          );
        }}
      />
    </Modal>
  );
};

export default TagManageModal;
