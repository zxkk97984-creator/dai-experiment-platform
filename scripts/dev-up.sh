#!/usr/bin/env bash
# DAI 实验平台 —— 本地开发一键启动
#
# 用法:  ./scripts/dev-up.sh        （从项目根目录运行）
# 功能:  启动 MySQL/Redis → 执行幂等迁移 → 检查判题镜像 →
#        启动后端 API/判题 Worker/环境构建 Worker/前端
# 幂等:  已在运行（pidfile 存活且属于本项目）的服务自动跳过；
#        端口被「外部」程序占用时立即失败并给出指引。
#
# 可用环境变量:
#   DAI_PYTHON       后端 Python 解释器（默认 backend/.venv/bin/python，Python 3.12）
#   DAI_DEV_API_PORT API 监听端口（默认 8000；本机 8000 被占用时用 8001）
#   DAI_DEV_RUN_DIR  运行目录（PID/日志，默认 /tmp/dai-dev）
#   DAI_DEV_NO_BROWSER=1  启动成功后不自动打开浏览器
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${DAI_DEV_RUN_DIR:-/tmp/dai-dev}"
PY="${DAI_PYTHON:-$PROJECT_DIR/backend/.venv/bin/python}"
API_PORT="${DAI_DEV_API_PORT:-8000}"
FRONTEND_PORT=5173
mkdir -p "$RUN_DIR"

log()  { printf '\033[36m[dev-up]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[dev-up]\033[0m %s\n' "$*" >&2; exit 1; }

# 端口是否已被监听（本机回环 TCP 探测）
port_busy() {
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

# 进程是否确实属于本项目（防 PID 复用误判：kill -0 只看 PID 是否存活）
is_our_process() {
    local pid="$1" name="$2"
    kill -0 "$pid" 2>/dev/null || return 1
    case "$name" in
        # 前端记录的是 npm 包装进程（cmdline 不含项目路径），宽松匹配 npm/node
        frontend) ps -p "$pid" -o args= 2>/dev/null | grep -qE "npm|node" ;;
        *)        ps -p "$pid" -o args= 2>/dev/null | grep -qF "$PROJECT_DIR" ;;
    esac
}

# pidfile 是否有效（存在 + 进程活着 + 属于本项目）
pid_alive() {
    local name="$1"
    local pidfile="$RUN_DIR/$name.pid" pid
    [ -f "$pidfile" ] || return 1
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    [ -n "${pid:-}" ] || return 1
    is_our_process "$pid" "$name"
}

# 启动后台进程（需要 docker 组权限的进程在无权限会话中经 sudo -u 启动）
launch() {
    local name="$1"; shift
    local pidfile="$RUN_DIR/$name.pid" logfile="$RUN_DIR/$name.log"
    if pid_alive "$name"; then
        log "[跳过] $name 已在运行 (PID $(cat "$pidfile"))"
        return
    fi
    rm -f "$pidfile"  # 失效/被复用的旧 pidfile
    # 直接后台启动。不要用命令替换或嵌套 bash -c 包一层：
    # 内层 bash 退出前等待后台子进程会挂起外层脚本（已实测踩坑）
    if [ "$DOCKER_GROUP_OK" = 1 ]; then
        nohup "$@" >"$logfile" 2>&1 &
    else
        # 无 docker 组权限的会话：经 sudo -u 启动（需 sudoers NOPASSWD 规则；
        # 记录的是 sudo 的 PID，停止时 sudo 会向子进程转发信号）
        sudo -u "$USER" nohup "$@" >"$logfile" 2>&1 &
    fi
    echo $! >"$pidfile"
    log "[启动] $name (PID $(cat "$pidfile"))"
}

# ── 1. 环境检查 ──────────────────────────────────────────────
[ -x "$PY" ] || fail "未找到后端 Python: $PY（可用 DAI_PYTHON=/path/to/python 覆盖；建议: uv venv backend/.venv --python 3.12 && uv pip install -r backend/requirements.txt）"
"$PY" -c 'import fastapi, sqlalchemy' 2>/dev/null \
    || fail "后端 .venv 缺少依赖，请先: cd backend && uv pip install -r requirements.txt"
[ -f "$PROJECT_DIR/backend/.env" ] || fail "缺少 backend/.env（首次使用请: cd backend && cp .env.example .env，默认值适配本地 docker compose）"
command -v npm >/dev/null 2>&1 || fail "未找到 npm"

# Docker 访问方式：当前会话可用 → 直接调用；否则走 sudo（需 sudoers NOPASSWD 或输密码）
if docker info >/dev/null 2>&1; then
    DOCKER="docker"
    DOCKER_GROUP_OK=1
else
    DOCKER="sudo docker"
    DOCKER_GROUP_OK=0
    log "当前会话无 docker 组权限，docker 与后端进程将经 sudo 启动（已配置 NOPASSWD 则无密码提示）"
