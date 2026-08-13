# 备份与恢复 Runbook（TASK-014）

目标指标：**RPO 24 小时 / RTO 4 小时**。备份由 `scripts/backup.sh` 每日执行，
保留 7 个日备 + 4 个周备；输出在 Compose 卷之外，凭据不落仓库。

## 1. 定时备份

生产主机 cron（示例，凌晨 02:15 错峰）：

```cron
15 2 * * * COMPOSE_PROJECT_NAME=dai-prod DAI_BACKUP_DIR=/data/dai-backups /opt/dai-experiment-platform/scripts/backup.sh >> /data/dai-backups/cron.log 2>&1
```

备份内容与校验：

| 组件 | 方式 | 校验 |
| --- | --- | --- |
| MySQL | `mysqldump --single-transaction --routines --triggers --events`（容器内执行，密码取容器环境变量） | `Dump completed` 结尾 + manifest sha256 |
| Redis | `redis-cli --rdb` 一致性快照 | RDB 魔数 `REDIS` + sha256 |
| studio/video/cover 卷 | 只读挂载 + tar.gz（不停止服务） | sha256 |
| dai-env 镜像 | `docker image save`（可选，`DAI_BACKUP_ENV_IMAGES=0` 跳过；可由 environment-builder 重建） | sha256 |

目录结构：`<DAI_BACKUP_DIR>/daily-YYYY-MM-DD/{mysql,redis,volumes,images}/` + `manifest.txt`（sha256 清单）。

## 2. 恢复流程（先隔离演练，再碰生产）

> 生产恢复前必须先在本机隔离环境完成一次演练（见 §4）。以下步骤同时是演练步骤。

### 2.1 MySQL

```bash
# 1) 起一个全新的隔离 MySQL（不要挂载生产卷）
docker run -d --name dai-restore-mysql -e MYSQL_ROOT_PASSWORD=<新密码> \
  -e MYSQL_DATABASE=dai_platform mysql:8.0
# 2) 等待 healthy 后导入
docker exec -i dai-restore-mysql sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" dai_platform' \
  < <备份>/mysql/dai_platform.sql
# 3) 校验：表数量与业务行数
docker exec dai-restore-mysql mysql -uroot -p... -N -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dai_platform';
   SELECT COUNT(*) FROM dai_platform.users;"
```

### 2.2 Redis

> 注意（演练实测）：Redis 7 的 multi-part AOF 在 manifest 缺失时**不会**回退加载
> `dump.rdb`；且 `docker cp` 写入已停止容器的文件会被卷挂载遮蔽。
> 因此恢复必须经由卷操作 + 先以 `appendonly no` 加载 RDB，再在线转换回 AOF：

```bash
# 0) 准备卷（停止并清空旧数据）
docker volume create dai-restore-redis-data   # 若不存在
docker stop dai-restore-redis 2>/dev/null || true
docker run --rm -v dai-restore-redis-data:/data alpine:3.20 \
  sh -c 'rm -rf /data/appendonlydir /data/dump.rdb'
# 1) 放入快照（必须写卷，不要 docker cp 到停止的容器）
docker run --rm -v dai-restore-redis-data:/data -v <备份>/redis:/src:ro \
  alpine:3.20 sh -c 'cp /src/redis.rdb /data/dump.rdb && chown -R 999:1000 /data'
# 2) 先以 appendonly no 启动（经典 RDB 加载路径），校验关键键
docker run -d --name dai-restore-redis -p 6380:6379 \
  -v dai-restore-redis-data:/data redis:7-alpine redis-server --appendonly no
docker exec dai-restore-redis redis-cli keys '*'
# 3) 在线转换回 AOF，再按生产命令（appendonly yes）重启验证
docker exec dai-restore-redis redis-cli CONFIG SET appendonly yes
docker exec dai-restore-redis redis-cli BGREWRITEAOF
docker stop dai-restore-redis && docker rm dai-restore-redis
docker run -d --name dai-restore-redis -p 6380:6379 -v dai-restore-redis-data:/data \
  redis:7-alpine redis-server --appendonly yes --appendfsync everysec
docker exec dai-restore-redis redis-cli keys '*'
```

### 2.3 数据卷

