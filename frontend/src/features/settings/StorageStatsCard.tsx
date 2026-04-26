import { useCallback, useEffect, useState } from 'react';
import {
  Card,
  Button,
  Typography,
  Flex,
  App,
  Spin,
  Tag,
  Progress,
  Popconfirm,
  theme,
} from 'antd';
import {
  DeleteOutlined,
  DatabaseOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { getStorageStats, cleanAllCaches, type StorageStats } from '@/api';

const { Text, Paragraph } = Typography;

const ONE_GB = 1024 * 1024 * 1024;
const FIVE_GB = 5 * ONE_GB;

/** Bytes to human-readable string */
function formatBytes(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i >= 2 ? 1 : 0)} ${units[i]}`;
}

function getSizeTagColor(totalBytes: number): string | undefined {
  if (totalBytes > FIVE_GB) return 'red';
  if (totalBytes > ONE_GB) return 'orange';
  return 'default';
}

function StorageStatsCard() {
  const { message } = App.useApp();
  const { token } = theme.useToken();
  const [storageStats, setStorageStats] = useState<StorageStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await getStorageStats();
      setStorageStats(data);
    } catch {
      message.error('获取存储信息失败');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleCleanCaches = async () => {
    setCleaning(true);
    try {
      const { data } = await cleanAllCaches();
      const freedStr = formatBytes(data.freed_bytes);
      message.success(
        `清理完成！释放 ${freedStr}，清理了 ${data.cleaned_count} 个 profile`,
      );
      if (data.skipped_running > 0) {
        message.info(`跳过 ${data.skipped_running} 个运行中的浏览器`);
      }
      fetchStats();
    } catch {
      message.error('清理失败');
    } finally {
      setCleaning(false);
    }
  };

  return (
    <Card
      style={{ marginTop: 16 }}
      title={
        <Flex gap={8} align="center">
          <DatabaseOutlined />
          <span>存储清理</span>
          {storageStats && storageStats.total_bytes > 0 && (
            <Tag color={getSizeTagColor(storageStats.total_bytes)}>
              {formatBytes(storageStats.total_bytes)}
            </Tag>
          )}
        </Flex>
      }
      extra={
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={fetchStats}
          loading={loading}
        >
          刷新
        </Button>
      }
    >
      {loading && !storageStats ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Spin />
        </div>
      ) : storageStats ? (
        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              marginBottom: 16,
            }}
          >
            <div style={{ flex: 1 }}>
              <Text strong style={{ fontSize: 15 }}>
                浏览器 Profile 缓存
              </Text>
              <Paragraph
                type="secondary"
                style={{ marginBottom: 0, marginTop: 4 }}
              >
                每个浏览器 profile
                会自动生成 Chromium 缓存（模型、Safe Browsing、TTS
                引擎等），这些数据不影响登录态和 cookies，可以安全清理
              </Paragraph>
            </div>
          </div>

          <Flex gap={24} style={{ marginBottom: 16 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Profile 数量
              </Text>
              <div>
                <Text strong style={{ fontSize: 20 }}>
                  {storageStats.profile_count}
                </Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                总占用
              </Text>
              <div>
                <Text strong style={{ fontSize: 20 }}>
                  {formatBytes(storageStats.total_bytes)}
                </Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                可清理缓存
              </Text>
              <div>
                <Text
                  strong
                  style={{
                    fontSize: 20,
                    color:
                      storageStats.cleanable_bytes > ONE_GB
                        ? token.colorError
                        : undefined,
                  }}
                >
                  {formatBytes(storageStats.cleanable_bytes)}
                </Text>
              </div>
            </div>
            {storageStats.total_bytes > 0 && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  缓存占比
                </Text>
                <div>
                  <Progress
                    type="circle"
                    size={48}
                    percent={Math.round(
                      (storageStats.cleanable_bytes /
                        storageStats.total_bytes) *
                        100,
                    )}
                    strokeColor={
                      storageStats.cleanable_bytes > ONE_GB
                        ? token.colorError
                        : token.colorPrimary
                    }
                  />
                </div>
              </div>
            )}
          </Flex>

          <Popconfirm
            title="确认清理缓存？"
            description={`将清理 ${storageStats.profile_count} 个 profile 的 Chromium 缓存数据，预计释放 ${formatBytes(storageStats.cleanable_bytes)}。运行中的浏览器会自动跳过，cookies 和登录态不受影响。`}
            onConfirm={handleCleanCaches}
            okText="确认清理"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            placement="topRight"
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={cleaning}
              disabled={!storageStats.cleanable_bytes}
            >
              清理所有缓存
            </Button>
          </Popconfirm>
        </div>
      ) : (
        <Text type="secondary">无法获取存储信息</Text>
      )}
    </Card>
  );
}

export default StorageStatsCard;
