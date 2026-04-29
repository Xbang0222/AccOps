import { Button, Empty, Flex, Input, Spin, Tag, Tooltip, Typography, theme as antTheme } from 'antd'
import { LoadingOutlined, SearchOutlined, SettingOutlined, ShoppingCartOutlined } from '@ant-design/icons'

import type { SmsCountryPrice } from '@/api/sms'

import { MAX_CONCURRENT_BUY } from '../constants'
import { hasInsufficientBalance } from '../utils'

const { Text } = Typography

interface SmsCountryListProps {
  activeProviderApiKey?: string
  atConcurrentCap: boolean
  balance?: string
  concurrentCount: number
  countries: SmsCountryPrice[]
  countryLoading: boolean
  countrySearch: string
  countrySortBy: 'count' | 'price'
  defaultService: string
  isBuyLoading: (countryId: number) => boolean
  onBuyNumber: (serviceCode: string, countryId: number) => void
  onChangeSearch: (value: string) => void
  onChangeSortBy: (value: 'count' | 'price') => void
  onOpenConfig: () => void
}

export function SmsCountryList({
  activeProviderApiKey,
  atConcurrentCap,
  balance,
  concurrentCount,
  countries,
  countryLoading,
  countrySearch,
  countrySortBy,
  defaultService,
  isBuyLoading,
  onBuyNumber,
  onChangeSearch,
  onChangeSortBy,
  onOpenConfig,
}: SmsCountryListProps) {
  const { token } = antTheme.useToken()
  return (
    <div style={{ width: 340, flexShrink: 0, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Flex align="center" gap={8} style={{ marginBottom: 8 }}>
        <Input
          size="small"
          placeholder="搜索国家..."
          prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
          value={countrySearch}
          onChange={(event) => onChangeSearch(event.target.value)}
          allowClear
          style={{ flex: 1 }}
        />
        <Flex gap={4}>
          <Text
            style={{ fontSize: 11, cursor: 'pointer', color: countrySortBy === 'count' ? token.colorPrimary : token.colorTextTertiary, whiteSpace: 'nowrap' }}
            onClick={() => onChangeSortBy('count')}
          >
            数量↓
          </Text>
          <Text
            style={{ fontSize: 11, cursor: 'pointer', color: countrySortBy === 'price' ? token.colorPrimary : token.colorTextTertiary, whiteSpace: 'nowrap' }}
            onClick={() => onChangeSortBy('price')}
          >
            价格↑
          </Text>
        </Flex>
        <Tooltip title="配置">
          <Button size="small" icon={<SettingOutlined />} onClick={onOpenConfig} />
        </Tooltip>
      </Flex>

      {atConcurrentCap ? (
        <Text type="warning" style={{ fontSize: 11, marginBottom: 6 }}>
          已达同时购买上限 ({concurrentCount}/{MAX_CONCURRENT_BUY})，完成或取消后再继续
        </Text>
      ) : null}

      <div style={{ flex: 1, overflowY: 'auto', border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 8, background: token.colorBgContainer }}>
        {!activeProviderApiKey ? (
          <Empty description="请先配置提供商" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 40 }} />
        ) : countryLoading ? (
          <div style={{ padding: 40, textAlign: 'center' }}><Spin /></div>
        ) : countries.length === 0 ? (
          <Empty description="暂无可用号码" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 40 }} />
        ) : (
          countries.map((country) => {
            const insufficient = hasInsufficientBalance(balance, country.price)
            const disabled = atConcurrentCap || insufficient
            const tooltipText = atConcurrentCap
              ? `已达同时购买上限 (${MAX_CONCURRENT_BUY})`
              : insufficient
                ? `余额不足 ($${balance ?? '未知'})`
                : ''
            const loading = isBuyLoading(country.country_id)

            return (
              <div
                key={country.country_id}
                className="hover-card"
                style={{
                  padding: '7px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  borderBottom: `1px solid ${token.colorBorderSecondary}`,
                  cursor: disabled ? 'not-allowed' : 'pointer',
                  opacity: disabled ? 0.5 : 1,
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(event) => {
                  if (!disabled) event.currentTarget.style.background = token.colorPrimaryBg
                }}
                onMouseLeave={(event) => {
                  event.currentTarget.style.background = 'transparent'
                }}
                onClick={() => {
                  if (disabled || loading) return
                  onBuyNumber(defaultService, country.country_id)
                }}
              >
                <Text ellipsis style={{ flex: 1, fontSize: 12 }}>
                  {country.country_name}
                  {country.phone_code ? <Text type="secondary" style={{ fontSize: 11 }}> ({country.phone_code})</Text> : null}
                </Text>
                <Tag style={{ margin: 0, fontSize: 11 }}>{country.count}</Tag>
                <Text type="secondary" style={{ fontSize: 11, minWidth: 45, textAlign: 'right' }}>${country.price}</Text>
                {loading ? (
                  <LoadingOutlined style={{ fontSize: 16, color: '#1677ff' }} />
                ) : (
                  <Tooltip title={tooltipText}>
                    <ShoppingCartOutlined
                      style={{
                        fontSize: 16,
                        color: disabled ? token.colorTextDisabled : '#52c41a',
                        transition: 'all 0.2s',
                      }}
                      onMouseEnter={(event) => {
                        if (disabled) return
                        event.currentTarget.style.fontSize = '20px'
                        event.currentTarget.style.color = '#389e0d'
                      }}
                      onMouseLeave={(event) => {
                        if (disabled) return
                        event.currentTarget.style.fontSize = '16px'
                        event.currentTarget.style.color = '#52c41a'
                      }}
                    />
                  </Tooltip>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
