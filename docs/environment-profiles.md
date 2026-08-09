# 环境档位（Environment Profiles）运维手册

> 本文档对应实施计划《环境档位管理 Implementation Plan》Phase 6，覆盖：生产组件、迁移顺序、首次发布、回滚、镜像备份与清理、几百人规模容量建议。
>
> 架构模型：管理员维护「环境档位 → 不可变环境版本 → 受控包版本」，每个版本构建一份统一 judge/kernel 运行镜像并冻结内容 digest；作业/题目/提交/Notebook/实验记录只绑定环境版本 ID，运行时解析为 digest。**生产运行只使用绑定 digest，不使用 `latest` 标签。**

---

## 1. 生产组件

### 1.1 Compose 服务

`docker-compose.prod.yml` 在 `api`/`worker`/`frontend`/`mysql`/`redis` 之外新增 `environment-builder`：

| 服务 | 职责 | 关键点 |
|---|---|---|
| `environment-builder` | 单副本、单并发的环境构建 Worker | `command: python -m app.worker.environment_builder_worker`；只挂载 `/var/run/docker.sock`，**不挂载学生工作目录**；DB 是任务事实源，Redis list 只负责唤醒 |
| `api` / `worker` | 不执行环境构建 | 仅需提供 `DAI_ENV_BASE_IMAGE`（生产校验全局生效） |

现有 `dai-judge-python:latest` / `dai-kernel-python:latest` 仅保留为未绑定环境版本的存量兼容路径与回滚窗口；新提交与新实验一律使用环境版本 digest。

### 1.2 环境变量（.env.example 已收录）

```text
DAI_ENV_BASE_IMAGE=python:3.12-slim@sha256:<64位hex>   # 生产必须带 digest，见 3.1
DAI_ENV_BUILD_QUEUE_NAME=environment:build:queue
DAI_ENV_BUILD_TIMEOUT_SECONDS=3600                     # 单次构建超时上限（60~86400）
DAI_ENV_IMAGE_REPOSITORY=dai-env                       # 镜像仓库前缀
DAI_ENV_BUILD_LOG_MAX_BYTES=61440                      # 构建日志 60 KiB 尾部上限
```

**生产校验（`backend/app/config.py`）**：`DAI_ENVIRONMENT=production` 时 `DAI_ENV_BASE_IMAGE` 必须匹配 `<ref>@sha256:[0-9a-f]{64}`，可变标签（如 `python:3.12-slim`）直接拒绝启动——api/worker/builder 全部进程生效。

### 1.3 构建链路

```text
管理员 seed/API → DB 写入 build job(queued) → Redis rpush 唤醒
environment-builder 消费 → claim(条件更新防抢占) → docker build(临时 tag)
→ 离线 smoke(import + pip freeze) → 捕获 image ID digest → DB 事务内写 digest + 版本转 available
→ 仅全部验证通过后添加正式标签 dai-env:<slug>-v<N>
```

- 构建失败/超时只影响当前版本，不修改旧 available 版本；重试由管理 API 创建新 job（`retry_of_id`）。
- Worker 崩溃后由 lease（60 秒）恢复：超时 → `timed_out`，未超时 → 回 `queued`。
- 构建日志逐行脱敏（URL 凭据 / token / secret / 宿主机绝对路径）并按 60 KiB 截尾入库，仅管理员可见。

---

## 2. 迁移顺序（分两次可部署发布）

> Alembic head：`c5d6e7f8a901`（迁移 B）。迁移 A `b4c5d6e7f890`（控制面五表）→ 迁移 B `c5d6e7f8a901`（业务绑定）。

**上线必须严格按此顺序，不可一次跳过：**

```text
迁移 A（控制面表） → 部署 api/worker/environment-builder → seed 入队
→ 等待 basic/data/torch-cpu v1 全部 available（admin 页面或 seed 输出确认）
→ 三个 digest 真实 smoke 通过 → 镜像备份（docker save / Registry）
→ 迁移 B（业务绑定） → 验证新提交与新实验容器使用 digest → 保留旧镜像一个回滚周期
```

