#!/usr/bin/env bash
# DAI 实验平台 —— 本地开发一键关闭
#
# 用法:  ./scripts/dev-down.sh      （从项目根目录运行）
# 功能:
#   1. 按 pidfile 停止前端/后端 API/判题 Worker/环境构建 Worker（递归终止进程树）；
#   2. 清扫「未登记」的本项目残留进程（手动 nohup 启动、pidfile 丢失、脚本中途
#      崩溃留下的），按进程特征精确匹配，不会误伤其他项目；
#   3. 停止 MySQL 与 Redis 容器（数据保存在 docker volume 中，下次启动不丢失）。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${DAI_DEV_RUN_DIR:-/tmp/dai-dev}"
FRONTEND_PORT=5173

log()  { printf '\033[36m[dev-down]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[dev-down]\033[0m %s\n' "$*" >&2; exit 1; }

if docker info >/dev/null 2>&1; then
    DOCKER="docker"
else
    DOCKER="sudo docker"
fi

# 进程是否确实属于本项目（防 PID 复用：kill -0 只证明 PID 存活，不证明归属）
is_our_process() {
    local pid="$1" name="$2"
    kill -0 "$pid" 2>/dev/null || return 1
    case "$name" in
        # 前端记录的是 npm 包装进程（cmdline 不含项目路径），宽松匹配 npm/node
        frontend) ps -p "$pid" -o args= 2>/dev/null | grep -qE "npm|node" ;;
        *)        ps -p "$pid" -o args= 2>/dev/null | grep -qF "$PROJECT_DIR" ;;
    esac
}

# ── 1. 停止应用进程 ──────────────────────────────────────────
# 递归终止整棵进程树（npm run dev 会经 sh 拉起 vite，只杀父进程会孤儿化子进程）
killtree() {
    local p="$1" c
    for c in $(pgrep -P "$p" 2>/dev/null || true); do
        killtree "$c"
    done
    kill "$p" 2>/dev/null || true
}

stopped=0
for name in frontend api judge envbuilder; do
    pidfile="$RUN_DIR/$name.pid"
    [ -f "$pidfile" ] || { log "[跳过] $name 未在运行"; continue; }
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
        if is_our_process "$pid" "$name"; then
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
            log "[清理] $name 的 PID 已被其他进程复用，仅移除 pidfile（不终止该进程）"
        fi
    else
        log "[清理] $name 的 PID 文件已失效"
    fi
    rm -f "$pidfile"
done
[ "$stopped" = 1 ] && log "应用进程已全部停止"

# ── 2. 清扫未登记的本项目残留进程 ────────────────────────────
# 特征精确到本项目路径；正则用 [x] 技巧排除「正在执行本脚本的进程」自身，
# 也不会误伤其他项目（K12 等进程来自各自独立的 venv/路径）。
swept=0
sweep() {
    local pattern="$1" p
    for p in $(pgrep -f "$pattern" 2>/dev/null || true); do
        [ "$p" = "$$" ] && continue
        kill "$p" 2>/dev/null || true
        swept=1
    done
}
# 后端：本项目 venv 的 python（api/judge/envbuilder 都以该绝对路径出现在 cmdline）
sweep "${PROJECT_DIR}/backend/\.venv/bin/[p]ython"
# 前端：本项目 node_modules 下的 vite（npm 包装进程会随 vite 退出而退出）
sweep "${PROJECT_DIR}/frontend/node_modules/\.bin/[v]ite"
if [ "$swept" = 1 ]; then
    sleep 2
    log "[清扫] 已停止未登记的本项目残留进程"
fi

# ── 3. 端口复查 ──────────────────────────────────────────────
if (exec 3<>"/dev/tcp/127.0.0.1/$FRONTEND_PORT") 2>/dev/null; then
    exec 3>&-
    log "[警告] 端口 $FRONTEND_PORT 仍被占用，请手动排查: ss -tlnp | grep $FRONTEND_PORT"
fi

# ── 4. 停止 MySQL 与 Redis 容器 ──────────────────────────────
cd "$PROJECT_DIR"
log "停止 MySQL 与 Redis 容器（数据卷保留）..."
$DOCKER compose stop mysql redis
log "容器已停止。如需彻底移除容器: docker compose down （数据卷会随之删除，注意备份）"

printf '\n\033[32m✔ 全部已关闭\033[0m\n  再次启动: ./scripts/dev-up.sh\n'
