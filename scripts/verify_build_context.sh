#!/usr/bin/env bash
# DAI 实验平台 —— Docker 构建上下文防泄露验证
#
# 用法:  ./scripts/verify_build_context.sh
# 功能:
#   1. 构建 backend / frontend 镜像（标签 dai-verify:*，仅用于验证，可安全删除）
#   2. 断言镜像内不存在本地环境文件、业务存储、宿主依赖与测试凭据
#   3. Secret 扫描：本地 .env 中非空敏感值不得出现在镜像文件系统中
#   4. 启动烟测：backend 应用可实例化，frontend nginx 可返回首页
#
# 对应整改: TASK-001（F-08/F-09）。CI 与本地均可运行。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

BACKEND_IMG="dai-verify:backend"
FRONTEND_IMG="dai-verify:frontend"
BACKEND_PORT="${VERIFY_BACKEND_PORT:-18000}"
FRONTEND_PORT="${VERIFY_FRONTEND_PORT:-18080}"

log()  { printf '\033[36m[verify-build]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[verify-build]\033[0m %s\n' "$*" >&2; exit 1; }

[ -f backend/Dockerfile ] || fail "未找到 backend/Dockerfile"
[ -f frontend/Dockerfile ] || fail "未找到 frontend/Dockerfile"
command -v docker >/dev/null 2>&1 || fail "未找到 docker"
docker info >/dev/null 2>&1 || fail "docker 守护进程不可用"

# ── 1. 构建镜像 ──────────────────────────────────────────────
log "构建 backend 镜像 ..."
docker build -t "$BACKEND_IMG" backend/

log "构建 frontend 镜像 ..."
docker build -t "$FRONTEND_IMG" frontend/

# ── 2. 后端镜像敏感路径断言 ──────────────────────────────────
log "后端镜像：断言敏感路径不存在 ..."
docker run --rm --entrypoint sh "$BACKEND_IMG" -c '
set -eu
for p in /app/.env /app/.env.local /app/.env.production /app/storage /app/lesson_content /app/.venv; do
    if [ -e "$p" ]; then echo "LEAK: $p 存在于镜像"; exit 1; fi
done
# 示例配置允许保留，但其中不得包含真实凭据（由第 4 步 Secret 扫描兜底）
[ -f /app/.env.example ] || { echo "MISSING: .env.example 应保留在镜像"; exit 1; }
echo "backend 路径断言通过"
'

# ── 3. 前端镜像敏感路径断言 ──────────────────────────────────
log "前端镜像：断言敏感路径不存在 ..."
docker run --rm --entrypoint sh "$FRONTEND_IMG" -c '
set -eu
for p in /usr/share/nginx/html/node_modules /usr/share/nginx/html/.env \
         /usr/share/nginx/html/e2e /usr/share/nginx/html/test-results \
         /usr/share/nginx/html/playwright-report; do
    if [ -e "$p" ]; then echo "LEAK: $p 存在于镜像"; exit 1; fi
done
echo "frontend 路径断言通过"
'

# ── 4. Secret 扫描 ────────────────────────────────────────────
# 本地 .env 中非空、非占位的敏感值不得出现在镜像中。
log "Secret 扫描：本地 .env 敏感值 ..."
if [ -f backend/.env ]; then
    # 提取所有 KEY=VALUE 中的非空 VALUE（排除注释与空值），逐值扫描镜像
    secrets="$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=.+' backend/.env | cut -d= -f2- || true)"
    scanned=0
    while IFS= read -r value; do
        [ -n "$value" ] || continue
        # 跳过无敏感性的本地开发地址与镜像源
        case "$value" in
            http://localhost*|http://127.0.0.1*|redis://localhost*) continue ;;
        esac
        scanned=$((scanned + 1))
        if docker run --rm --entrypoint sh "$BACKEND_IMG" \
                -c "grep -RlF -- '$value' /app 2>/dev/null" | grep -q .; then
            fail "Secret 泄露: 本地 .env 值出现在后端镜像中（$value）"
        fi
        if docker run --rm --entrypoint sh "$FRONTEND_IMG" \
                -c "grep -RlF -- '$value' /usr/share/nginx/html 2>/dev/null" | grep -q .; then
            fail "Secret 泄露: 本地 .env 值出现在前端镜像中（$value）"
        fi
    done <<< "$secrets"
    log "Secret 扫描通过（检查 $scanned 个敏感值）"
else
    log "backend/.env 不存在，跳过值扫描（仅做路径断言）"
fi

# ── 5. 启动烟测 ───────────────────────────────────────────────
log "烟测：backend 应用可实例化 ..."
docker run --rm --entrypoint sh "$BACKEND_IMG" \
    -c 'python -c "from app.main import create_app; create_app(); print(\"backend app ok\")"'

log "烟测：frontend nginx 返回首页 ..."
cid="$(docker run -d -p "$FRONTEND_PORT":80 "$FRONTEND_IMG")"
trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then break; fi
    sleep 0.5
done
curl -fsS "http://127.0.0.1:$FRONTEND_PORT/" | grep -q '<div id="app">' \
    || fail "frontend 烟测失败：首页未正常返回"
docker rm -f "$cid" >/dev/null 2>&1
trap - EXIT

log "全部通过：构建成功、镜像与上下文不含本地敏感文件、Secret 扫描无结果、烟测通过"