fi

# ── 2. 基础服务（MySQL + Redis）──────────────────────────────
log "启动 MySQL 与 Redis..."
cd "$PROJECT_DIR"
$DOCKER compose up -d --wait --no-recreate mysql redis
log "MySQL/Redis 健康检查通过"

# ── 2.5 幂等迁移（TASK-016 后 API 不再自动跑 Alembic）────────
log "执行数据库迁移（alembic upgrade head，幂等）..."
cd "$PROJECT_DIR/backend"
"$PY" -m alembic upgrade head | tail -1

# ── 3. 判题镜像（不存在时构建）───────────────────────────────
cd "$PROJECT_DIR"
for img in dai-judge-python:latest dai-kernel-python:latest; do
    if ! $DOCKER images -q "$img" | grep -q .; then
        log "构建镜像 $img ..."
        case "$img" in
            dai-judge*)  $DOCKER build -q -t "$img" backend/docker/judge ;;
            dai-kernel*) $DOCKER build -q -t "$img" backend/docker/kernel ;;
        esac
    fi
done

# ── 4. 后端与 Worker ─────────────────────────────────────────
cd "$PROJECT_DIR/backend"
if pid_alive api; then
    log "[跳过] api 已在运行 (PID $(cat "$RUN_DIR/api.pid"))"
elif port_busy "$API_PORT"; then
    fail "端口 $API_PORT 已被「其他程序」占用（本项目自己的 api 在运行时会自动跳过）。换端口重跑: DAI_DEV_API_PORT=8001 ./scripts/dev-up.sh"
else
    launch api "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT"
fi
launch judge      "$PY" -m app.worker.judge_worker
launch envbuilder "$PY" -m app.worker.environment_builder_worker

# ── 5. 前端 ──────────────────────────────────────────────────
cd "$PROJECT_DIR/frontend"
[ -d node_modules ] || { log "安装前端依赖..."; npm install --silent; }
if pid_alive frontend; then
    log "[跳过] frontend 已在运行 (PID $(cat "$RUN_DIR/frontend.pid"))"
elif port_busy "$FRONTEND_PORT"; then
    fail "端口 $FRONTEND_PORT 已被「未登记进程」占用（常见：手动启动或崩溃残留的前端）。请先运行 ./scripts/dev-down.sh 清扫残留，再重新启动"
else
    # vite 代理目标跟随 API 端口（默认 8000），避免 API 换端口后前端仍请求旧端口
    launch frontend env VITE_API_PROXY_TARGET="http://localhost:${API_PORT}" npm run dev
fi

# ── 6. 健康检查 ──────────────────────────────────────────────
log "等待后端就绪..."
for _ in $(seq 1 30); do
    if curl -sf --max-time 3 "http://localhost:${API_PORT}/api/v1/health/ready" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
curl -sf --max-time 5 "http://localhost:${API_PORT}/api/v1/health/ready" \
    && { printf '\n'; log "后端健康: $(curl -s --max-time 5 "http://localhost:${API_PORT}/api/v1/health/ready")"; } \
    || fail "后端未就绪，请查看日志: $RUN_DIR/api.log（端口 $API_PORT 被占用可换 DAI_DEV_API_PORT=8001 重启）"

printf '\n\033[32m✔ 全部启动完成\033[0m\n'
printf '  前端页面:   http://localhost:%s\n' "$FRONTEND_PORT"
printf '  Swagger:    http://localhost:%s/docs\n' "$API_PORT"
printf '  健康检查:   http://localhost:%s/api/v1/health/ready\n' "$API_PORT"
printf '  运行目录:   %s （PID 与日志）\n' "$RUN_DIR"
printf '  登录账号:   库内种子账号密码因种子而异——admin 常为 Passw0rd! 或 Test1234!；\n'
printf '              teacher_john / student_alice 等内测账号为 Test1234!；\n'
printf '              全新库请先按 README §3 创建管理员（app.cli create-admin）。\n\n'
printf '  关闭:       ./scripts/dev-down.sh\n'

# ── 7. 自动打开浏览器（可用 DAI_DEV_NO_BROWSER=1 关闭）────────
if [ "${DAI_DEV_NO_BROWSER:-0}" != "1" ]; then
    if command -v xdg-open >/dev/null 2>&1; then
        nohup xdg-open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 || true
        log "已尝试用默认浏览器打开 http://localhost:${FRONTEND_PORT}"
    elif command -v open >/dev/null 2>&1; then
        nohup open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 || true
        log "已尝试用默认浏览器打开 http://localhost:${FRONTEND_PORT}"
    else
        log "未找到 xdg-open/open，请手动打开 http://localhost:${FRONTEND_PORT}"
    fi
fi
