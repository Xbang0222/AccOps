import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Button,
  Input,
  Select,
  Typography,
  Space,
  App,
  Tag,
  Flex,
  Modal,
  Row,
  Col,
} from 'antd';
import {
  LoginOutlined,
  TeamOutlined,
  UserAddOutlined,
  CheckCircleOutlined,
  UserDeleteOutlined,
  LogoutOutlined,
  GlobalOutlined,
  ThunderboltOutlined,
  LoadingOutlined,
  CheckOutlined,
  CloseOutlined,
  SwapOutlined,
  ArrowLeftOutlined,
  PoweroffOutlined,
  SyncOutlined,
  StopOutlined,
} from '@ant-design/icons';
import type { Account } from '@/types';
import { discoverFamily } from '@/api';
import { useAutomationWs } from '@/hooks/useAutomationWs';

const { Text } = Typography;

interface OperationPanelProps {
  account: Account;
  browserRunning: boolean;
  browserLoading: boolean;
  onBack: () => void;
  onLaunchBrowser: () => void;
  onStopBrowser: () => void;
  onRefreshAccount?: () => void;
}

/** 操作定义 */
interface OpDef {
  key: string;
  label: string;
  icon: React.ReactNode;
  color: string;
  bg: string;
  needBrowser: boolean;
  fields?: { name: string; placeholder: string }[];
  danger?: boolean;
  /** 可见性: 'any'=所有人, 'owner'=家庭组管理员, 'member'=家庭组成员, 'no-group'=未加入家庭组 */
  role?: 'any' | 'owner' | 'member' | 'no-group';
}

const OPERATIONS: OpDef[] = [
  {
    key: 'browser',
    label: '启动浏览器',
    icon: <GlobalOutlined />,
    color: '#4285f4',
    bg: '#e8f0fe',
    needBrowser: false,
  },
  {
    key: 'login',
    label: '自动登录',
    icon: <LoginOutlined />,
    color: '#1677ff',
    bg: '#e6f4ff',
    needBrowser: true,
  },
  {
    key: 'family-discover',
    label: '同步家庭组',
    icon: <SyncOutlined />,
    color: '#1677ff',
    bg: '#e6f4ff',
    needBrowser: false,
  },
  {
    key: 'family-create',
    label: '创建家庭组',
    icon: <TeamOutlined />,
    color: '#722ed1',
    bg: '#f9f0ff',
    needBrowser: true,
    role: 'no-group',
  },
  {
    key: 'family-invite',
    label: '发送邀请',
    icon: <UserAddOutlined />,
    color: '#13c2c2',
    bg: '#e6fffb',
    needBrowser: true,
    fields: [{ name: 'invite_email', placeholder: '被邀请人邮箱' }],
    role: 'owner',
  },
  {
    key: 'family-accept',
    label: '接受邀请',
    icon: <CheckCircleOutlined />,
    color: '#52c41a',
    bg: '#f6ffed',
    needBrowser: true,
    role: 'no-group',
  },
  {
    key: 'family-remove',
    label: '移除成员',
    icon: <UserDeleteOutlined />,
    color: '#ff4d4f',
    bg: '#fff2f0',
    needBrowser: true,
    fields: [{ name: 'member_email', placeholder: '要移除的成员邮箱' }],
    danger: true,
    role: 'owner',
  },
  {
    key: 'family-leave',
    label: '退出家庭组',
    icon: <LogoutOutlined />,
    color: '#fa8c16',
    bg: '#fff7e6',
    needBrowser: true,
    danger: true,
    role: 'member',
  },
  {
    key: 'family-delete',
    label: '删除家庭组',
    icon: <LogoutOutlined />,
    color: '#ff4d4f',
    bg: '#fff2f0',
    needBrowser: true,
    danger: true,
    role: 'owner',
  },
  {
    key: 'replace',
    label: '替换成员',
    icon: <SwapOutlined />,
    color: '#722ed1',
    bg: '#f9f0ff',
    needBrowser: true,
    fields: [
      { name: 'old_email', placeholder: '旧成员邮箱 (将被移除)' },
      { name: 'new_email', placeholder: '新成员邮箱 (将被邀请)' },
    ],
    role: 'owner',
  },
];

