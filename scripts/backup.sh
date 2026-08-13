#!/usr/bin/env bash
# DAI 实验平台 —— 单机生产数据备份（TASK-014）
#
# 用法:  DAI_BACKUP_DIR=/data/dai-backups [COMPOSE_PROJECT_NAME=dai-prod] ./scripts/backup.sh
#
# 备份内容: MySQL 全库（single-transaction + routines/triggers/events）、
#           Redis（redis-cli --rdb 一致性快照）、studio/video/cover 数据卷、
#           环境档位镜像（dai-env:*，可用 DAI_BACKUP_ENV_IMAGES=0 跳过）
# 保留策略: 7 个日备 + 4 个周备（日备超过 7 天时，每周只保留该周最后一份并升为周备）
# 目标指标: RPO 24 小时、RTO 4 小时（恢复步骤见 docs/backup-restore.md）
#
# 安全约束:
#   - 备份输出必须在 Compose 卷之外（脚本强制检查，拒绝 /var/lib/docker/volumes 下路径）
#   - 凭据一律不写入仓库/脚本：MySQL 凭据从容器内环境变量读取，
#     Redis/卷/镜像无凭据；如需加密备份请在生产环境另行加锁（如 dm-crypt）
#   - 幂等：同日重复执行覆盖当日日备，不会产生重复目录
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${DAI_COMPOSE_FILE:-$PROJECT_DIR/docker-compose.prod.yml}"
DAI_BACKUP_DIR="${DAI_BACKUP_DIR:?必须设置 DAI_BACKUP_DIR（备份输出目录，必须在 Compose 卷之外）}"
KEEP_DAILY="${DAI_KEEP_DAILY:-7}"
KEEP_WEEKLY="${DAI_KEEP_WEEKLY:-4}"

log()  { printf '\033[36m[backup]\033[0m %s\n' "$*" | tee -a "$DAI_BACKUP_DIR/backup.log"; }
die()  { printf '\033[31m[backup]\033[0m %s\n' "$*" | tee -a "$DAI_BACKUP_DIR/backup.log" >&2; exit 1; }

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

# ── 1. 前置检查 ──────────────────────────────────────────────
[ -f "$COMPOSE_FILE" ] || die "未找到 Compose 文件: $COMPOSE_FILE"
mkdir -p "$DAI_BACKUP_DIR"

