#!/usr/bin/env bash
# DAI 实验平台 —— 本地开发一键关闭
#
# 用法:  ./scripts/dev-down.sh      （从项目根目录运行）
# 功能:  停止前端/后端 API/判题 Worker/环境构建 Worker，并停止 MySQL 与 Redis 容器
#        （容器数据保存在 docker volume 中，下次启动不丢失）
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${DAI_DEV_RUN_DIR:-/tmp/dai-dev}"

log()  { printf '\033[36m[dev-down]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[dev-down]\033[0m %s\n' "$*" >&2; exit 1; }

if docker info >/dev/null 2>&1; then
    DOCKER="docker"
else
    DOCKER="sudo docker"
fi

# ── 1. 停止应用进程 ──────────────────────────────────────────
# 递归终止整棵进程树（npm run dev 会经 sh 拉起 vite，只杀父进程会孤儿化子进程）
killtree() {
    local p="$1"
    local c
    for c in $(pgrep -P "$p" 2>/dev/null); do
        killtree "$c"
    done
    kill "$p" 2>/dev/null || true
}

stopped=0
for name in frontend api judge envbuilder; do
    pidfile="$RUN_DIR/$name.pid"
    [ -f "$pidfile" ] || { log "[跳过] $name 未在运行"; continue; }
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
        # 先递归终止子进程树，再停主进程（顺序保证 npm→sh→vite 全停）
        killtree "$pid"
        # 最多等待 10 秒优雅退出，之后强制结束
        for _ in $(seq 1 50); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.2
        done
        kill -0 "$pid" 2>/dev/null && { kill -9 "$pid" 2>/dev/null || true; log "[停止] $name (PID $pid，已强制结束)"; } \
                                     || log "[停止] $name (PID $pid)"
        stopped=1
    else
        log "[清理] $name 的 PID 文件已失效"
    fi
    rm -f "$pidfile"
done
[ "$stopped" = 1 ] && log "应用进程已全部停止"

# ── 2. 停止 MySQL 与 Redis 容器 ──────────────────────────────
cd "$PROJECT_DIR"
log "停止 MySQL 与 Redis 容器（数据卷保留）..."
$DOCKER compose stop mysql redis
log "容器已停止。如需彻底移除容器: docker compose down （数据卷会随之删除，注意备份）"

printf '\n\033[32m✔ 全部已关闭\033[0m\n  再次启动: ./scripts/dev-up.sh\n'
