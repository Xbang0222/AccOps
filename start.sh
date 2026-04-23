#!/usr/bin/env bash
# AccOps 一键启动脚本
# 用法: ./start.sh
#
# 行为:
#   1. 杀掉遗留的 uvicorn / vite 进程
#   2. 后台启动后端 (http://127.0.0.1:8000)
#   3. 后台启动前端 (http://127.0.0.1:5173)
#   4. 健康检查 + 打印日志路径
#
# 日志: /tmp/accops-backend.log / /tmp/accops-frontend.log
# 停止: ./stop.sh

set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_LOG=/tmp/accops-backend.log
FRONTEND_LOG=/tmp/accops-frontend.log

# 非交互 bash 下 .zshrc 的 PATH 不会加载，兜底补上 uv / pnpm 所在路径
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$HOME/.npm-global/bin:/usr/local/bin:$PATH"

echo "==> 杀掉遗留进程"
pkill -9 -f "uvicorn app:app" 2>/dev/null || true
pkill -9 -f "run.py"          2>/dev/null || true
pkill -9 -f "node.*vite"      2>/dev/null || true
sleep 1

echo "==> 启动后端 (日志: $BACKEND_LOG)"
cd "$ROOT/backend"
nohup uv run uvicorn app:app \
  --host 127.0.0.1 --port 8000 \
  --reload --reload-exclude ".browser_profiles" \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "==> 启动前端 (日志: $FRONTEND_LOG)"
cd "$ROOT/frontend"
nohup pnpm dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo "==> 等待服务就绪..."
sleep 4

BACKEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs || echo "000")
FRONTEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173 || echo "000")

echo
echo "后端  pid=$BACKEND_PID  http://127.0.0.1:8000  [$BACKEND_CODE]"
echo "前端  pid=$FRONTEND_PID  http://127.0.0.1:5173  [$FRONTEND_CODE]"

if [[ "$BACKEND_CODE" != "200" || "$FRONTEND_CODE" != "200" ]]; then
  echo
  echo "⚠️  有服务未就绪，查看日志排查:"
  echo "    tail -f $BACKEND_LOG"
  echo "    tail -f $FRONTEND_LOG"
  exit 1
fi

echo
echo "✅ 启动完成"