BACKUP_REAL="$(realpath -m "$DAI_BACKUP_DIR")"
case "$BACKUP_REAL" in
  /var/lib/docker/volumes/*)
    die "备份目录不得位于 Docker 卷内（$BACKUP_REAL）——卷丢失将连带备份丢失" ;;
esac

# 可用空间检查（少于 20% 直接失败，避免备份写坏磁盘）
AVAIL_PCT="$(df --output=pcent "$BACKUP_REAL" | tail -1 | tr -d ' %')"
[ "$AVAIL_PCT" -lt 80 ] || die "备份目录所在磁盘可用空间不足（已用 ${AVAIL_PCT}%）"

compose ps --status running mysql redis >/dev/null 2>&1 \
  || die "mysql/redis 服务未运行，请先确认生产 Compose 栈状态（docker compose -f $COMPOSE_FILE ps）"

# ── 2. 备份 ──────────────────────────────────────────────────
TODAY="$(date +%F)"
TS="$(date '+%F %T %z')"
DEST="$DAI_BACKUP_DIR/daily-$TODAY"
mkdir -p "$DEST/mysql" "$DEST/redis" "$DEST/volumes" "$DEST/images"
log "开始备份 → $DEST（$TS）"

# MySQL：容器内执行 mysqldump，密码取自容器环境变量，不经过宿主机命令行
compose exec -T mysql sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers --events "$MYSQL_DATABASE"' \
  > "$DEST/mysql/dai_platform.sql"
grep -q "Dump completed" "$DEST/mysql/dai_platform.sql" || die "MySQL dump 不完整（缺少 Dump completed 结尾）"
log "MySQL dump 完成（$(wc -c < "$DEST/mysql/dai_platform.sql") 字节）"

# Redis：redis-cli --rdb 一致性快照，经 stdout 二进制安全导出
compose exec -T redis sh -c \
  'redis-cli --rdb /tmp/dai-redis-backup.rdb >/dev/null 2>&1 && cat /tmp/dai-redis-backup.rdb && rm -f /tmp/dai-redis-backup.rdb' \
  > "$DEST/redis/redis.rdb"
head -c 5 "$DEST/redis/redis.rdb" | grep -q "REDIS" || die "Redis 快照无效（缺少 RDB 魔数）"
log "Redis 快照完成（$(wc -c < "$DEST/redis/redis.rdb") 字节）"

# 数据卷：只读挂载 + tar 导出（不停止业务服务）
PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$PROJECT_DIR")}"
for vol in studio_data video_data cover_data; do
  docker run --rm \
    -v "${PROJECT}_${vol}:/src:ro" \
    -v "$DEST/volumes:/backup" \
    alpine:3.20 tar czf "/backup/${vol}.tar.gz" -C /src . \
    || die "数据卷 $vol 导出失败"
  log "数据卷 $vol 导出完成（$(wc -c < "$DEST/volumes/${vol}.tar.gz") 字节）"
done

# 环境档位镜像（可选——可由 environment-builder 按 DB 事实重建，属加速项而非唯一副本）
if [ "${DAI_BACKUP_ENV_IMAGES:-1}" = "1" ]; then
  # shellcheck disable=SC2046  # 按行拆分镜像名是有意行为
  ENV_IMAGES="$(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '^dai-env' || true)"
  if [ -n "$ENV_IMAGES" ]; then
    # shellcheck disable=SC2086
    docker image save -o "$DEST/images/dai-env-images.tar" $ENV_IMAGES
    log "环境镜像导出完成（$(wc -c < "$DEST/images/dai-env-images.tar") 字节）"
  else
    log "无 dai-env:* 镜像，跳过镜像备份"
  fi
fi

# ── 3. 校验和清单 ────────────────────────────────────────────
( cd "$DEST" && find . -type f -name '*.sql' -o -type f -name '*.rdb' -o -type f -name '*.tar.gz' -o -type f -name '*.tar' \
  | sort | xargs -r sha256sum ) > "$DEST/manifest.txt"
echo "BACKUP_TS=$TS" >> "$DEST/manifest.txt"
log "校验和清单生成完成"

# ── 4. 保留策略：7 日备 + 4 周备 ──────────────────────────────
CUTOFF="$(date -d "$TODAY - $KEEP_DAILY days" +%F)"

# 收集过期日备（ISO 日期字符串比较）
OLDS=()
for d in "$DAI_BACKUP_DIR"/daily-*/; do
  [ -d "$d" ] || continue
  DDATE="${d##*/}"; DDATE="${DDATE#daily-}"; DDATE="${DDATE%/}"
  [ "$DDATE" \< "$CUTOFF" ] && OLDS+=("$DDATE")
done

if [ "${#OLDS[@]}" -gt 0 ]; then
  # 升序排列；每周只把该周最后一份升为周备，其余删除
  mapfile -t OLDS < <(printf '%s\n' "${OLDS[@]}" | sort)
  LAST_WEEK=""; LAST_DATE=""
  for DDATE in "${OLDS[@]}"; do
    WEEK="$(date -d "$DDATE" +%G-W%V)"
    if [ "$WEEK" != "$LAST_WEEK" ]; then
      [ -n "$LAST_DATE" ] && mv "$DAI_BACKUP_DIR/daily-$LAST_DATE" "$DAI_BACKUP_DIR/weekly-$LAST_DATE"
      LAST_WEEK="$WEEK"; LAST_DATE="$DDATE"
    else
      rm -rf "$DAI_BACKUP_DIR/daily-$DDATE"
      LAST_DATE="$DDATE"
    fi
  done
  [ -n "$LAST_DATE" ] && mv "$DAI_BACKUP_DIR/daily-$LAST_DATE" "$DAI_BACKUP_DIR/weekly-$LAST_DATE"
fi

# 周备只保留最新 KEEP_WEEKLY 份
WKS=()
for w in "$DAI_BACKUP_DIR"/weekly-*/; do
  [ -d "$w" ] && WKS+=("${w%/}")
done
if [ "${#WKS[@]}" -gt "$KEEP_WEEKLY" ]; then
  mapfile -t WKS < <(printf '%s\n' "${WKS[@]}" | sort -r)
  for ((i = KEEP_WEEKLY; i < ${#WKS[@]}; i++)); do
    rm -rf "${WKS[$i]}"
  done
fi

log "备份完成：$DEST（日备 $KEEP_DAILY / 周备 $KEEP_WEEKLY）"
