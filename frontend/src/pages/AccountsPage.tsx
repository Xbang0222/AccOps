import React, { useCallback, useEffect, useMemo, useState, type SyntheticEvent } from 'react';
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
  Radio,
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
  DownloadOutlined,
  TagsOutlined,
  TagOutlined,
} from '@ant-design/icons';
import {
  getAccounts,
  deleteAccount,
  getTags,
  importAccounts,
  getBrowserProfiles,
  createBrowserProfile,
  launchBrowser,
  stopBrowser,
  markAccountUnusable,
  clearAccountStatus,
  batchUpdateTags,
} from '@/api';
import { createAccountTableColumns, SELECTION_COLUMN_WIDTH } from '@/features/accountsTableColumns';
import { createDefaultBrowserProfile } from '@/features/browser/browserProfileDefaults';
import {
  buildBrowserRuntimeState,
  updateLoadingAccountSet,
  updateRunningAccountSet,
} from '@/features/browser/runtime';
import type { Account, Tag } from '@/types';
import { getErrorMessage } from '@/utils/http';
import AccountModal from '@/components/AccountModal';
import TagManageModal from '@/components/TagManageModal';
import ResizableTitle from '@/components/ResizableTitle';
import { generateTOTP } from '@/utils/totp';
import { downloadAccountsTxt } from '@/utils/exportAccount';
import { useAutomation, useAutomationEvents } from '@/contexts/automationContext';

const { Text } = Typography;

// v2: 重命名 key 强制清掉旧版本残留 (存过被拖宽到异常值的列宽, 视觉上会出现错位的 resize handle / 空白边界)
const COLUMN_WIDTHS_STORAGE_KEY = 'accops:accounts-column-widths-v2';
const LEGACY_COLUMN_WIDTHS_KEYS = ['accops:accounts-column-widths'];
// localStorage 中保存的列宽超过默认值此倍数视为误拖, 回落默认值, 防止视觉异常
const MAX_COLUMN_WIDTH_FACTOR = 3;