```bash
for vol in studio_data video_data cover_data; do
  docker volume create dai-restore-$vol
  docker run --rm -v dai-restore-$vol:/dst -v <备份>/volumes:/src alpine:3.20 \
    sh -c "tar xzf /src/$vol.tar.gz -C /dst"
done
# 校验：与源卷逐文件 sha256 对比
```

### 2.4 环境镜像（可选）

```bash
docker load -i <备份>/images/dai-env-images.tar
```

### 2.5 应用烟测

用后端镜像（`DAI_ENVIRONMENT` 按需设为 production/development）连接恢复后的
MySQL/Redis，依次验证：

1. `GET /api/v1/health/ready` → 200（DB + Redis 双依赖通过）
2. 备份前种入的测试账号 `POST /api/v1/auth/login` → 200 且返回 token（关键用户旅程）

全部通过后方可把步骤套用到生产卷/容器。

## 3. 回滚与安全

- 恢复脚本只写入隔离目标（新容器名/新卷名），**不得**覆盖生产容器/卷；
- 生产恢复时先 `docker compose stop`（保卷），再按 §2 换入恢复产物；
- 备份目录磁盘使用需监控：日备×7 + 周备×4，`df` 可用 <20% 时 `backup.sh` 直接失败。

## 4. 恢复演练记录

> 以下记录由真实演练产出，演练环境与生产无关（隔离容器/卷/目录）。

见下节「演练证据」——每次演练后追加时间戳记录。

### 演练证据（2026-08-14，首次，隔离环境）

**演练环境**（与生产无关）：源栈 `dai-prod-drill`（compose 项目，MySQL8.0+Redis7 AOF）、
恢复栈 `dai-restore-*` 独立容器/卷；备份目录 `/tmp/dai-backup-drill`。

**源数据种子**：2 用户（drill_stu / drill_teacher，bcrypt 密码 DrillPass123!）、1 课程、
Redis 2 键（auth:refresh:drill / blacklist:drill-jti）、studio 卷 2 文件（drill.txt + nested/blob.bin 64KiB）。

**备份**（`scripts/backup.sh`，TS=2026-08-14 00:43:56 +0800）：

| 组件 | 大小 | sha256（前 16 位） |
| --- | --- | --- |
| mysql/dai_platform.sql | 54,904 B | c432eae3c65b5899 |
| redis/redis.rdb | 242 B | b8c2e874360563e2 |
| volumes/studio_data.tar.gz | 65,830 B | 3ffef0454d27bc38 |
| volumes/video_data.tar.gz | 85 B | 785939deacb3337c |
| volumes/cover_data.tar.gz | 85 B | 785939deacb3337c |
| images/dai-env-images.tar | 205,622,784 B | a102d7bf61bc9386 |

manifest 内 6 项 `sha256sum -c` 全部 OK。

**恢复核验**：

| 项 | 源 | 恢复后 | 结果 |
| --- | --- | --- | --- |
| MySQL 表数 | 35 | 35 | ✓ |
| users / courses 行数 | 2 / 1 | 2 / 1（drill_stu、drill_teacher、演练课程） | ✓ |
| Redis 键 | auth:refresh:drill、blacklist:drill-jti | 同左（经 RDB 加载 → BGREWRITEAOF 转换 → AOF 配置重启后仍在） | ✓ |
| studio 卷校验和 | 475bfdbf…/08dbc2f0… | 完全一致 | ✓ |
| 应用烟测 | — | `GET /api/v1/health/ready` → 200；`POST /api/v1/auth/login`（drill_stu/DrillPass123!）→ 200 + token | ✓ |

**耗时**：备份 <1 分钟（含 205MB 镜像）；恢复全流程（含 MySQL 初始化等待）约 10 分钟 < RTO 4h。

**演练发现并已修正**：
1. `backup.sh` 保留策略的日备日期提取 bug（`${d##*-}` 截断成 `14`）→ 已修复并复跑通过；
2. Redis 7 multi-part AOF 不会回退加载 dump.rdb，且 `docker cp` 写停止容器会被卷遮蔽
   → runbook §2.2 已改为卷操作 + `appendonly no` 加载 + 在线 `BGREWRITEAOF` 转换流程。

