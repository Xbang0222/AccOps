import type { BrowserProfileForm } from '@/api/browser'

export function createDefaultBrowserProfile(accountId: number, email: string): BrowserProfileForm {
  return {
    name: email || `Profile-${accountId}`,
    account_id: accountId,
    proxy_type: '',
    proxy_host: '',
    proxy_port: null,
    proxy_username: '',
    proxy_password: '',
    user_agent: '',
    os_type: 'macos',
    timezone: '',
    language: 'en-US',
    screen_width: 1920,
    screen_height: 1080,
    webrtc_disabled: true,
    notes: '',
  }
}
