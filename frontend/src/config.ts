/** 应用全局配置 — 从环境变量读取，支持 .env 文件覆盖 */
export const config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  wsBaseUrl: import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000',
} as const;
