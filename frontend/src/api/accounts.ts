/** 账号相关 API */
import client, { API_PREFIX } from './client';
import type { Account, TOTPResponse } from '@/types';

export interface GetAccountsParams {
  search?: string;
  group?: string;
  page?: number;
  pageSize?: number;
  ownerOnly?: boolean;
  sortBy?: string;
  sortOrder?: string;
}

export const getAccounts = ({
  search,
  group,
  page = 1,
  pageSize = 20,
  ownerOnly = false,
  sortBy = 'created_at',
  sortOrder = 'desc',
}: GetAccountsParams = {}) => {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (group) params.append('group', group);
  params.append('page', String(page));
  params.append('page_size', String(pageSize));
  if (ownerOnly) params.append('owner_only', 'true');
  params.append('sort_by', sortBy);
  params.append('sort_order', sortOrder);
  return client.get<{ accounts: Account[]; total: number; page: number; page_size: number }>(`${API_PREFIX}/accounts?${params}`);
};

export const getAccount = (id: number) =>
  client.get<Account>(`${API_PREFIX}/accounts/${id}`);

export const createAccount = (data: Omit<Account, 'id'>) =>
  client.post<{ id: number; message: string }>(`${API_PREFIX}/accounts`, data);

export const updateAccount = (id: number, data: Omit<Account, 'id'>) =>
  client.put<{ message: string }>(`${API_PREFIX}/accounts/${id}`, data);

export const deleteAccount = (id: number) =>
  client.delete<{ message: string }>(`${API_PREFIX}/accounts/${id}`);

export const getGroups = () =>
  client.get<{ groups: string[] }>(`${API_PREFIX}/accounts/groups`);

export const getTOTP = (accountId: number) =>
  client.get<TOTPResponse>(`${API_PREFIX}/accounts/${accountId}/totp`);

export interface ImportResult {
  message: string;
  success: number;
  skipped: number;
  failed: number;
  details: { email?: string; line?: string; status: string; reason?: string; id?: number }[];
}

export const importAccounts = (text: string, group_name?: string, notes?: string) =>
  client.post<ImportResult>(`${API_PREFIX}/accounts/import`, { text, group_name, notes });

export const getAvailableAccounts = (search?: string) => {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  return client.get<{ accounts: { id: number; email: string }[] }>(`${API_PREFIX}/accounts/available?${params}`);
};