const OperationPanel: React.FC<OperationPanelProps> = ({
  account,
  browserRunning,
  browserLoading,
  onBack,
  onLaunchBrowser,
  onStopBrowser,
  onRefreshAccount,
}) => {
  const { message: msg } = App.useApp();

  // REST 操作的独立 running 状态 (discover)
  const [discoverRunning, setDiscoverRunning] = useState(false);
  // 各操作的最终状态: 'success' | 'fail'
  const [opResults, setOpResults] = useState<Record<string, 'success' | 'fail'>>({});
  // 子弹窗
  const [activeOp, setActiveOp] = useState<OpDef | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  // 多邮箱选择 (邀请/移除)
  const [selectedEmails, setSelectedEmails] = useState<string[]>([]);

  const stepsEndRef = useRef<HTMLDivElement | null>(null);

  const ws = useAutomationWs({
    onSuccess: (opKey, message) => {
      setOpResults((prev) => ({ ...prev, [opKey]: 'success' }));
      msg.success(message);
      onRefreshAccount?.();
    },
    onFail: (opKey, message) => {
      setOpResults((prev) => ({ ...prev, [opKey]: 'fail' }));
      msg.warning(message);
    },
    onError: (opKey, message) => {
      setOpResults((prev) => ({ ...prev, [opKey]: 'fail' }));
      msg.error(message);
    },
  });

  const { runningOp, steps, resultMsg } = ws;
  const { cancel } = ws;

  // 自动滚动到最新步骤
  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [steps]);

  /** 通过 WebSocket 执行操作 */
  const executeViaWs = useCallback(
    (action: string, extra: Record<string, string> = {}, opKey?: string) => {
      ws.execute(account.id, action, extra, opKey);
    },
    [account.id, ws.execute],
  );

  /** 替换成员: 后端一体化操作 (移除旧成员 → 邀请新成员 → 可选自动接受) */
  const executeReplace = useCallback(
    (oldEmail: string, newEmail: string) => {
      executeViaWs('family-replace', { old_email: oldEmail, new_email: newEmail });
    },
    [executeViaWs],
  );

  /** 纯 HTTP 同步家庭组 */
  const handleDiscover = async () => {
    setDiscoverRunning(true);
    try {
      const { data } = await discoverFamily(account.id);
      if (data.success) {
        msg.success(data.message || '同步成功');
        setOpResults((prev) => ({ ...prev, 'family-discover': 'success' }));
        onRefreshAccount?.();
      } else if (data.cookies_expired) {
        msg.warning(data.message || 'Cookies 已过期，请重新登录');
        setOpResults((prev) => ({ ...prev, 'family-discover': 'fail' }));
      } else {
        msg.warning(data.message || '同步失败');
        setOpResults((prev) => ({ ...prev, 'family-discover': 'fail' }));
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || '同步请求失败';
      msg.error(errMsg);
      setOpResults((prev) => ({ ...prev, 'family-discover': 'fail' }));
    } finally {
      setDiscoverRunning(false);
    }
  };

  /** 点击卡片 */
  const handleCardClick = (op: OpDef) => {
    if (op.key === 'browser') {
      if (browserRunning) { cancel(); onStopBrowser(); } else { onLaunchBrowser(); }
      return;
    }
    // family-discover 用 REST API, 不需要浏览器
    if (op.key === 'family-discover') {
      handleDiscover();
      return;
    }
    if (op.needBrowser && !browserRunning) {
      msg.warning('请先启动浏览器');
      return;
    }
    // family-delete 映射为 family-leave (后端统一处理)
    const actionKey = op.key === 'family-delete' ? 'family-leave' : op.key;
    if (!op.fields) {
      // 无输入字段, 直接执行
      executeViaWs(actionKey, {}, op.key);
      return;
    }
    // 有输入字段, 弹出子弹窗
    setFormValues({});
    setSelectedEmails([]);
    setActiveOp(op);
  };

  /** 子弹窗提交 */
  const handleSubModalOk = () => {
    if (!activeOp) return;

    if (activeOp.key === 'family-invite') {
      if (selectedEmails.length === 0) {
        msg.warning('请输入至少一个邮箱');
        return;
      }
      executeViaWs('family-invite', { invite_email: selectedEmails.join(',') });
    } else if (activeOp.key === 'family-remove') {
      if (selectedEmails.length === 0) {
        msg.warning('请输入至少一个邮箱');
        return;
      }
      executeViaWs('family-remove', { member_email: selectedEmails.join(',') });
    } else if (activeOp.key === 'replace') {
      if (!formValues.old_email?.trim()) {
        msg.warning('请输入旧成员邮箱');
        return;
      }
      if (!formValues.new_email?.trim()) {
        msg.warning('请输入新成员邮箱');
        return;
      }
      executeReplace(formValues.old_email.trim(), formValues.new_email.trim());
    } else {
      for (const f of activeOp.fields || []) {
        if (!formValues[f.name]?.trim()) {
          msg.warning(`请输入${f.placeholder}`);
          return;
        }
      }
      const extra: Record<string, string> = {};
      for (const f of activeOp.fields || []) {
        extra[f.name] = formValues[f.name].trim();
      }
      executeViaWs(activeOp.key, extra);
    }
    setActiveOp(null);
  };

  /** 处理邀请/移除 Select 粘贴: 支持逗号、换行、分号分隔多邮箱 */
  const handleEmailSearch = (value: string) => {
    if (/[,;\n\r]/.test(value)) {
      const emails = value
        .split(/[,;\n\r\s]+/)
        .map((e) => e.trim())
        .filter((e) => e && e.includes('@'));
      if (emails.length > 0) {
        setSelectedEmails((prev) => [...new Set([...prev, ...emails])]);
      }
    }
  };

  const isAnyRunning = runningOp !== null || discoverRunning;

  // 计算当前账号的家庭组角色
  const hasGroup = !!account.family_group_id;
  const isOwner = !!account.is_family_owner;
  const isMember = hasGroup && !isOwner;
  const isFull = (account.family_member_count ?? 0) >= 6; // Google 家庭组最多 6 人

  // 根据角色过滤可见操作
  const visibleOps = OPERATIONS.filter((op) => {
    if (!op.role || op.role === 'any') return true;
    if (op.role === 'owner') {
      if (!isOwner) return false;
      // 满员时隐藏邀请和替换
      if (isFull && (op.key === 'family-invite' || op.key === 'replace')) return false;
      return true;
    }
    if (op.role === 'member') return isMember;
    if (op.role === 'no-group') return !hasGroup;
    return true;
  });

  return (
    <div>
      {/* 顶栏 */}
      <Flex align="center" gap={12} style={{ marginBottom: 24 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={onBack}
          style={{ padding: '4px 8px' }}
        />
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            background: 'linear-gradient(135deg, #4285f4, #34a853)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <ThunderboltOutlined style={{ color: '#fff', fontSize: 16 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text strong style={{ fontSize: 16 }}>
            {account.email}
          </Text>
          <br />
          {browserRunning ? (
            <Tag color="green" style={{ margin: 0, fontSize: 11 }}>
              浏览器运行中
            </Tag>
          ) : (
            <Tag style={{ margin: 0, fontSize: 11 }}>浏览器未启动</Tag>
          )}
        </div>
      </Flex>

      {/* 操作卡片网格 */}
      <Row gutter={[12, 12]}>
        {visibleOps.map((op) => {
          const result = opResults[op.key];
          const isBrowser = op.key === 'browser';
          const isThisRunning = runningOp === op.key || (op.key === 'family-discover' && discoverRunning);
          const disabled =
            (isBrowser && browserLoading) ||
            (!isBrowser && isAnyRunning) ||
            (!isBrowser && op.needBrowser && !browserRunning);

          let label = op.label;
          let cardColor = op.color;
          let cardBg = op.bg;
          let cardIcon = op.icon;
          if (isBrowser) {
            if (browserLoading) {
              label = '处理中…';
              cardIcon = <LoadingOutlined />;
            } else if (browserRunning) {
              label = '关闭浏览器';
              cardColor = '#ff4d4f';
              cardBg = '#fff2f0';
              cardIcon = <PoweroffOutlined />;
            }
          }

          return (
            <Col span={8} key={op.key}>
              <div
                onClick={() => !disabled && handleCardClick(op)}
                style={{
                  border: `1px solid ${
                    isThisRunning
                      ? '#1677ff'
                      : result === 'success'
                        ? '#b7eb8f'
                        : result === 'fail'
                          ? '#ffa39e'
                          : '#f0f0f0'
                  }`,
                  borderRadius: 12,
                  padding: '20px 12px 16px',
                  textAlign: 'center',
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  opacity: disabled ? 0.45 : 1,
                  background: isThisRunning
                    ? '#f0f5ff'
                    : result === 'success'
                      ? '#f6ffed'
                      : result === 'fail'
                        ? '#fff2f0'
                        : '#fff',
                  transition: 'all 0.2s',
                  position: 'relative',
                }}
                onMouseEnter={(e) => {
                  if (!disabled) e.currentTarget.style.borderColor = cardColor;
                }}
                onMouseLeave={(e) => {
                  if (!disabled)
                    e.currentTarget.style.borderColor = isThisRunning
                      ? '#1677ff'
                      : result === 'success'
                        ? '#b7eb8f'
                        : result === 'fail'
                          ? '#ffa39e'
                          : '#f0f0f0';
                }}
              >
                {/* 状态角标 */}
                {(result || isThisRunning) && (
                  <div style={{ position: 'absolute', top: 8, right: 8 }}>
                    {isThisRunning ? (
                      <LoadingOutlined style={{ color: '#1677ff', fontSize: 14 }} />
                    ) : result === 'success' ? (
                      <CheckOutlined style={{ color: '#52c41a', fontSize: 14 }} />
                    ) : (
                      <CloseOutlined style={{ color: '#ff4d4f', fontSize: 14 }} />
                    )}
                  </div>
                )}
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 12,
                    background: cardBg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 10px',
                    fontSize: 20,
                    color: cardColor,
                  }}
                >
                  {cardIcon}
                </div>
                <Text strong style={{ fontSize: 13 }}>
                  {label}
                </Text>
              </div>
            </Col>
          );
        })}
      </Row>

      {/* 实时步骤日志 */}
      {steps.length > 0 && (
        <div
          style={{
            marginTop: 20,
            background: '#fafafa',
            border: '1px solid #f0f0f0',
            borderRadius: 10,
            padding: '12px 16px',
            maxHeight: 260,
            overflowY: 'auto',
            fontFamily: "'SF Mono', Consolas, monospace",
            fontSize: 12,
            lineHeight: '22px',
          }}
        >
          {runningOp && (
            <Flex justify="flex-end" style={{ marginBottom: 8 }}>
              <Button
                size="small"
                danger
                icon={<StopOutlined />}
                onClick={() => cancel()}
              >
                取消
              </Button>
            </Flex>
          )}
          {steps.map((s, i) => (
            <div key={i} style={{ minWidth: 0 }}>
                <span
                  style={{
                    color:
                      s.status === 'fail'
                        ? '#ff4d4f'
                        : s.status === 'ok'
                          ? '#52c41a'
                          : s.status === 'skip'
                            ? '#faad14'
                            : '#333',
                  }}
                >
                  {s.name}
                </span>
                {s.message && (
                  <span style={{ color: '#999', marginLeft: 8 }}>{s.message}</span>
                )}
                {s.duration_ms ? (
                  <span style={{ color: '#bbb', marginLeft: 6 }}>({s.duration_ms}ms)</span>
                ) : null}
            </div>
          ))}
          <div ref={stepsEndRef} />
        </div>
      )}

      {/* 最终结果消息 */}
      {resultMsg && !isAnyRunning && (
        <div
          style={{
            marginTop: 12,
            padding: '8px 12px',
            borderRadius: 8,
            fontSize: 13,
            background: opResults[Object.keys(opResults).pop()!] === 'success' ? '#f6ffed' : '#fff2f0',
            border: `1px solid ${opResults[Object.keys(opResults).pop()!] === 'success' ? '#b7eb8f' : '#ffa39e'}`,
          }}
        >
          {resultMsg}
        </div>
      )}

      {/* 子弹窗 */}
      <Modal
        open={!!activeOp}
        title={activeOp?.label}
        onCancel={() => setActiveOp(null)}
        onOk={handleSubModalOk}
        okText="执行"
        cancelText="取消"
        okButtonProps={{ danger: activeOp?.danger }}
        width={420}
        destroyOnClose
      >
        <div style={{ marginTop: 12 }}>
          {/* 邀请: Select tags 模式，粘贴自动拆分 */}
          {activeOp?.key === 'family-invite' && (
            <Select
              mode="tags"
              style={{ width: '100%' }}
              placeholder="输入或粘贴邮箱，回车添加（支持逗号、换行分隔）"
              value={selectedEmails}
              onChange={setSelectedEmails}
              onSearch={handleEmailSearch}
              tokenSeparators={[',', ';', '\n', '\t', ' ']}
              open={false}
              suffixIcon={null}
              notFoundContent={null}
            />
          )}

          {/* 移除: Select tags 模式 */}
          {activeOp?.key === 'family-remove' && (
            <Select
              mode="tags"
              style={{ width: '100%' }}
              placeholder="输入或粘贴邮箱，回车添加（支持逗号、换行分隔）"
              value={selectedEmails}
              onChange={setSelectedEmails}
              onSearch={handleEmailSearch}
              tokenSeparators={[',', ';', '\n', '\t', ' ']}
              open={false}
              suffixIcon={null}
              notFoundContent={null}
            />
          )}

          {/* 替换 / 其他操作: 保持 Input 模式 */}
          {activeOp && !['family-invite', 'family-remove'].includes(activeOp.key) && (
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              {activeOp.fields?.map((f) => (
                <Input
                  key={f.name}
                  placeholder={f.placeholder}
                  value={formValues[f.name] || ''}
                  onChange={(e) =>
                    setFormValues((prev) => ({ ...prev, [f.name]: e.target.value }))
                  }
                  onPressEnter={handleSubModalOk}
                />
              ))}
            </Space>
          )}
        </div>
      </Modal>
    </div>
  );
};

export default OperationPanel;
