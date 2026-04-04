/** Ant Design 主题配置 */
import type { ThemeConfig } from 'antd';
import { theme as antTheme } from 'antd';

export function getThemeConfig(isDark: boolean): ThemeConfig {
  return {
    algorithm: isDark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
    token: {
      // 品牌色 - Google 蓝
      colorPrimary: '#4285f4',
      colorInfo: '#4285f4',
      // 圆角
      borderRadius: 8,
      borderRadiusLG: 12,
      // 字体
      fontFamily:
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
      // 阴影
      boxShadow: isDark
        ? '0 2px 8px rgba(0, 0, 0, 0.3)'
        : '0 2px 8px rgba(0, 0, 0, 0.06)',
      boxShadowSecondary: isDark
        ? '0 4px 16px rgba(0, 0, 0, 0.4)'
        : '0 4px 16px rgba(0, 0, 0, 0.08)',
    },
    components: {
      Layout: {
        headerBg: isDark ? '#141414' : '#ffffff',
        siderBg: isDark ? '#141414' : '#ffffff',
        bodyBg: isDark ? '#0a0a0a' : '#f5f7fa',
      },
      Menu: {
        itemBorderRadius: 8,
        itemMarginInline: 8,
        itemHeight: 44,
      },
      Button: {
        borderRadius: 8,
        controlHeight: 36,
      },
      Card: {
        borderRadiusLG: 12,
      },
      Table: {
        borderRadiusLG: 12,
        headerBg: isDark ? '#1f1f1f' : '#fafbfc',
      },
      Input: {
        borderRadius: 8,
      },
      Select: {
        borderRadius: 8,
      },
      Modal: {
        borderRadiusLG: 16,
      },
    },
  };
}
