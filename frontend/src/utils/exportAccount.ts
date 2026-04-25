import type { Account } from '@/types';

const SEPARATOR = '----';

export function formatAccountLine(account: Account): string {
  return [
    account.email ?? '',
    account.password ?? '',
    account.totp_secret ?? '',
  ].join(SEPARATOR);
}

export function buildAccountsText(accounts: ReadonlyArray<Account>): string {
  return accounts.map(formatAccountLine).join('\n');
}

function buildTimestamp(): string {
  const d = new Date();
  const pad = (n: number) => n.toString().padStart(2, '0');
  return (
    d.getFullYear().toString() +
    pad(d.getMonth() + 1) +
    pad(d.getDate()) +
    '-' +
    pad(d.getHours()) +
    pad(d.getMinutes()) +
    pad(d.getSeconds())
  );
}

const MAX_EMAIL_IN_FILENAME = 60;

function sanitizeFilenamePart(value: string): string {
  return value.replace(/[\\/:*?"<>|]/g, '_').slice(0, MAX_EMAIL_IN_FILENAME);
}

export function downloadAccountsTxt(accounts: ReadonlyArray<Account>): void {
  if (accounts.length === 0) {
    return;
  }
  const text = buildAccountsText(accounts);
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const ts = buildTimestamp();
  const filename =
    accounts.length === 1
      ? `account-${sanitizeFilenamePart(accounts[0].email)}-${ts}.txt`
      : `accounts-${accounts.length}-${ts}.txt`;
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Safari < 15 在同步帧 revoke 偶发取消下载，给浏览器一点时间派发下载事件
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
