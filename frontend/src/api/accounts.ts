/** 账号相关 API */
import client, { API_PREFIX } from './client';
import type { Account, AccountInput, TOTPResponse } from '@/types';

export interface GetAccountsParams {
  search?: string;
  page?: number;
  pageSize?: number;
  ownerOnly?: boolean;
  sortBy?: string;
  sortOrder?: string;
  tagIds?: number[];
}

export const getAccounts = ({
  search,
  page = 1,
  pageSize = 20,
  ownerOnly = false,
  sortBy = 'created_at',
  sortOrder = 'desc',
  tagIds,
}: GetAccountsParams = {}) => {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  params.append('page', String(page));
  params.append('page_size', String(pageSize));
  if (ownerOnly) params.append('owner_only', 'true');
  params.append('sort_by', sortBy);
  params.append('sort_order', sortOrder);
  if (tagIds && tagIds.length > 0) {
    params.append('tag_ids', tagIds.join(','));
  }
  return client.get<{ accounts: Account[]; total: number; page: number; page_size: number }>(`${API_PREFIX}/accounts?${params}`);
};

export const getAccount = (id: number) =>
  client.get<Account>(`${API_PREFIX}/accounts/${id}`);

export const createAccount = (data: AccountInput) =>
  client.post<{ id: number; message: string }>(`${API_PREFIX}/accounts`, data);

export const updateAccount = (id: number, data: AccountInput) =>
  client.put<{ message: string }>(`${API_PREFIX}/accounts/${id}`, data);

export const deleteAccount = (id: number) =>
  client.delete<{ message: string }>(`${API_PREFIX}/accounts/${id}`);

export const getTOTP = (accountId: number) =>
  client.get<TOTPResponse>(`${API_PREFIX}/accounts/${accountId}/totp`);

export interface ImportResult {
  message: string;
  success: number;
  skipped: number;
  failed: number;
  details: { email?: string; line?: string; status: string; reason?: string; id?: number }[];
}

export const importAccounts = (text: string, notes?: string) =>
  client.post<ImportResult>(`${API_PREFIX}/accounts/import`, { text, notes });

export const getAvailableAccounts = (search?: string) => {
  const params = new URLSearchParams();
  if (search) params.append('search', search);
  return client.get<{ accounts: { id: number; email: string }[] }>(`${API_PREFIX}/accounts/available?${params}`);
};

export const markAccountUnusable = (id: number) =>
  client.post<{ message: string }>(`${API_PREFIX}/accounts/${id}/mark-unusable`);

export const clearAccountStatus = (id: number) =>
  client.post<{ message: string }>(`${API_PREFIX}/accounts/${id}/clear-status`);

export const batchUpdateTags = (
  accountIds: number[],
  tagIds: number[],
  mode: 'add' | 'replace' | 'remove' = 'add',
  replaceFromId?: number,
) =>
  client.post<{ message: string; count: number }>(`${API_PREFIX}/accounts/batch-tags`, {
    account_ids: accountIds,
    tag_ids: tagIds,
    mode,
    replace_from_id: replaceFromId,
  });
