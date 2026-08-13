#!/usr/bin/env bash
# TASK-030：安全响应头回归——对运行中的前端（nginx）逐路径断言。
#
# 用法：BASE_URL=http://localhost:8080 ./scripts/check_security_headers.sh
# 断言：
#   1) 每路径携带 nosniff / Referrer-Policy / X-Frame-Options / CSP-Report-Only
#   2) 纯 HTTP 内层绝不携带 HSTS（HSTS 只允许在真实 HTTPS 终止层）
# 退出码：任一断言失败 → 1（供 CI/cron 使用）。
set -u

BASE_URL="${BASE_URL:-http://localhost:8080}"
PATHS=(
  "/"                      # 主页面（SPA fallback）
  "/login"                 # SPA 路由（登录页）
  "/api/v1/health/live"    # API 代理路径
  "/api/v1/media/x"        # 媒体路径（上游 4xx/5xx 时头部仍需存在）
)

REQUIRED_HEADERS=(
  "X-Content-Type-Options"
  "Referrer-Policy"
  "X-Frame-Options"
  "Content-Security-Policy-Report-Only"
)

fail=0
for path in "${PATHS[@]}"; do
  headers=$(curl -sI --max-time 10 "${BASE_URL}${path}" | tr -d '\r')
  for header in "${REQUIRED_HEADERS[@]}"; do
    if ! echo "$headers" | grep -qi "^${header}:"; then
      echo "FAIL ${path}: 缺少 ${header}"
      fail=1
    fi
  done
  # HSTS 内层禁止：出现即失败（责任层越界）
  if echo "$headers" | grep -qi "^Strict-Transport-Security:"; then
    echo "FAIL ${path}: 内层 HTTP 携带 HSTS（仅 HTTPS 终止层可设置）"
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "OK: ${#PATHS[@]} 条路径安全头断言全部通过（${BASE_URL}）"
fi
exit "$fail"