const AccountsPage: React.FC = () => {
  const { message: msg } = App.useApp();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingAccount, setEditingAccount] = useState<Account | null>(null);
  const [searchText, setSearchText] = useState('');
  const [tags, setTags] = useState<Tag[]>([]);
  const [tagFilter, setTagFilter] = useState<number[]>([]);
  const [tagModalVisible, setTagModalVisible] = useState(false);
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

  // 批量导出
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // 批量标签
  const [batchTagVisible, setBatchTagVisible] = useState(false);
  const [batchTagIds, setBatchTagIds] = useState<number[]>([]);
  const [batchTagMode, setBatchTagMode] = useState<'add' | 'replace' | 'remove'>('add');
  const [batchTagFromId, setBatchTagFromId] = useState<number | undefined>(undefined);
  const [batchTagLoading, setBatchTagLoading] = useState(false);

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
        page: currentPage,
        pageSize,
        ownerOnly,
        sortBy: sortField,
        sortOrder,
        tagIds: tagFilter,
      });
      setAccounts(data.accounts);
      setTotal(data.total);
    } catch {
      msg.error('加载账号失败');
    } finally {
      setLoading(false);
    }
  }, [currentPage, msg, ownerOnly, pageSize, searchText, sortField, sortOrder, tagFilter]);

  const loadTags = useCallback(async () => {
    try {
      const { data } = await getTags();
      setTags(data.tags);
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
    void loadTags();
  }, [loadAccounts, loadTags]);

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
        try { await deleteAccount(id); msg.success('已删除'); void loadAccounts(); }
        catch { msg.error('删除失败'); }
      },
    });
  };

  const handleMarkUnusable = async (id: number) => {
    try {
      await markAccountUnusable(id);
      msg.success('已标记为无法使用');
      void loadAccounts();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '标记失败'));
    }
  };

  const handleClearStatus = async (id: number) => {
    try {
      await clearAccountStatus(id);
      msg.success('已恢复正常状态');
      void loadAccounts();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '操作失败'));
    }
  };

  const writeClipboard = (text: string, successMsg: string) => {
    navigator.clipboard.writeText(text).then(
      () => msg.success(successMsg),
      () => msg.error('复制失败，请检查浏览器剪贴板权限'),
    );
  };

  const copyToClipboard = (text: string, label: string) => {
    writeClipboard(text, `${label}已复制`);
  };

  const copyFullAccount = (record: Account) => {
    const parts = [record.email, record.password, record.recovery_email || '', record.totp_secret || ''];
    writeClipboard(parts.join('----'), '账号信息已复制');
  };

  const copyTOTPCode = (secret: string) => {
    try {
      const { code } = generateTOTP(secret);
      writeClipboard(code, `2FA 验证码已复制: ${code}`);
    } catch {
      msg.error('生成验证码失败');
    }
  };

  const handleExportSingle = (account: Account) => {
    downloadAccountsTxt([account]);
    msg.success('已导出 1 个账号');
  };

  const selectedAccountTags = useMemo(() => {
    const idSet = new Set<number>(selectedRowKeys.map(Number));
    const tagMap = new Map<number, Tag>();
    for (const a of accounts) {
      if (idSet.has(a.id)) {
        for (const t of a.tags ?? []) {
          tagMap.set(t.id, t);
        }
      }
    }
    return Array.from(tagMap.values());
  }, [accounts, selectedRowKeys]);

  const handleExportSelected = () => {
    const idSet = new Set<number>(selectedRowKeys.map(Number));
    const selected = accounts.filter((a) => idSet.has(a.id));
    if (selected.length === 0) {
      msg.warning('请先勾选要导出的账号');
      return;
    }
    downloadAccountsTxt(selected);
    msg.success(`已导出 ${selected.length} 个账号`);
  };

  const handleBatchTagSubmit = async () => {
    if (batchTagIds.length === 0) {
      msg.warning('请选择标签');
      return;
    }
    if (batchTagMode === 'replace' && !batchTagFromId) {
      msg.warning('请选择要替换的原标签');
      return;
    }
    const ids = selectedRowKeys.map(Number);
    if (ids.length === 0) return;
    setBatchTagLoading(true);
    try {
      const { data } = await batchUpdateTags(ids, batchTagIds, batchTagMode, batchTagFromId);
      msg.success(data.message);
      setBatchTagVisible(false);
      setBatchTagIds([]);
      setBatchTagFromId(undefined);
      void loadAccounts();
    } catch (error: unknown) {
      msg.error(getErrorMessage(error, '操作失败'));
    } finally {
      setBatchTagLoading(false);
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
        setImportVisible(false); setImportText(''); void loadAccounts();
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
    onExportAccount: handleExportSingle,
    onLaunchAndLogin: handleLaunchAndLogin,
    onStopBrowser: handleStopBrowser,
    onMarkUnusable: handleMarkUnusable,
    onClearStatus: handleClearStatus,
  });

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() => {
    // v1 → v2 迁移: 顺手清掉旧 key, 放在 useState 初始化函数内避免模块顶层副作用
    try {
      for (const k of LEGACY_COLUMN_WIDTHS_KEYS) localStorage.removeItem(k);
    } catch { /* ignore */ }

    const defaults: Record<string, number> = {};
    for (const col of baseColumns) {
      const key = (col as { key?: string }).key;
      const width = (col as { width?: number }).width;
      if (key && width) defaults[key] = width;
    }
    try {
      const saved = localStorage.getItem(COLUMN_WIDTHS_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (typeof parsed === 'object' && parsed !== null) {
          const merged: Record<string, number> = { ...defaults };
          for (const [k, v] of Object.entries(parsed)) {
            if (defaults[k] === undefined) continue; // 丢弃已删除列的旧 key
            if (typeof v !== 'number' || v <= 0) continue;
            if (v > defaults[k] * MAX_COLUMN_WIDTH_FACTOR) continue; // 防误拖: 异常宽度回落默认
            merged[k] = v;
          }
          return merged;
        }
      }
    } catch { /* ignore */ }
    return defaults;
  });

  const handleColumnResize = (key: string) =>
    (_e: SyntheticEvent, { size }: ResizeCallbackData) => {
      setColumnWidths((prev) => {
        const next = { ...prev, [key]: size.width };
        try { localStorage.setItem(COLUMN_WIDTHS_STORAGE_KEY, JSON.stringify(next)); } catch { /* ignore */ }
        return next;
      });
    };

  // baseColumns 每次 render 都重建, useMemo 形同虚设; 直接计算更直白, 开销可忽略
  const validColumnKeys = new Set(
    baseColumns.map((c) => (c as { key?: string }).key).filter(Boolean) as string[],
  );
  const tableScrollX = Object.entries(columnWidths)
    .filter(([k]) => validColumnKeys.has(k))
    .reduce((sum, [, w]) => sum + w, 0) + SELECTION_COLUMN_WIDTH;

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
            mode="multiple"
            placeholder="标签"
            style={{ minWidth: 180, maxWidth: 360 }}
            value={tagFilter}
            onChange={(v) => { setTagFilter(v); setCurrentPage(1); }}
            allowClear
            showSearch
            options={tags.map((t) => ({ label: t.name, value: t.id }))}
            maxTagCount="responsive"
          />
        </Flex>
        <Flex gap={8} align="center">
          <Tooltip title="添加账号">
            <Button type="text" icon={<PlusOutlined />} onClick={handleAdd} />
          </Tooltip>
          <Tooltip title="批量导入">
            <Button type="text" icon={<ImportOutlined />} onClick={() => setImportVisible(true)} />
          </Tooltip>
          <Tooltip title="管理标签">
            <Button type="text" icon={<TagsOutlined />} onClick={() => setTagModalVisible(true)} />
          </Tooltip>
          <Tooltip title={selectedRowKeys.length === 0 ? '勾选账号后导出' : `导出已选 ${selectedRowKeys.length} 个账号 (.txt)`}>
            <Button
              type={selectedRowKeys.length > 0 ? 'primary' : 'text'}
              icon={<DownloadOutlined />}
              disabled={selectedRowKeys.length === 0}
              onClick={handleExportSelected}
              aria-label="批量导出已选账号"
            >
              {selectedRowKeys.length > 0 ? `导出 ${selectedRowKeys.length}` : null}
            </Button>
          </Tooltip>
          <Tooltip title={selectedRowKeys.length === 0 ? '勾选账号后打标签' : `为已选 ${selectedRowKeys.length} 个账号打标签`}>
            <Button
              type={selectedRowKeys.length > 0 ? 'primary' : 'text'}
              ghost={selectedRowKeys.length > 0}
              icon={<TagOutlined />}
              disabled={selectedRowKeys.length === 0}
              onClick={() => { setBatchTagIds([]); setBatchTagFromId(undefined); setBatchTagMode('add'); setBatchTagVisible(true); }}
            >
              {selectedRowKeys.length > 0 ? `标签 ${selectedRowKeys.length}` : null}
            </Button>
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
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <Table<Account>
          className="accounts-table-excel"
          components={tableComponents}
          columns={columns}
          dataSource={accounts}
          rowKey="id"
          loading={loading}
          size="small"
          scroll={{ x: tableScrollX }}
          pagination={false}
          onChange={handleTableChange}
          rowSelection={{
            selectedRowKeys,
            onChange: setSelectedRowKeys,
            preserveSelectedRowKeys: true,
          }}
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
        tags={tags}
        onClose={() => setModalVisible(false)}
        onSuccess={() => { void loadAccounts(); }}
      />

      <TagManageModal
        visible={tagModalVisible}
        onClose={() => setTagModalVisible(false)}
        onChange={() => { void loadTags(); void loadAccounts(); }}
      />

      <Modal
        title={`批量标签 (${selectedRowKeys.length} 个账号)`}
        open={batchTagVisible}
        onCancel={() => setBatchTagVisible(false)}
        onOk={handleBatchTagSubmit}
        confirmLoading={batchTagLoading}
        okText="确认"
        destroyOnClose
      >
        <Flex vertical gap={16} style={{ marginTop: 16 }}>
          <div>
            <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>操作方式</Text>
            <Radio.Group value={batchTagMode} onChange={(e) => { setBatchTagMode(e.target.value); setBatchTagIds([]); setBatchTagFromId(undefined); }}>
              <Radio.Button value="add">追加</Radio.Button>
              <Radio.Button value="replace">替换</Radio.Button>
              <Radio.Button value="remove">移除</Radio.Button>
            </Radio.Group>
          </div>
          {batchTagMode === 'replace' ? (
            <>
              <div>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>原标签（从哪个标签替换）</Text>
                <Select
                  placeholder="选择要替换掉的标签"
                  style={{ width: '100%' }}
                  value={batchTagFromId}
                  onChange={setBatchTagFromId}
                  options={selectedAccountTags.map((t) => ({ label: t.name, value: t.id }))}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>新标签（替换为）</Text>
                <Select
                  mode="multiple"
                  placeholder="选择新标签"
                  style={{ width: '100%' }}
                  value={batchTagIds}
                  onChange={setBatchTagIds}
                  options={tags.filter((t) => t.id !== batchTagFromId).map((t) => ({ label: t.name, value: t.id }))}
                />
              </div>
            </>
          ) : batchTagMode === 'remove' ? (
            <div>
              <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>选择要移除的标签</Text>
              <Select
                mode="multiple"
                placeholder="选择标签"
                style={{ width: '100%' }}
                value={batchTagIds}
                onChange={setBatchTagIds}
                options={selectedAccountTags.map((t) => ({ label: t.name, value: t.id }))}
              />
            </div>
          ) : (
            <div>
              <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>选择要添加的标签</Text>
              <Select
                mode="multiple"
                placeholder="选择标签"
                style={{ width: '100%' }}
                value={batchTagIds}
                onChange={setBatchTagIds}
                options={tags.map((t) => ({ label: t.name, value: t.id }))}
              />
            </div>
          )}
        </Flex>
      </Modal>
    </div>
  );
};

export default AccountsPage;
