#!/usr/bin/env bash
# 验证单机 Redis AOF + 命名卷：restart 与 recreate 后 key 均保留。
# 用法：scripts/verify-redis-persistence.sh [TAG]
set -euo pipefail

TAG="${1:-verify}"
NAME="dai-redis-verify-${TAG}"
VOL="${NAME}-data"

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker volume rm -f "$VOL" >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

echo "==> 启动 AOF Redis（everysec）"
docker run -d --name "$NAME" \
  -v "$VOL:/data" \
  redis:7-alpine redis-server --appendonly yes --appendfsync everysec >/dev/null
sleep 2

echo "==> 写入 key"
docker exec "$NAME" redis-cli set verify:token "survives" >/dev/null
docker exec "$NAME" redis-cli rpush verify:queue "job-1" >/dev/null

echo "==> restart 后验证"
docker restart "$NAME" >/dev/null
sleep 2
test "$(docker exec "$NAME" redis-cli get verify:token)" = "survives"
test "$(docker exec "$NAME" redis-cli llen verify:queue)" = "1"

echo "==> recreate（rm + 同卷重跑）后验证"
docker rm -f "$NAME" >/dev/null
docker run -d --name "$NAME" \
  -v "$VOL:/data" \
  redis:7-alpine redis-server --appendonly yes --appendfsync everysec >/dev/null
sleep 2
test "$(docker exec "$NAME" redis-cli get verify:token)" = "survives"
test "$(docker exec "$NAME" redis-cli llen verify:queue)" = "1"

echo "OK: AOF 与命名卷在 restart/recreate 后均保留数据"
