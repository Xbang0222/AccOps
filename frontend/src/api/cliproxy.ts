/** CLIProxyAPI 集成 API */
import client, { API_PREFIX } from './client'

export interface CliproxyUploadItem {
  account_id: number
  email: string
  success: boolean
  message: string
}

export interface CliproxyUploadResponse {
  total: number
  succeeded: number
  failed: number
  items: CliproxyUploadItem[]
}

export interface CliproxyStatus {
  configured: boolean
  reachable: boolean
  status_code?: number
  message: string
}

export const uploadToCliproxy = (accountIds: number[]) =>
  client.post<CliproxyUploadResponse>(`${API_PREFIX}/cliproxy/upload`, {
    account_ids: accountIds,
  })

export const getCliproxyStatus = () =>
  client.get<CliproxyStatus>(`${API_PREFIX}/cliproxy/status`)
