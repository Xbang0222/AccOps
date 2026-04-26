/** 数据类型定义 */

import type { AccountStatus } from '@/constants/accountStatus'

export interface Tag {
  id: number;
  name: string;
  sort_order?: number;
  accounts_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface Account {
  id: number;
  email: string;
  password: string;
  recovery_email?: string;
  totp_secret?: string;
  family_group_id?: number;
  is_family_owner?: boolean;
  is_family_pending?: boolean;
  family_member_count?: number;
  subscription_status?: string;
  subscription_expiry?: string;
  has_oauth_credential?: boolean;
  validation_url?: string;
  notes?: string;
  retired_at?: string;
  status?: AccountStatus;
  tags?: Tag[];
  created_at?: string;
  updated_at?: string;
}

/** 账号创建/更新请求体 (与响应 Account 区分开) */
export interface AccountInput {
  email: string;
  password?: string;
  recovery_email?: string;
  totp_secret?: string;
  group_id?: number | null;
  notes?: string;
  tag_ids?: number[];
}

export interface Group {
  id: number;
  name: string;
  main_account_id?: number;
  main_account_email?: string;
  notes?: string;
  accounts?: Account[];
  created_at?: string;
  updated_at?: string;
}

export interface TOTPResponse {
  code: string;
  remaining: number;
  formatted: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
