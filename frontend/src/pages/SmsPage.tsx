import React from 'react';
import { Spin } from 'antd';

import { SmsActivationCard } from '@/features/sms/components/SmsActivationCard';
import { SmsConfigModal } from '@/features/sms/components/SmsConfigModal';
import { SmsCountryList } from '@/features/sms/components/SmsCountryList';
import { SmsHistoryCard } from '@/features/sms/components/SmsHistoryCard';
import { useSmsPageController } from '@/features/sms/useSmsPageController';

const SmsPage: React.FC = () => {
  const controller = useSmsPageController();

  if (controller.loading) {
    return <div style={{ textAlign: 'center', padding: '100px 0' }}><Spin size="large" /></div>;
  }

  return (
    <div style={{ display: 'flex', height: '100%', gap: 12 }}>
      <SmsCountryList
        activeProviderApiKey={controller.activeProvider?.api_key}
        atConcurrentCap={controller.atConcurrentCap}
        balance={controller.activeProvider?.balance}
        concurrentCount={controller.concurrentCount}
        countries={controller.sortedCountries}
        countryLoading={controller.countryLoading}
        countrySearch={controller.countrySearch}
        countrySortBy={controller.countrySortBy}
        defaultService={controller.defaultService}
        isBuyLoading={controller.isBuyLoading}
        onBuyNumber={controller.handleBuyNumber}
        onChangeSearch={controller.setCountrySearch}
        onChangeSortBy={controller.setCountrySortBy}
        onOpenConfig={controller.openConfig}
      />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, height: '100%' }}>
        {controller.activeActivationList.length > 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 0,
              maxHeight: '50%',
              overflowY: 'auto',
              flexShrink: 0,
            }}
          >
            {controller.activeActivationList.map((activation) => (
              <SmsActivationCard
                key={activation.activation_id}
                activation={activation}
                polling={controller.isPolling(activation.activation_id)}
                onCancel={() => controller.handleCancel(activation.activation_id)}
                onClear={() => controller.handleClear(activation.activation_id)}
                onCopy={controller.copyText}
                onFinish={() => controller.handleFinish(activation.activation_id)}
              />
            ))}
          </div>
        ) : null}

        <SmsHistoryCard
          activeProvider={controller.activeProvider}
          history={controller.history}
          historyLoading={controller.historyLoading}
          historyPage={controller.historyPage}
          historyTotal={controller.historyTotal}
          onCopy={controller.copyText}
          onFinish={controller.handleHistoryFinish}
          onPageChange={controller.loadHistory}
          onRefresh={() => void controller.loadHistory(controller.historyPage)}
          onCancel={controller.handleHistoryCancel}
        />
      </div>

      <SmsConfigModal
        configApiKey={controller.configApiKey}
        configCountries={controller.configCountries}
        configCountry={controller.configCountry}
        configCountryLoading={controller.configCountryLoading}
        configOpen={controller.configOpen}
        configSaving={controller.configSaving}
        configService={controller.configService}
        configTestResult={controller.configTestResult}
        configTesting={controller.configTesting}
        configType={controller.configType}
        services={controller.services}
        onCancel={() => controller.setConfigOpen(false)}
        onChangeApiKey={controller.setConfigApiKey}
        onChangeCountry={controller.setConfigCountry}
        onChangeService={controller.handleConfigServiceChange}
        onChangeType={controller.handleConfigTypeChange}
        onSave={controller.handleSaveConfig}
        onTest={controller.handleTestApiKey}
      />
    </div>
  );
};

export default SmsPage;
