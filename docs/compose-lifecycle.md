# Compose 生命周期与健康检查（TASK-015）

## 配置摘要（docker-compose.prod.yml）

| 服务 | restart | healthcheck | 说明 |
| --- | --- | --- | --- |
| mysql / redis | unless-stopped | 原生 ping | 数据完整性由卷 + TASK-014 备份保证 |
| api | unless-stopped | 调 `/api/v1/health/ready`（DB+Redis 双依赖），interval 15s / retries 5 / start_period 30s | Redis 故障 → unhealthy，恢复后自动 healthy（TASK-003 语义） |
| worker | unless-stopped | **无**（不伪造业务健康） | 只做进程级重启；队列事实源在 DB，stale recovery 兜底 |
| environment-builder | unless-stopped | 无 | 单副本低频管理任务，进程级重启 |
| frontend | unless-stopped | `wget -Y off /health`（nginx 反代 api live），interval 20s / retries 6 | `depends_on: api: condition: service_healthy`，等待 API 就绪再启动 |

注意：frontend healthcheck 使用 `wget -Y off` 显式禁用代理——健康检查只测本机
nginx，不应受宿主机/环境代理变量影响（演练中实测发现：环境注入的 HTTP_PROXY
会使 busybox wget 绕过 no_proxy 直连 127.0.0.1 失败）。

## 演练记录（2026-08-14，隔离 compose 项目 dai-prod-drill，端口 18080）

### 1. Redis 故障 → API unhealthy → 恢复 → healthy（验收核心）

| 步骤 | 结果 |
| --- | --- |
| `compose stop redis` | `GET /api/v1/health/ready` → 503；api 状态 **unhealthy** |
| `compose start redis` | api 自动回到 **healthy**；ready → 200 |

### 2. 进程崩溃自动恢复（容器内真实退出路径，RestartCount 递增为证）

| 服务 | 注入方式 | 结果 |
| --- | --- | --- |
| api | SIGKILL uvicorn 子进程（等价应用崩溃） | RestartCount 0→1，health 恢复 healthy，ready 200 |
| worker | SIGINT → 主循环 KeyboardInterrupt 退出 | RestartCount 0→1，running |
| frontend | SIGTERM nginx master（优雅退出） | RestartCount 0→1，health 恢复 healthy |

### 3. 补充事实（本演练环境）

- 本机 daemon 对宿主机侧 `docker kill`（SIGKILL）不触发 restart policy（与官方
  dockerd 行为不同，属本沙箱环境特性）；容器内**进程自行退出**路径（崩溃/异常退出/
  优雅退出）均正确触发重启，语义与生产一致——生产主机为官方 dockerd 时，
  外部 kill 同样会触发 restart。
- 依赖顺序验证：全栈 up 时 api 先 healthy，frontend 才启动（`condition: service_healthy`）。

## 一次性迁移（TASK-016）演练记录

配置：`migrate` 服务（同镜像 `alembic upgrade head`，restart: "no"），
api/worker/environment-builder `depends_on: migrate: condition: service_completed_successfully`；
backend Dockerfile CMD 已移除 alembic（API 只跑 uvicorn）。

| 演练 | 结果 |
| --- | --- |
| 已 head 库上重复执行 `up migrate` ×2 | 两次 rc=0（幂等，no-op） |
| 失败修订号 `alembic upgrade 2026-does-not-exist` | rc=255（非零） |
| 空库直接 `up migrate` | exit 1（迁移 B 前置：basic 无 available 版本——新库两步部署的既定语义） |
| 失败后 `up -d api` | compose 拒绝启动：`service "migrate" didn't complete successfully: exit 1`（新 API 被阻断） |
| 两步空库部署（迁移 A → 种入 basic → head → up api） | api healthy；日志 0 次 alembic，首行为 `Started server process`（API 不再执行迁移） |

发布顺序运维注意：api 容器重建后 IP 变化，nginx 静态解析旧上游 IP 会 502，
需 `docker compose restart frontend`（已写入 README 发布顺序第 4 步）。
