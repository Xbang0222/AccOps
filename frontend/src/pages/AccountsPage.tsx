import React, { useCallback, useEffect, useState, type SyntheticEvent } from 'react';
import {
  Button,
  Input,
  Select,
  Modal,
  Table,
  Pagination,
  Tooltip,
  Flex,
  App,
  Typography,
} from 'antd';
import type { TablePaginationConfig } from 'antd';
import type { FilterValue, SorterResult } from 'antd/es/table/interface';
import type { ResizeCallbackData } from 'react-resizable';
import {
  PlusOutlined,
  SearchOutlined,
  CrownOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  ImportOutlined,
} from '@ant-design/icons';
import {
  getAccounts,
  deleteAccount,
  getGroups,
  importAccounts,
  getBrowserProfiles,
  createBrowserProfile,
  launchBrowser,
  stopBrowser,
  markAccountUnusable,
  clearAccountStatus,
} from '@/api';
import { createAccountTableColumns } from '@/features/accountsTableColumns';
import { createDefaultBrowserProfile } from '@/features/browser/browserProfileDefaults';
import {
  buildBrowserRuntimeState,
  updateLoadingAccountSet,
  updateRunningAccountSet,
} from '@/features/browser/runtime';
import type { Account } from '@/types';
import { getErrorMessage } from '@/utils/http';
import AccountModal from '@/components/AccountModal';
import ResizableTitle from '@/components/ResizableTitle';
import { generateTOTP } from '@/utils/totp';
import { useAutomation, useAutomationEvents } from '@/contexts/automationContext';

const { Text } = Typography;

