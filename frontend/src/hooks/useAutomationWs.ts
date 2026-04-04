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
  /** 发送自动化命令 */
  execute: (accountId: number, action: string, extra?: Record<string, string>, opKey?: string) => void;
}

interface UseAutomationWsOptions {
  /** 操作成功时的回调 (opKey, message) */
  onSuccess?: (opKey: string, message: string) => void;
  /** 操作失败时的回调 (opKey, message) */
  onFail?: (opKey: string, message: string) => void;
  /** 连接错误时的回调 (opKey, message) */
  onError?: (opKey: string, message: string) => void;
}

/**
 * 封装自动化 WebSocket 逻辑的 hook。
 *
 * 管理 WebSocket 连接生命周期、步骤消息解析、运行状态跟踪。
 * 组件卸载时自动关闭连接。
 */
export function useAutomationWs(options: UseAutomationWsOptions = {}): AutomationWsResult {
  const { onSuccess, onFail, onError } = options;

  const [runningOp, setRunningOp] = useState<string | null>(null);
  const [steps, setSteps] = useState<StepMsg[]>([]);
  const [resultMsg, setResultMsg] = useState('');
  const [resultSuccess, setResultSuccess] = useState<boolean | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  // 用 ref 跟踪当前 opKey，确保回调时能拿到正确的值
  const trackKeyRef = useRef<string>('');

  // 组件卸载时关闭 WebSocket
  useEffect(() => {
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  const execute = useCallback(
    (accountId: number, action: string, extra: Record<string, string> = {}, opKey?: string) => {
      // 关闭之前的连接
      wsRef.current?.close();

      const trackKey = opKey || action;
      trackKeyRef.current = trackKey;
      const token = localStorage.getItem('token') || '';
      const ws = new WebSocket(`${WS_URL}?token=${token}`);
      wsRef.current = ws;

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

          if (data.type === 'step') {
            setSteps((prev) => {
              if (data.status === 'running') {
                return [...prev, data];
              }
              // 更新最后一个同 step 号的条目
              const updated = [...prev];
              let idx = -1;
              for (let j = updated.length - 1; j >= 0; j--) {
                if (updated[j].step === data.step) { idx = j; break; }
              }
              if (idx >= 0) updated[idx] = data;
              else updated.push(data);
              return updated;
            });
          } else if (data.type === 'result') {
            const isOk = data.success ?? false;
            const key = trackKeyRef.current;
            setRunningOp(null);
            setResultMsg(data.message || '');
            setResultSuccess(isOk);
            if (isOk) {
              onSuccess?.(key, data.message || '操作成功');
            } else {
              onFail?.(key, data.message || '操作失败');
            }
            ws.close();
          } else if (data.type === 'error') {
            const key = trackKeyRef.current;
            setRunningOp(null);
            setResultMsg(data.message || '操作异常');
            setResultSuccess(false);
            onError?.(key, data.message || '操作异常');
            ws.close();
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        const key = trackKeyRef.current;
        setRunningOp(null);
        setResultMsg('WebSocket 连接失败');
        setResultSuccess(false);
        onError?.(key, 'WebSocket 连接失败');
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    },
    [onSuccess, onFail, onError],
  );

  return { runningOp, steps, resultMsg, resultSuccess, execute };
}
