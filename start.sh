#!/usr/bin/env bash
# AccOps 一键启动脚本
# 用法: ./start.sh
#
# 行为:
#   1. 杀掉遗留的 uvicorn / vite 进程
#   2. 后台启动后端 (http://127.0.0.1:$BACKEND_PORT)
#   3. 后台启动前端 (http://127.0.0.1:$FRONTEND_PORT)
#   4. 健康检查 + 打印日志路径 + disown 使进程脱离终端常驻
#
# 端口可通过环境变量覆盖: BACKEND_PORT / FRONTEND_PORT
# 日志: /tmp/accops-backend.log / /tmp/accops-frontend.log
# 停止: ./stop.sh

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_LOG=/tmp/accops-backend.log
FRONTEND_LOG=/tmp/accops-frontend.log
BACKEND_PORT="${BACKEND_PORT:-17893}"
FRONTEND_PORT="${FRONTEND_PORT:-17894}"

# 非交互 bash 下 .zshrc 的 PATH 不会加载，兜底补上 uv / pnpm 所在路径
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$HOME/.npm-global/bin:/usr/local/bin:$PATH"

# 让前端通过环境变量感知后端端口（vite.config.ts / config.ts 都会读）
export VITE_DEV_PROXY_TARGET="http://127.0.0.1:${BACKEND_PORT}"
# 让后端 CORS 放行前端端口
export GAM_CORS_ORIGINS="${GAM_CORS_ORIGINS:-http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}}"
export GAM_PORT="${GAM_PORT:-$BACKEND_PORT}"

echo "==> 杀掉遗留进程"
pkill -9 -f "uvicorn app:app" 2>/dev/null || true
pkill -9 -f "run.py"          2>/dev/null || true
pkill -9 -f "node.*vite"      2>/dev/null || true
sleep 1

echo "==> 启动后端 (端口: $BACKEND_PORT, 日志: $BACKEND_LOG)"
cd "$ROOT/backend"
nohup uv run uvicorn app:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" \
  --reload --reload-exclude ".browser_profiles" \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
disown "$BACKEND_PID" 2>/dev/null || true

echo "==> 启动前端 (端口: $FRONTEND_PORT, 日志: $FRONTEND_LOG)"
cd "$ROOT/frontend"
nohup pnpm dev --port "$FRONTEND_PORT" --strictPort > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
disown "$FRONTEND_PID" 2>/dev/null || true

echo "==> 等待服务就绪..."
sleep 4

BACKEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/docs" || echo "000")
FRONTEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${FRONTEND_PORT}" || echo "000")

echo
echo "后端  pid=$BACKEND_PID  http://127.0.0.1:${BACKEND_PORT}  [$BACKEND_CODE]"
echo "前端  pid=$FRONTEND_PID  http://127.0.0.1:${FRONTEND_PORT}  [$FRONTEND_CODE]"

if [[ "$BACKEND_CODE" != "200" || "$FRONTEND_CODE" != "200" ]]; then
  echo
  echo "⚠️  有服务未就绪，查看日志排查:"
  echo "    tail -f $BACKEND_LOG"
  echo "    tail -f $FRONTEND_LOG"
  exit 1
fi

echo
echo "✅ 启动完成"
