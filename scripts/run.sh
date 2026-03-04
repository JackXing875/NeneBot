#!/bin/bash
# NeneBot 全自动点火脚本

echo "正在启动 NeneBot 工业级双引擎..."

# ==========================================
# 0. 自动唤醒 Ollama (大模型引擎)
# ==========================================
echo "检查 Ollama 引擎状态..."
# 检查后台是否有 ollama 进程
if ! pgrep -x "ollama" > /dev/null
then
    echo "   发现 Ollama 处于沉睡状态，正在为您自动唤醒..."
    # 丢弃烦人的日志，在后台静默启动
    ollama serve > /dev/null 2>&1 &
    sleep 3  # 给引擎3秒钟的预热时间
    echo "   Ollama 唤醒成功！"
else
    echo "   Ollama 引擎已在正常运转。"
fi

# ==========================================
# 优雅降级与清理机制
# ==========================================
cleanup() {
    echo -e "\n接收到停止信号，正在关闭服务..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "界面与后端已安全退出 (Ollama 仍保留在后台为您待命)。"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ==========================================
# 1. 启动后端 (FastAPI)
# ==========================================
echo "启动后端大脑 (FastAPI -> 端口 8000)..."
python -m src.main &
BACKEND_PID=$!
sleep 2

# ==========================================
# 2. 启动前端 (Vue + Vite)
# ==========================================
echo "启动视觉界面 (Vue 3 -> 端口 5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo "------------------------------------------------------"
echo "NeneBot 启动成功！"
echo "请在浏览器打开 Galgame 界面: http://localhost:5173"
echo "按 [Ctrl+C] 即可一键安全关闭服务。"
echo "------------------------------------------------------"

wait