1. **备份**：MySQL 全量、`.env`、现有 Docker 镜像清单（`docker images --format ...` 落盘）。
2. **迁移 A**：`cd backend && ./.venv/Scripts/python.exe -m alembic upgrade b4c5d6e7f890`（或 `upgrade head` 前先确认 seed 前位置）。迁移 A **不触发任何 Docker 构建**。
3. **seed 构建**：`./.venv/Scripts/python.exe -m app.cli seed-environments --enqueue`（幂等，可重复执行）。等待三个档位 `available`。
4. **迁移 B**：`alembic upgrade head`。迁移 B 会主动检查 `basic` 最新 available 版本的 `image_digest` 非空，**不满足则拒绝升级**——不要绕过该检查。
5. **验证**：新提交 `submissions.environment_version_id` 有值；新实验容器 `docker inspect` 显示 `dai.image_digest` label 且与版本一致；判题 `docker run` 参数使用 digest。

### 存量数据回填（迁移 B 内置）

- 存量作业/题目/提交/Notebook 草稿与历史版本/实验记录全部绑定 `basic` v1；
- import 策略：作业/Notebook → `unrestricted`，题目 → `inherit`；
- `ExperimentRecord.environment_version_id` 优先复制其 `NotebookTemplateVersion` 的值。

---

## 3. 首次发布

### 3.1 基础镜像 digest 获取

```bash
docker pull python:3.12-slim
docker image inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
# 输出形如 python@sha256:57cd7c3a... → 写入 DAI_ENV_BASE_IMAGE=python:3.12-slim@sha256:57cd7c3a...
```

digest 是内容寻址，任意节点只要拉取同一镜像即得到相同 digest；`.env.example` 已给出参考值，部署时以服务器实际镜像为准。

### 3.2 种子命令

```bash
# 幂等：已 available 不重建；draft/failed 且无活跃 build job 时才入队
cd backend
./.venv/Scripts/python.exe -m app.cli seed-environments            # 仅建目录/版本
./.venv/Scripts/python.exe -m app.cli seed-environments --enqueue  # 同时入队构建
```

`environment-builder` 在 compose 中随 `docker compose up -d` 常驻；也可在宿主机手动验证：

```bash
docker compose -f docker-compose.prod.yml up -d environment-builder
docker compose -f docker-compose.prod.yml logs -f environment-builder
```

### 3.3 预热

课程开始前 10~15 分钟在所有运行节点：

```bash
docker pull dai-env:basic-v1          # 或 docker load < dai-env-basic-v1.tar
# 每个 digest 做一次离线 import smoke，使层与常用模块进入页缓存
docker run --rm --network none --user 1000:1000 dai-env:basic-v1 python -c "import pytest"
```

运行时强制 `--pull=never`，本机缺 digest 时 fail closed 并告警，**不允许学生请求触发在线拉取**。

---

## 4. 回滚

回滚顺序（自顶向下，任何一步停止都安全）：

1. 停止 `environment-builder`（`docker compose stop environment-builder`），避免产生新版本。
2. 回滚教师/学生前端——不影响控制面数据与已绑定记录。
3. 回滚运行链路代码到 Phase 1，恢复旧 `DAI_JUDGE_IMAGE` / `DAI_KERNEL_IMAGE`（`latest`）配置。
4. 降级迁移 B：`alembic downgrade c5d6e7f8a901-1`（移除业务绑定列；**控制面表与镜像保留**）。
5. 只有确认没有任何业务引用后才考虑降级迁移 A（`alembic downgrade b4c5d6e7f890-1`）。
6. **不删除已生成镜像**；待系统恢复并核对引用后人工处理。

