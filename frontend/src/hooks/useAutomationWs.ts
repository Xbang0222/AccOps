import { useState, useRef, useCallback, useEffect } from 'react';
import { config } from '@/config';

const WS_URL = `${config.wsBaseUrl}/api/v1/ws/automation`;

/** WebSocket 步骤消息 */
export interface StepMsg {
  type: 'step' | 'result' | 'error';
  step?: number;
  name?: string;
  status?: string;
  message?: string;
  success?: boolean;
  duration_ms?: number;
  timestamp?: string;
}

export interface AutomationWsResult {
  /** 当前正在执行的操作 key (null = 空闲) */
  runningOp: string | null;
  /** 实时步骤日志 */
  steps: StepMsg[];
  /** 最终结果消息 */
  resultMsg: string;
  /** 最终结果是否成功 */
  resultSuccess: boolean | null;
  /** 发送自动化命令（支持多连接并行） */
  execute: (accountId: number, action: string, extra?: Record<string, string>, opKey?: string) => void;
  /** 取消指定账号的操作，不传则取消最后一个 */
  cancel: (accountId?: number) => void;
}

interface UseAutomationWsOptions {
  /** 操作成功时的回调 (opKey, message, accountId) */
  onSuccess?: (opKey: string, message: string, accountId?: number) => void;
  /** 操作失败时的回调 (opKey, message, accountId) */
  onFail?: (opKey: string, message: string, accountId?: number) => void;
  /** 连接错误时的回调 (opKey, message, accountId) */
  onError?: (opKey: string, message: string, accountId?: number) => void;
  /** 每个步骤消息的回调 (accountId, step) — 所有并发操作都会触发 */
  onStep?: (accountId: number, step: StepMsg) => void;
}

interface WsConnection {
  ws: WebSocket;
  opKey: string;
  accountId: number;
}

/**
 * 封装自动化 WebSocket 逻辑的 hook。
 *
 * 支持多个 WebSocket 连接并行运行，每个 accountId 独立管理。
 * 组件卸载时自动关闭所有连接。
 */
export function useAutomationWs(options: UseAutomationWsOptions = {}): AutomationWsResult {
  const { onSuccess, onFail, onError, onStep } = options;

  // 最后一个操作的状态（用于 UI 展示当前选中账号的日志）
  const [runningOp, setRunningOp] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepMsg[]>([]);
  const [resultMsg, setResultMsg] = useState('');
  const [resultSuccess, setResultSuccess] = useState<boolean | null>(null);

  // 连接池：accountId → WsConnection
  const connectionsRef = useRef<Map<number, WsConnection>>(new Map());
  // 跟踪最后一个活跃的 accountId
  const lastAccountIdRef = useRef<number | null>(null);

  // 组件卸载时关闭所有 WebSocket
  useEffect(() => {
    return () => {
      for (const conn of connectionsRef.current.values()) {
        conn.ws.close();
      }
      connectionsRef.current.clear();
    };
  }, []);

  const execute = useCallback(
    (accountId: number, action: string, extra: Record<string, string> = {}, opKey?: string) => {
      // 关闭该账号之前的连接（同一账号不能同时两个操作）
      const existing = connectionsRef.current.get(accountId);
      if (existing) {
        existing.ws.close();
        connectionsRef.current.delete(accountId);
      }

      const trackKey = opKey || action;
      lastAccountIdRef.current = accountId;
      const token = localStorage.getItem('token') || '';
      const ws = new WebSocket(`${WS_URL}?token=${token}`);

      const conn: WsConnection = { ws, opKey: trackKey, accountId };
      connectionsRef.current.set(accountId, conn);

      // 只有最后启动的操作更新全局 UI 状态
      setRunningOp(trackKey);
      setSteps([]);
      setResultMsg('');
      setResultSuccess(null);

      ws.onopen = () => {
        ws.send(JSON.stringify({ action, account_id: accountId, ...extra }));
      };

      ws.onmessage = (e) => {
        try {
          const data: StepMsg = JSON.parse(e.data);
          const isActive = lastAccountIdRef.current === accountId;

          if (data.type === 'step') {
            // 对所有并发操作都触发 onStep 回调
            onStep?.(accountId, data);
            if (isActive) {
              setSteps((prev) => {
                if (data.status === 'running') {
                  return [...prev, data];
                }
                const updated = [...prev];
                let idx = -1;
                for (let j = updated.length - 1; j >= 0; j--) {
                  if (updated[j].step === data.step) { idx = j; break; }
                }
                if (idx >= 0) updated[idx] = data;
                else updated.push(data);
                return updated;
              });
            }
          } else if (data.type === 'result') {
            const isOk = data.success ?? false;
            if (isActive) {
              setRunningOp(null);
              setResultMsg(data.message || '');
              setResultSuccess(isOk);
            }
            if (isOk) {
              onSuccess?.(trackKey, data.message || '操作成功', accountId);
            } else {
              onFail?.(trackKey, data.message || '操作失败', accountId);
            }
            ws.close();
            connectionsRef.current.delete(accountId);
          } else if (data.type === 'error') {
            if (isActive) {
              setRunningOp(null);
              setResultMsg(data.message || '操作异常');
              setResultSuccess(false);
            }
            onError?.(trackKey, data.message || '操作异常', accountId);
            ws.close();
            connectionsRef.current.delete(accountId);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        const isActive = lastAccountIdRef.current === accountId;
        if (isActive) {
          setRunningOp(null);
          setResultMsg('WebSocket 连接失败');
          setResultSuccess(false);
        }
        onError?.(trackKey, 'WebSocket 连接失败', accountId);
        connectionsRef.current.delete(accountId);
      };

      ws.onclose = () => {
        connectionsRef.current.delete(accountId);
      };
    },
    [onSuccess, onFail, onError],
  );

  const cancel = useCallback((accountId?: number) => {
    if (accountId !== undefined) {
      const conn = connectionsRef.current.get(accountId);
      if (conn && conn.ws.readyState === WebSocket.OPEN) {
        conn.ws.send(JSON.stringify({ action: 'cancel' }));
      }
    } else {
      // 取消所有
      for (const conn of connectionsRef.current.values()) {
        if (conn.ws.readyState === WebSocket.OPEN) {
          conn.ws.send(JSON.stringify({ action: 'cancel' }));
        }
      }
    }
  }, []);

  return { runningOp, steps, resultMsg, resultSuccess, execute, cancel };
}
