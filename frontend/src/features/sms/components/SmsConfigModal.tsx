import { Button, Flex, Input, Modal, Select, Typography } from 'antd'
import { SafetyCertificateOutlined } from '@ant-design/icons'

import { PROVIDER_TYPES } from '../constants'

const { Text } = Typography

interface SmsConfigModalProps {
  configApiKey: string
  configCountries: { value: number | string; label: string }[]
  configCountry: number | string
  configCountryLoading: boolean
  configOpen: boolean
  configSaving: boolean
  configService: string
  configTestResult: { ok: boolean; msg: string } | null
  configTesting: boolean
  configType: string
  services: { code: string; name: string }[]
  onCancel: () => void
  onChangeApiKey: (value: string) => void
  onChangeCountry: (value: number | string) => void
  onChangeService: (value: string) => void
  onChangeType: (value: string) => void
  onSave: () => void
  onTest: () => void
}

export function SmsConfigModal({
  configApiKey,
  configCountries,
  configCountry,
  configCountryLoading,
  configOpen,
  configSaving,
  configService,
  configTestResult,
  configTesting,
  configType,
  services,
  onCancel,
  onChangeApiKey,
  onChangeCountry,
  onChangeService,
  onChangeType,
  onSave,
  onTest,
}: SmsConfigModalProps) {
  return (
    <Modal
      open={configOpen}
      title="接码配置"
      onCancel={onCancel}
      onOk={onSave}
      okText="保存"
      cancelText="取消"
      confirmLoading={configSaving}
      width={480}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 16 }}>
        <div>
          <Text strong>提供商</Text>
          <Select style={{ width: '100%', marginTop: 4 }} value={configType} onChange={onChangeType} options={PROVIDER_TYPES} />
        </div>
        <div>
          <Text strong>API Key</Text>
          <Flex gap={8} style={{ marginTop: 4 }}>
            <Input.Password
              placeholder="输入 API Key"
              value={configApiKey}
              onChange={(event) => onChangeApiKey(event.target.value)}
              style={{ flex: 1 }}
            />
            <Button icon={<SafetyCertificateOutlined />} loading={configTesting} onClick={onTest}>
              测试
            </Button>
          </Flex>
          {configTestResult ? (
            <Text
              type={configTestResult.ok ? 'success' : 'danger'}
              style={{ fontSize: 12, marginTop: 4, display: 'block' }}
            >
              {configTestResult.msg}
            </Text>
          ) : null}
        </div>
        <Flex gap={16}>
          <div style={{ flex: 1 }}>
            <Text strong>默认服务</Text>
            <Select
              style={{ width: '100%', marginTop: 4 }}
              value={configService}
              onChange={onChangeService}
              options={services.map((service) => ({ value: service.code, label: `${service.name} (${service.code})` }))}
              showSearch
              optionFilterProp="label"
              placeholder="选择服务"
            />
          </div>
          <div style={{ flex: 1 }}>
            <Text strong>默认国家</Text>
            <Select
              style={{ width: '100%', marginTop: 4 }}
              value={configCountry}
              onChange={onChangeCountry}
              options={configCountries}
              showSearch
              optionFilterProp="label"
              loading={configCountryLoading}
              placeholder="先选择服务"
            />
          </div>
        </Flex>
      </div>
    </Modal>
  )
}
