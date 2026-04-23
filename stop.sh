#!/usr/bin/env bash
# AccOps 停止脚本
# 用法: ./stop.sh

echo "==> 停止后端 / 前端"
pkill -9 -f "uvicorn app:app" 2>/dev/null && echo "   后端已停" || echo "   后端未在运行"
pkill -9 -f "run.py"          2>/dev/null
pkill -9 -f "node.*vite"      2>/dev/null && echo "   前端已停" || echo "   前端未在运行"
echo "✅ 停止完成"
