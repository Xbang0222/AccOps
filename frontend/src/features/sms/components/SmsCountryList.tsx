import { Button, Empty, Flex, Input, Spin, Tag, Tooltip, Typography } from 'antd'
import { LoadingOutlined, SearchOutlined, SettingOutlined, ShoppingCartOutlined } from '@ant-design/icons'

import type { SmsCountryPrice } from '@/api/sms'

const { Text } = Typography

interface SmsCountryListProps {
  activeProviderApiKey?: string
  buyLoading: string | null
  countries: SmsCountryPrice[]
  countryLoading: boolean
  countrySearch: string
  countrySortBy: 'count' | 'price'
  defaultService: string
  onBuyNumber: (serviceCode: string, countryId: number) => void
  onChangeSearch: (value: string) => void
  onChangeSortBy: (value: 'count' | 'price') => void
  onOpenConfig: () => void
}

export function SmsCountryList({
  activeProviderApiKey,
  buyLoading,
  countries,
  countryLoading,
  countrySearch,
  countrySortBy,
  defaultService,
  onBuyNumber,
  onChangeSearch,
  onChangeSortBy,
  onOpenConfig,
}: SmsCountryListProps) {
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
            style={{ fontSize: 11, cursor: 'pointer', color: countrySortBy === 'count' ? '#1677ff' : '#999', whiteSpace: 'nowrap' }}
            onClick={() => onChangeSortBy('count')}
          >
            数量↓
          </Text>
          <Text
            style={{ fontSize: 11, cursor: 'pointer', color: countrySortBy === 'price' ? '#1677ff' : '#999', whiteSpace: 'nowrap' }}
            onClick={() => onChangeSortBy('price')}
          >
            价格↑
          </Text>
        </Flex>
        <Tooltip title="配置">
          <Button size="small" icon={<SettingOutlined />} onClick={onOpenConfig} />
        </Tooltip>
      </Flex>

      <div style={{ flex: 1, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 8, background: '#fff' }}>
        {!activeProviderApiKey ? (
          <Empty description="请先配置提供商" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 40 }} />
        ) : countryLoading ? (
          <div style={{ padding: 40, textAlign: 'center' }}><Spin /></div>
        ) : countries.length === 0 ? (
          <Empty description="暂无可用号码" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 40 }} />
        ) : (
          countries.map((country) => (
            <div
              key={country.country_id}
              className="hover-card"
              style={{
                padding: '7px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                borderBottom: '1px solid #f5f5f5',
                cursor: 'pointer',
                transition: 'background 0.15s',
              }}
              onMouseEnter={(event) => {
                event.currentTarget.style.background = '#e6f4ff'
              }}
              onMouseLeave={(event) => {
                event.currentTarget.style.background = 'transparent'
              }}
              onClick={() => onBuyNumber(defaultService, country.country_id)}
            >
              <Text ellipsis style={{ flex: 1, fontSize: 12 }}>
                {country.country_name}
                {country.phone_code ? <Text type="secondary" style={{ fontSize: 11 }}> ({country.phone_code})</Text> : null}
              </Text>
              <Tag style={{ margin: 0, fontSize: 11 }}>{country.count}</Tag>
              <Text type="secondary" style={{ fontSize: 11, minWidth: 45, textAlign: 'right' }}>${country.price}</Text>
              {buyLoading === `${country.country_id}` ? (
                <LoadingOutlined style={{ fontSize: 16, color: '#1677ff' }} />
              ) : (
                <ShoppingCartOutlined
                  style={{ fontSize: 16, color: '#52c41a', transition: 'all 0.2s' }}
                  onMouseEnter={(event) => {
                    event.currentTarget.style.fontSize = '20px'
                    event.currentTarget.style.color = '#389e0d'
                  }}
                  onMouseLeave={(event) => {
                    event.currentTarget.style.fontSize = '16px'
                    event.currentTarget.style.color = '#52c41a'
                  }}
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
