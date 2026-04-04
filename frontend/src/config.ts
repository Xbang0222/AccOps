/** 应用全局配置 — 从环境变量读取，支持 .env 文件覆盖 */
export function normalizeBaseUrl(value?: string | null): string | null {
  const trimmed = value?.trim()
  if (!trimmed) {
    return null
  }

  return trimmed.replace(/\/+$/, '')
}

export function getDefaultWsBaseUrl(location: Pick<Location, 'protocol' | 'host'>): string {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}`
}

const apiBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL) ?? ''

const wsBaseUrl =
  normalizeBaseUrl(import.meta.env.VITE_WS_BASE_URL) ??
  (typeof window !== 'undefined'
    ? getDefaultWsBaseUrl(window.location)
    : 'ws://127.0.0.1:5173')

export const config = {
  apiBaseUrl,
  wsBaseUrl,
} as const
