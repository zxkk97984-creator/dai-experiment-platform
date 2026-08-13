#!/usr/bin/env bash
# 验证前后端 Docker 构建上下文不含本地环境文件、业务存储或宿主依赖，且镜像可正常构建。
# 用法：scripts/verify-build-context.sh [TAG_SUFFIX]
#   成功：exit 0；失败：打印违规路径并 exit 1。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUFFIX="${1:-ctxcheck}"
VIOLATIONS="$(mktemp)"
trap 'rm -f "$VIOLATIONS"' EXIT

fail() {
  echo "VIOLATION: $*" >&2
  echo "1" >>"$VIOLATIONS"
}

probe_context() {
  # 用 busybox 探针镜像精确枚举进入构建上下文的文件列表
  local context="$1" tag="$2" tmpdf
  tmpdf="$(mktemp)"
  printf 'FROM busybox:latest\nCOPY . /probe\n' >"$tmpdf"
  docker build -q -f "$tmpdf" -t "$tag" "$context" >/dev/null
  local cname="${tag//:/-}-probe"
  docker create --name "$cname" "$tag" >/dev/null
  docker export "$cname" | tar -t | grep '^probe/' | sed 's#^probe/#/#' | sort || true
  docker rm "$cname" >/dev/null || true
  docker rmi -f "$tag" >/dev/null || true
  rm -f "$tmpdf"
}

echo "==> 枚举 backend 构建上下文"
backend_ctx=$(probe_context "$ROOT/backend" "dai-ctxprobe-backend:${SUFFIX}")
echo "$backend_ctx" | grep -E '^/\.env' | grep -vE '^/\.env\.example$' | while read -r p; do fail "backend 上下文: $p（凭据文件）"; done || true
echo "$backend_ctx" | grep -E '^/(storage|lesson_content)/' | while read -r p; do fail "backend 上下文: $p（本地业务数据）"; done || true
echo "$backend_ctx" | grep -E '^/\.pytest-temp-root/' | while read -r p; do fail "backend 上下文: $p（pytest 临时目录）"; done || true
echo "$backend_ctx" | grep -E '^/.+\.log$' | while read -r p; do fail "backend 上下文: $p（日志文件）"; done || true
if ! echo "$backend_ctx" | grep -qE '^/\.env\.example$'; then fail "backend 上下文: 缺少 .env.example（排除规则过宽）"; fi
if ! echo "$backend_ctx" | grep -qE '^/app/main\.py$'; then fail "backend 上下文: 缺少 app/main.py（排除规则过宽）"; fi

echo "==> 枚举 frontend 构建上下文"
frontend_ctx=$(probe_context "$ROOT/frontend" "dai-ctxprobe-frontend:${SUFFIX}")
echo "$frontend_ctx" | grep -E '^/\.env' | grep -vE '^/\.env\.example$' | while read -r p; do fail "frontend 上下文: $p（凭据文件）"; done || true
echo "$frontend_ctx" | grep -E '^/node_modules/' | while read -r p; do fail "frontend 上下文: $p（宿主 node_modules）"; done || true
echo "$frontend_ctx" | grep -E '^/dist/' | while read -r p; do fail "frontend 上下文: $p（宿主 dist）"; done || true
echo "$frontend_ctx" | grep -E '^/.+\.log$' | while read -r p; do fail "frontend 上下文: $p（日志文件）"; done || true
if ! echo "$frontend_ctx" | grep -qE '^/package\.json$'; then fail "frontend 上下文: 缺少 package.json（排除规则过宽）"; fi

echo "==> 构建真实镜像（验证 ignore 收紧后构建仍成功）"
# 本机存在仅监听 127.0.0.1 的代理时可设 VERIFY_BUILD_NETWORK=host 复用宿主网络
net_args=()
if [ -n "${VERIFY_BUILD_NETWORK:-}" ]; then
  net_args=(--network "${VERIFY_BUILD_NETWORK}")
fi
build_with_retry() {
  local attempts=3 i
  for i in $(seq 1 "$attempts"); do
    if docker build -q "${net_args[@]}" -t "$2" "$1" >/dev/null; then
      return 0
    fi
    echo "  构建第 $i 次失败，重试..." >&2
    sleep 5
  done
  fail "$1 镜像构建失败（见上方日志）"
}
build_with_retry "$ROOT/backend" "dai-ctxcheck-backend:${SUFFIX}"
build_with_retry "$ROOT/frontend" "dai-ctxcheck-frontend:${SUFFIX}"

echo "==> 扫描最终镜像"
backend_img=$(docker run --rm "dai-ctxcheck-backend:${SUFFIX}" sh -c "find /app -type f | sort")
echo "$backend_img" | grep -E '^/app/\.env' | grep -vE '^/app/\.env\.example$' | while read -r p; do fail "backend 镜像: $p"; done || true
echo "$backend_img" | grep -E '^/app/(storage|lesson_content)/' | while read -r p; do fail "backend 镜像: $p"; done || true
frontend_img=$(docker run --rm "dai-ctxcheck-frontend:${SUFFIX}" sh -c "find / -path /proc -prune -o -path /sys -prune -o -type f -print | sort")
echo "$frontend_img" | grep -E '^/app/node_modules/' | while read -r p; do fail "frontend 镜像: $p"; done || true
if ! echo "$frontend_img" | grep -qE '^/usr/share/nginx/html/index\.html$'; then fail "frontend 镜像: 缺少构建产物 index.html"; fi

echo "==> 清理"
docker rmi -f "dai-ctxcheck-backend:${SUFFIX}" "dai-ctxcheck-frontend:${SUFFIX}" >/dev/null

if [ -s "$VIOLATIONS" ]; then
  echo "FAILED: $(wc -l <"$VIOLATIONS") 处违规" >&2
  exit 1
fi
echo "OK: 上下文与镜像均未发现敏感路径泄漏，构建成功"
