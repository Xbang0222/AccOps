/** 浏览器配置相关 API */
import client, { API_PREFIX } from './client';

export interface BrowserProfile {
  id: number;
  name: string;
  account_id: number | null;
  account_email: string;
  proxy_type: string;
  proxy_host: string;
  proxy_port: number | null;
  proxy_username: string;
  proxy_password: string;
  user_agent: string;
  os_type: string;
  timezone: string;
  language: string;
  screen_width: number;
  screen_height: number;
  webrtc_disabled: boolean;
  notes: string;
  status: 'running' | 'stopped';
  created_at: string;
  updated_at: string;
}

export type BrowserProfileForm = Omit<BrowserProfile, 'id' | 'account_email' | 'status' | 'created_at' | 'updated_at'>;

const BASE = `${API_PREFIX}/browser-profiles`;

export const getBrowserProfiles = () =>
  client.get<{ profiles: BrowserProfile[] }>(BASE);

export const getBrowserProfile = (id: number) =>
  client.get<BrowserProfile>(`${BASE}/${id}`);

export const createBrowserProfile = (data: BrowserProfileForm) =>
  client.post(BASE, data);

export const updateBrowserProfile = (id: number, data: BrowserProfileForm) =>
  client.put(`${BASE}/${id}`, data);

export const deleteBrowserProfile = (id: number) =>
  client.delete(`${BASE}/${id}`);

export const launchBrowser = (id: number) =>
  client.post(`${BASE}/${id}/launch`);

export const stopBrowser = (id: number) =>
  client.post(`${BASE}/${id}/stop`);

export const getBrowserStatus = (id: number) =>
  client.get(`${BASE}/${id}/status`);

export interface StorageStats {
  total_bytes: number;
  profile_count: number;
  cleanable_bytes: number;
  profiles: {
    dir_name: string;
    profile_id: number | null;
    total_bytes: number;
    cache_bytes: number;
  }[];
}

export interface CleanResult {
  cleaned_count: number;
  freed_bytes: number;
  skipped_running: number;
  pruned_dead: number;
}

export interface PruneDeadResult {
  pruned_count: number;
  pruned_profile_ids: number[];
}

export interface ForceClearResult {
  cleared_alive: number[];
  cleared_dead: number[];
  killed_pids: number[];
  total: number;
}

export const getStorageStats = () =>
  client.get<StorageStats>(`${BASE}/storage/stats`);

export const cleanAllCaches = () =>
  client.post<CleanResult>(`${BASE}/storage/clean`);

export const pruneDeadBrowsers = () =>
  client.post<PruneDeadResult>(`${BASE}/storage/prune-dead`);

export const forceClearAllBrowsers = () =>
  client.post<ForceClearResult>(`${BASE}/storage/force-clear`);
