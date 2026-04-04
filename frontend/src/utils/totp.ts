import { TOTP } from 'otpauth';

export function generateTOTP(secret: string): { code: string; remaining: number; formatted: string } {
  const totp = new TOTP({ issuer: 'Google', label: 'Account', algorithm: 'SHA1', digits: 6, period: 30, secret });
  const code = totp.generate();
  const remaining = totp.period - (Math.floor(Date.now() / 1000) % totp.period);
  const formatted = code.slice(0, 3) + ' ' + code.slice(3);
  return { code, remaining, formatted };
}
