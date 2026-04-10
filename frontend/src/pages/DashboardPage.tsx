import React, { useState, useEffect } from 'react';
import {
  Card,
  Statistic,
  Typography,
  List,
  message,
  Flex,
} from 'antd';
import {
  ContactsOutlined,
  TeamOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { getDashboardStats } from '@/api';
import type { DashboardStats } from '@/api/dashboard';

const { Text } = Typography;

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const { data } = await getDashboardStats();
      setStats(data);
    } catch {
      message.error('加载统计数据失败');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (text: string | null) => {
    if (!text) return '-';
    const date = new Date(text + 'Z');
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="fade-in" style={{ flex: 1, overflowY: 'auto' }}>
      {/* 顶部统计卡片 */}
      <Flex gap={16} wrap style={{ marginBottom: 24 }}>
        <Card loading={loading} style={{ flex: 1, minWidth: 200 }} hoverable>
          <Statistic
            title="总账号数"
            value={stats?.total_accounts ?? 0}
            prefix={<ContactsOutlined style={{ color: '#4285f4' }} />}
          />
        </Card>
        <Card loading={loading} style={{ flex: 1, minWidth: 200 }} hoverable>
          <Statistic
            title="分组数"
            value={stats?.total_groups ?? 0}
            prefix={<TeamOutlined style={{ color: '#9254de' }} />}
          />
        </Card>
      </Flex>

      <Flex gap={16} wrap>

        {/* 最近更新 */}
        <Card
          title={
            <Flex align="center" gap={8}>
              <ClockCircleOutlined style={{ color: '#1890ff' }} />
              <span>最近更新</span>
            </Flex>
          }
          loading={loading}
          style={{ flex: 1, minWidth: 300 }}
          styles={{ body: { padding: 0 } }}
        >
          {stats?.recent_accounts && stats.recent_accounts.length > 0 ? (
            <List
              dataSource={stats.recent_accounts}
              renderItem={(item) => (
                <List.Item style={{ padding: '10px 24px' }}>
                  <Flex justify="space-between" align="center" style={{ width: '100%' }}>
                    <Text>{item.email}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {formatTime(item.updated_at)}
                    </Text>
                  </Flex>
                </List.Item>
              )}
            />
          ) : (
            <div style={{ padding: 24 }}>
              <Text type="secondary">暂无数据</Text>
            </div>
          )}
        </Card>
      </Flex>
    </div>
  );
};

export default DashboardPage;