const AccountsPage: React.FC = () => {
  const { message: msg } = App.useApp();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [searchText, setSearchText] = useState('');
  const [groupFilter, setGroupFilter] = useState<string | undefined>();
  const [groups, setGroups] = useState<string[]>([]);
  const [masked, setMasked] = useState(false);
  const [ownerOnly, setOwnerOnly] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [sortField, setSortField] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // 导入
  const [importVisible, setImportVisible] = useState(false);
  const [importText, setImportText] = useState('');
  const [importLoading, setImportLoading] = useState(false);

  // 浏览器状态
  const [browserRunning, setBrowserRunning] = useState<Set<number>>(new Set());
  const [browserLoading, setBrowserLoading] = useState<Set<number>>(new Set());
  const [profileMap, setProfileMap] = useState<Record<number, number>>({});

  const { execute: executeAutomation } = useAutomation();
  useAutomationEvents({
    onSuccess: () => {
      void loadAccounts();
    },
  });

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getAccounts({
        search: searchText,
        group: groupFilter,
        page: currentPage,
        pageSize,
        ownerOnly,
        sortBy: sortField,
        sortOrder,
      });
      setAccounts(data.accounts);
      setTotal(data.total);
    } catch {
      msg.error('加载账号失败');
    } finally {
      setLoading(false);
    }
  }, [currentPage, groupFilter, msg, ownerOnly, pageSize, searchText, sortField, sortOrder]);

  const loadFilters = useCallback(async () => {
    try {
      const groupsRes = await getGroups();
      setGroups(groupsRes.data.groups);
    } catch { /* silent */ }
  }, []);

  const loadBrowserStatus = useCallback(async () => {
    try {
      const { data } = await getBrowserProfiles();
      const runtimeState = buildBrowserRuntimeState(data.profiles);
      setProfileMap(runtimeState.profileMap);
      setBrowserRunning(runtimeState.runningAccountIds);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    void loadAccounts();
    void loadFilters();
  }, [loadAccounts, loadFilters]);

  useEffect(() => {
    void loadBrowserStatus();
  }, [loadBrowserStatus]);

  const handleLaunchAndLogin = async (record: Account) => {
    const accountId = record.id;
    setBrowserLoading((prev) => updateLoadingAccountSet(prev, accountId, true));
    try {
      let profileId = profileMap[accountId];
      if (!profileId) {
        const res = await createBrowserProfile(createDefaultBrowserProfile(accountId, record.email));
        profileId = res.data.id;
        setProfileMap((prev) => ({ ...prev, [accountId]: profileId }));
      }
      await launchBrowser(profileId);
      setBrowserRunning((prev) => updateRunningAccountSet(prev, accountId, true));
      msg.success('浏览器已启动，开始自动登录...');

      // 通过 WebSocket 触发自动登录（不显示日志）
      executeAutomation(accountId, 'login');
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '启动失败'));
    } finally {
      setBrowserLoading((prev) => updateLoadingAccountSet(prev, accountId, false));
    }
  };

  const handleStopBrowser = async (accountId: number) => {
    const profileId = profileMap[accountId];
    if (!profileId) return;
    setBrowserLoading((prev) => updateLoadingAccountSet(prev, accountId, true));
    try {
      await stopBrowser(profileId);
      setBrowserRunning((prev) => updateRunningAccountSet(prev, accountId, false));
      msg.success('浏览器已停止');
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '停止失败'));
    } finally {
      setBrowserLoading((prev) => updateLoadingAccountSet(prev, accountId, false));
    }
  };

  const handleAdd = () => { setEditingAccount(null); setModalVisible(true); };
  const handleEdit = (record: Account) => { setEditingAccount(record); setModalVisible(true); };
  const handleDelete = (id: number) => {
    Modal.confirm({
      title: '确认删除', content: '确定要删除这个账号吗？',
      okText: '删除', okType: 'danger', cancelText: '取消',
      onOk: async () => {
        try { await deleteAccount(id); msg.success('已删除'); loadAccounts(); loadFilters(); }
        catch { msg.error('删除失败'); }
      },
    });
  };

  const handleMarkUnusable = async (id: number) => {
    try {
      await markAccountUnusable(id);
      msg.success('已标记为无法使用');
      loadAccounts();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '标记失败'));
    }
  };

  const handleClearStatus = async (id: number) => {
    try {
      await clearAccountStatus(id);
      msg.success('已恢复正常状态');
      loadAccounts();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '操作失败'));
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text).then(() => msg.success(`${label}已复制`));
  };

  const copyFullAccount = (record: Account) => {
    const parts = [record.email, record.password, record.recovery_email || '', record.totp_secret || ''];
    navigator.clipboard.writeText(parts.join('----')).then(() => msg.success('账号信息已复制'));
  };

  const copyTOTPCode = (secret: string) => {
    try {
      const { code } = generateTOTP(secret);
      navigator.clipboard.writeText(code).then(() => {
        msg.success(`2FA 验证码已复制: ${code}`);
      });
    } catch {
      msg.error('生成验证码失败');
    }
  };

  const handleTableChange = (
    _pagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    sorter: SorterResult<Account> | SorterResult<Account>[],
  ) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    if (s.field && s.order) {
      setSortField(s.field as string);
      setSortOrder(s.order === 'ascend' ? 'asc' : 'desc');
    } else {
      // 取消排序时恢复默认
      setSortField('created_at');
      setSortOrder('desc');
    }
    setCurrentPage(1);
  };

  const handleImport = async () => {
    if (!importText.trim()) { msg.warning('请输入要导入的账号信息'); return; }
    setImportLoading(true);
    try {
      const res = await importAccounts(importText);
      const data = res.data;
      if (data.success > 0) msg.success(data.message);
      else if (data.skipped > 0) msg.warning(data.message);
      else msg.error(data.message);
      if (data.success > 0) {
        setImportVisible(false); setImportText(''); loadAccounts(); loadFilters();
      }
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '导入失败'));
    } finally { setImportLoading(false); }
  };

  const baseColumns = createAccountTableColumns({
    browserLoading,
    browserRunning,
    masked,
    onCopyFullAccount: copyFullAccount,
    onCopyText: copyToClipboard,
    onCopyTotpCode: copyTOTPCode,
    onDelete: handleDelete,
    onEdit: handleEdit,
    onLaunchAndLogin: handleLaunchAndLogin,
    onStopBrowser: handleStopBrowser,
    onMarkUnusable: handleMarkUnusable,
    onClearStatus: handleClearStatus,
  });

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() => {
    const widths: Record<string, number> = {};
    for (const col of baseColumns) {
      const key = (col as { key?: string }).key;
      const width = (col as { width?: number }).width;
      if (key && width) {
        widths[key] = width;
      }
    }
    return widths;
  });

  const handleColumnResize = (key: string) =>
    (_e: SyntheticEvent, { size }: ResizeCallbackData) => {
      setColumnWidths((prev) => ({ ...prev, [key]: size.width }));
    };

  const columns = baseColumns.map((col) => {
    const key = (col as { key?: string }).key;
    const colWithSort = {
      ...col,
      ...(key === sortField ? { sortOrder: sortOrder === 'asc' ? 'ascend' as const : 'descend' as const } : { sortOrder: undefined }),
    };
    if (!key || !columnWidths[key]) return colWithSort;
    return {
      ...colWithSort,
      width: columnWidths[key],
      onHeaderCell: () => ({
        width: columnWidths[key],
        onResize: handleColumnResize(key),
      }),
    };
  });

  const tableComponents = {
    header: { cell: ResizableTitle },
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 工具栏 */}
      <Flex justify="space-between" align="center" style={{ marginBottom: 16, flexShrink: 0 }} wrap gap={12}>
        <Flex gap={8} wrap>
          <Input
            placeholder="搜索邮箱或备注"
            prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
            style={{ width: 220 }}
            onChange={(e) => { setSearchText(e.target.value); setCurrentPage(1); }}
            allowClear
          />
          <Select
            placeholder="分组" style={{ width: 140 }}
            onChange={(v) => { setGroupFilter(v); setCurrentPage(1); }}
            allowClear options={groups.map((g) => ({ label: g, value: g }))}
          />
        </Flex>
        <Flex gap={8} align="center">
          <Tooltip title="添加账号">
            <Button type="text" icon={<PlusOutlined />} onClick={handleAdd} />
          </Tooltip>
          <Tooltip title="批量导入">
            <Button type="text" icon={<ImportOutlined />} onClick={() => setImportVisible(true)} />
          </Tooltip>
          <Tooltip title={ownerOnly ? '显示全部账号' : '仅显示创建者'}>
            <Button
              type={ownerOnly ? 'primary' : 'text'}
              icon={<CrownOutlined />}
              onClick={() => { setOwnerOnly((v) => !v); setCurrentPage(1); }}
              style={ownerOnly ? { boxShadow: 'none' } : {}}
            />
          </Tooltip>
          <Tooltip title={masked ? '显示邮箱' : '隐藏邮箱'}>
            <Button type="text" icon={masked ? <EyeInvisibleOutlined /> : <EyeOutlined />} onClick={() => setMasked((v) => !v)} />
          </Tooltip>
        </Flex>
      </Flex>

      {/* 表格 */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Table<Account>
          components={tableComponents}
          columns={columns}
          dataSource={accounts}
          rowKey="id"
          loading={loading}
          size="small"
          scroll={{ x: 1100, y: 'calc(100vh - 260px)' }}
          pagination={false}
          onChange={handleTableChange}
        />
      </div>

      {/* 分页 - 固定底部居中 */}
      <Flex justify="center" align="center" style={{ padding: '12px 0', flexShrink: 0 }}>
        <Pagination
          current={currentPage}
          pageSize={pageSize}
          total={total}
          showSizeChanger
          pageSizeOptions={['10', '20', '50', '100']}
          showTotal={(t) => `共 ${t} 个账号`}
          onChange={(p, ps) => { setCurrentPage(p); setPageSize(ps); }}
          size="small"
        />
      </Flex>

      {/* 导入弹窗 */}
      <Modal
        title="批量导入账号"
        open={importVisible}
        onCancel={() => { setImportVisible(false); setImportText(''); }}
        onOk={handleImport}
        okText="导入"
        cancelText="取消"
        confirmLoading={importLoading}
        width={600}
      >
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary">
            每行一个账号，字段用 <Text code>----</Text> 或 <Text code>|</Text> 分隔，智能识别字段类型：
          </Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>
            含 @ → 辅助邮箱 | http(s)开头 → 链接(存备注) | 其他 → 2FA密钥
          </Text>
        </div>
        <Input.TextArea
          rows={8}
          placeholder={`支持多种格式，例如：\nemail----密码----辅助邮箱----2FA密钥----短信链接\nemail|密码|辅助邮箱|2FA密钥|国家\nemail----密码----辅助邮箱`}
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
          style={{ fontFamily: 'monospace', fontSize: 12 }}
        />
        {importText.trim() && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">
              共 {importText.trim().split('\n').filter((l) => l.trim()).length} 条记录
            </Text>
          </div>
        )}
      </Modal>

      <AccountModal
        visible={modalVisible}
        account={editingAccount}
        onClose={() => setModalVisible(false)}
        onSuccess={() => { loadAccounts(); loadFilters(); }}
      />
    </div>
  );
};

export default AccountsPage;