> 降级迁移 B 不删除控制面表、不删除 Docker 镜像——避免不可恢复地破坏镜像审计数据。

---

## 5. 镜像备份与清理

### 备份

历史重判依赖本机仍持有 digest，因此：

- **Docker daemon 数据目录必须纳入主机备份**（Windows Docker Desktop：WSL2 vhdx；Linux：`/var/lib/docker`）。
- 更稳妥：构建成功后 `docker save` 到受保护存储或推送私有 Registry：

```bash
docker save dai-env:basic-v1 -o /backup/dai-env-basic-v1.tar      # 注意 digest 才是运行事实源
docker tag dai-env:basic-v1 registry.example.com/dai-env:basic-v1
docker push registry.example.com/dai-env:basic-v1                 # 未来运行统一用 repository@sha256:...
```

- 备份校验：`docker load < 备份.tar` 后对比 `docker image inspect <tag> --format '{{.Id}}'` 与 DB 中 `environment_versions.image_digest` 一致。

### 清理（禁止全局 prune）

- **禁止执行 `docker image prune -a` / `docker system prune -a`**——会删除历史重判依赖的 digest。
- 自动清理只能删除**数据库完全未引用**的 digest：先查 `environment_versions`/`submissions` 引用，再逐 digest 核对 `docker images --format '{{.ID}}'`，确认无引用才 `docker image rm <id>`。
- 旧构建缓存（`docker builder prune`）可按需清理，不影响已命名镜像。
- 保留多个不可变历史版本时不能假定层全部共享，按 10 组版本预留 100~200 GB 属正常量级。

---

## 6. 容量建议（几百人规模）

> 结论：**当前「单 Worker、Kernel 无准入上限、固定 900 秒回收」的单机方案不能承诺 300~500 人**。300 人 basic-heavy 可采用 256 GiB 加强单机；500 人或 data/torch 占比较高时推荐三节点起步。第一版不必引入 Kubernetes，但必须升级为「有准入、有队列、有资源预算」的运行平台。

### 6.1 内存预算（按容器 `--memory` 上限求和，不可按平均 RSS 乐观超配）

| 同时活跃 Kernel | basic 256 MiB | data 768 MiB | torch-cpu 2048 MiB |
|---:|---:|---:|---:|
| 300 | 75 GiB | 225 GiB | 600 GiB |
| 500 | 125 GiB | 375 GiB | 1000 GiB |

另加：宿主机 + Docker daemon 12~16 GiB；MySQL/Redis/API/前端 12~24 GiB；判题 4~12 GiB；Builder 构建期最多 8 GiB；20% 峰值余量。

| 场景 | 服务器内存最低/推荐 | CPU 最低/推荐 | Docker 盘最低/推荐 |
|---|---:|---:|---:|
| 300 人全 basic | 128/256 GiB | 64/96 核 | 250/500 GB NVMe |
| 500 人全 basic | 192/256 GiB | 96/128 核 | 250/500 GB NVMe |
| 300 人全 data | 384/512 GiB | 96/128 核 | 500 GB/1 TB |
| 500 人全 data | 512/768 GiB | 128/160 核 | 500 GB/1 TB |
| 300~500 人 torch-cpu | ≥768 GiB~1.25 TiB | ≥160~256 核 | 1/2 TB，单机不推荐 |

- 首次上线 Docker 可用磁盘至少 250 GB（镜像+构建缓存+多历史版本可达 100~200 GB），并始终保留 20% 空闲。
- 构建 torch 时主机最好保留 4 GB 以上可用内存；Builder 与高峰运行任务隔离。

### 6.2 必须的容量控制（升级清单）

