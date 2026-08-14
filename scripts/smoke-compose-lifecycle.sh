#!/usr/bin/env bash
# TASK-015 + TASK-016 烟测：真实 Compose 拉起 mysql/redis/migrate/api/frontend，验证
# 1) 空库部署序列（迁移 A → seed basic 环境 → migrate 服务 → api 才启动）；
# 2) Redis 故障 → api unhealthy；3) Redis 恢复 → api 重新 healthy；
# 4) 杀 api 进程 → restart 策略拉起。
# 用法：scripts/smoke-compose-lifecycle.sh [PROJECT]
set -euo pipefail

PROJECT="${1:-dai-t015-smoke}"
COMPOSE="docker compose -p $PROJECT -f docker-compose.prod.yml"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export DAI_SECRET_KEY="${DAI_SECRET_KEY:-smoke-test-secret-key-16chars}"
export DAI_CORS_ORIGINS="${DAI_CORS_ORIGINS:-https://smoke.example.edu.cn}"
export DAI_ENV_BASE_IMAGE="${DAI_ENV_BASE_IMAGE:-python:3.12-slim@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}"
export DAI_JUDGE_HOST_WORK_DIR="${DAI_JUDGE_HOST_WORK_DIR:-/tmp/dai-smoke-judgework}"
# 生产配置校验拒绝默认密码 dai_password，烟测使用一次性唯一密码
export DAI_DB_PASSWORD="${DAI_DB_PASSWORD:-smoke-db-password-9f3k}"
mkdir -p "$DAI_JUDGE_HOST_WORK_DIR"

NET="${PROJECT}_internal"
DB_URL="mysql+pymysql://dai:${DAI_DB_PASSWORD}@mysql:3306/dai_platform"

cleanup() {
  echo "==> 清理"
  $COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup

wait_health() {
  local service="$1" want="$2" attempts="${3:-60}"
  for _ in $(seq 1 "$attempts"); do
    status=$($COMPOSE ps --format '{{.Name}}|{{.Health}}' 2>/dev/null | grep -E "^${PROJECT}-${service}-" | head -1 | cut -d'|' -f2)
    [ "$status" = "$want" ] && return 0
    sleep 3
  done
  echo "FAILED: $service 未在时限内达到 $want（当前 $status）" >&2
  $COMPOSE logs --tail 40 "$service" >&2 || true
  return 1
}

echo "==> 预构建镜像（本机代理仅监听 127.0.0.1，构建用宿主网络）"
docker build -q --network host -t "${PROJECT}-api" "$ROOT/backend" >/dev/null
docker build -q --network host -t "${PROJECT}-frontend" "$ROOT/frontend" >/dev/null
# worker/environment-builder/migrate 仅需镜像名被 Compose 识别（smoke 不启动 worker/builder）
docker tag "${PROJECT}-api" "${PROJECT}-worker"
docker tag "${PROJECT}-api" "${PROJECT}-environment-builder"
docker tag "${PROJECT}-api" "${PROJECT}-migrate"

# runner：api 镜像临时容器跑 Alembic（需要 production 有效 settings 环境）
runner() {
  docker run --rm --network "$NET" \
    -e DAI_ENVIRONMENT=production \
    -e "DAI_DATABASE_URL=$DB_URL" \
    -e "DAI_SECRET_KEY=$DAI_SECRET_KEY" \
    -e "DAI_CORS_ORIGINS=$DAI_CORS_ORIGINS" \
    -e "DAI_ENV_BASE_IMAGE=$DAI_ENV_BASE_IMAGE" \
    -e "DAI_JUDGE_HOST_WORK_DIR=$DAI_JUDGE_HOST_WORK_DIR" \
    -v "$ROOT/backend/alembic/versions:/app/alembic/versions:ro" \
    -v "$ROOT/scripts:/scripts:ro" \
    "${PROJECT}-api" "$@"
}

echo "==> 空库部署序列：启动 mysql redis"
$COMPOSE up -d mysql redis >/dev/null
wait_health mysql healthy 40

echo "==> 部署步骤 1/3：迁移 A（b4c5d6e7f890）"
runner alembic upgrade b4c5d6e7f890

echo "==> 部署步骤 2/3：seed basic 环境（模拟 seed-environments --enqueue 构建完成）"
runner python /scripts/seed-basic-environment-mysql.py

echo "==> 部署步骤 3/3：migrate 一次性服务跑 alembic upgrade head"
$COMPOSE up -d migrate >/dev/null
migrate_rc=$(docker wait "${PROJECT}-migrate-1")
echo "==> migrate 退出码：$migrate_rc"
[ "$migrate_rc" = "0" ] || { echo "FAILED: migrate 服务非 0 退出" >&2; docker logs "${PROJECT}-migrate-1" >&2; exit 1; }
head_rev=$(runner alembic heads | tr -d ' ' | head -1)
echo "==> 数据库 head：$head_rev"

echo "==> 启动 api frontend（api 等待 migrate 成功后才启动）"
$COMPOSE up -d api frontend >/dev/null

echo "==> 等待 api healthy"
wait_health api healthy 60
echo "==> 等待 frontend healthy（depends_on api healthy 后启动）"
wait_health frontend healthy 30

echo "==> Redis 故障 → api unhealthy"
$COMPOSE stop redis >/dev/null
wait_health api unhealthy 60

echo "==> Redis 恢复 → api 重新 healthy"
$COMPOSE start redis >/dev/null
wait_health api healthy 60

echo "==> 杀 api 进程 → restart 策略自动拉起"
$COMPOSE exec -T api sh -c 'kill 1' >/dev/null 2>&1 || true
wait_health api healthy 60

echo "OK: 生命周期烟测全部通过（migrate head=$head_rev）"