- Kernel 数量上限 + 按 `minimum_memory_mb` 加权内存预算（Redis 原子准入，30 秒有界等待，超限返回 `KERNEL_CAPACITY_EXCEEDED` HTTP 429 + 中文提示）。
- 压力感知回收：容量 <60% 时 900 秒；60%~75% 时 600 秒；≥75% 时 300 秒；≥90% 或可用内存 <15% 时停止准入并按 LRU 回收（不回收持有执行锁的 Kernel）。课程结束 5 分钟后按 `course_id` 批量回收。
- 启动速率默认每秒 5 个、每节点同时启动 ≤20；同时执行 cell 数限制（排队时间不计入学生 30 秒执行超时）。
- 判题 Worker：每进程 prefetch=1，300 人 8 个、500 人 16 个起步；Judge/Exam 与 AI Worker 分离，防外部 AI 延迟阻塞 Docker 判题。
- Builder 忙时延后：活跃 Kernel 内存预算 >50%、判题队列 >100 或最老任务 >120 秒时保持 queued 不构建。
- 监控：活跃 Kernel 数/内存额度（80% 告警）、宿主机可用内存（25% 告警 / 15% 停准入 / 10% 紧急回收）、Kernel 创建 p95 >15 秒、准入拒绝持续 5 分钟、队列最老任务 120/300 秒、Docker OOM/exit 137、digest 缺失（任意一次立即告警）、Docker 盘 <20% 告警 / <10% 阻止新构建。
- 容量验收必须做 300/500 用户阶梯压测，不能仅用单容器 smoke 推断。

### 6.3 推荐三节点方案（500 人 basic/data 混合）

| 节点 | 建议配置 | 职责 |
|---|---|---|
| 控制/判题节点 | 32 核、64 GiB、1 TB NVMe | API、MySQL、Redis、8~16 Judge Worker、AI Worker、低峰期 Builder |
| Kernel 节点 A | 64~96 核、256 GiB、1 TB NVMe | Notebook Kernel |
| Kernel 节点 B | 64~96 核、256 GiB、1 TB NVMe | Notebook Kernel |

torch-cpu 初始全局上限 128，超过排队或提示。多节点需：构建镜像推私有 Registry、session 元数据与 label 增加 `runtime_node_id`、Docker CLI 封装为容器运行接口、node-local runtime agent + 调度器（剩余内存额度优先、活跃次数优先）、不暴露无认证 Docker socket。

---

## 7. 日常运维操作

```bash
# 查看构建队列与 job
docker compose -f docker-compose.prod.yml logs -f environment-builder
# 管理 API（admin token）：
GET  /environments/builds                    # 任务列表
GET  /environments/builds/{job_id}/log       # 脱敏日志
POST /environments/builds/{job_id}/retry     # 重试失败任务
```

- 版本进入 `available` 后完全不可变（包集合/基础镜像/资源/digest 均不可编辑），修改只能从旧版本复制出 vN+1。
- 停用 profile/version 只阻止新选择，不影响已绑定记录与镜像。
- 日志脱敏抽查：`GET /environments/builds/{job_id}/log` 不应出现 `http://user:pass@`、`Authorization: Bearer ...`、`--secret id=...`、`C:\...` 或 `/home/...` 宿主机路径。

## 8. 故障排查速查

| 现象 | 处理 |
|---|---|
| seed 后版本一直 draft | 确认 `environment-builder` 在跑、Redis 队列名一致、`docker ps` 正常 |
| 构建 failed `SMOKE_IMPORT_FAILED` | 看日志中缺失模块名；包版本冲突时在 package catalog 新建修订版本 |
| 构建 timed_out | 检查 Docker 磁盘/网络；`DAI_ENV_BUILD_TIMEOUT_SECONDS` 上限 86400 |
| 判题 `system_error` | 先查 digest 是否仍在本机（`docker image inspect <digest>`）；确认后从备份 `docker load` |
| 迁移 B 拒绝升级 | basic v1 尚未 available/digest 为空——先完成 seed 构建 |
| 生产启动被拒 | `DAI_ENV_BASE_IMAGE` 必须是带 `@sha256:` 的引用，见 3.1 |
