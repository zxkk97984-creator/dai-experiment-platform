# 环境档位（Environment Profiles）运维手册

> 本文档对应实施计划《环境档位管理 Implementation Plan》Phase 6，覆盖：生产组件、迁移顺序、首次发布、回滚、镜像备份与清理、几百人规模容量建议。
>
> 架构模型：管理员维护「环境档位 → 不可变环境版本 → 受控包版本」，每个版本构建一份统一 judge/kernel 运行镜像并冻结内容 digest；作业/题目/提交/Notebook/实验记录只绑定环境版本 ID，运行时解析为 digest。**生产运行只使用绑定 digest，不使用 `latest` 标签。**

## 当前状态与验收边界（2026-08-21）

环境编辑器 V2 的控制面和业务链路已经落地：Profile/Draft/immutable Version、包与 Python 版本校验、构建队列与 Worker heartbeat、结构化构建错误、发布/回滚、历史绑定和教师选择均已实现；后端自动化测试 `1267 passed, 3 skipped`，前端 `859 passed`，前端检查与生产构建通过。

本地代码验收不等于生产镜像验收。本轮剩余工作属于部署方必须在**真实部署机**完成的外部条件：

1. 部署机上的 Docker daemon 正常运行，Compose 服务能受控访问 Docker socket；
2. Registry 仓库和只读 Docker `config.json` Secret 已配置；
3. `environment-builder` 实际构建镜像、推送并按 digest 回拉，数据库只记录远端可拉取的 digest；
4. 分阶段 Alembic migration、Worker heartbeat、API readiness 和教师/学生真实链路完成现场 smoke。

因此，受限执行环境中的 `permission denied ... /var/run/docker.sock` 只能说明当前执行上下文没有 Docker daemon 权限，不能作为 V2 业务逻辑失败，也不能作为生产构建已完成的证据。

## 0. 环境编辑器 V2

V2 将管理员操作收敛为“Profile + Draft + immutable Version”三层：新建环境只需要名称和描述，系统自动创建 Python 3.12、256 MB 的草稿；管理员在草稿中选择 Python、直接 Python 包和 Debian 系统包，保存后提交构建。Worker 在固定 digest 的基础镜像内解析依赖、生成锁定结果并执行验证。构建成功只得到 `ready` 候选版本，必须由管理员单独确认发布。

状态含义：

| 对象状态 | 管理员 | 教师新选择 | 已绑定记录运行 |
|---|---|---|---|
| `editing` | 可编辑 | 不可见 | 不适用 |
| `building` | 编辑区锁定 | 不可见 | 不适用 |
| `failed` | 可修改或按服务端 capability 重试 | 不可见 | 不适用 |
| `ready` / version `available` | 查看报告、确认发布 | 发布前不可见 | 镜像可运行 |
| 当前发布版本 | 内容不可修改 | 每个 Profile 只显示这一版 | 可运行 |
| 历史已发布版本 | 内容不可修改、可回滚 | 仅已有绑定补充显示 | 继续可运行 |

发布或回滚只更新 `environment_profiles.current_version_id` 和审计表，不批量改动作业、提交、Notebook 或实验记录。归档 Profile 只隐藏教师新选择，已有绑定仍按版本 digest 运行。放弃草稿后才允许回滚；回滚目标必须是同 Profile 的历史发布版本且镜像仍可用。

### 0.1 V2 配置

V2 默认关闭。先部署迁移、API 和 Worker，确认构建服务就绪后再开启 `DAI_ENVIRONMENT_EDITOR_V2_ENABLED=true`。生产必须为 3.10、3.11、3.12 分别配置带 digest 的基础镜像：

```text
DAI_ENVIRONMENT_EDITOR_V2_ENABLED=false
DAI_ENV_PYTHON_BASE_IMAGES={"3.10":"python:3.10-slim-bookworm@sha256:<64位hex>","3.11":"python:3.11-slim-bookworm@sha256:<64位hex>","3.12":"python:3.12-slim-bookworm@sha256:<64位hex>"}
DAI_ENV_REGISTRY_REPOSITORY=registry.example/dai-env
DAI_ENV_REGISTRY_DOCKER_CONFIG=/run/secrets/config.json
DAI_ENV_REGISTRY_ALLOW_ANONYMOUS=false
DAI_ENV_PIP_INDEX_URL=https://pypi.org/simple
DAI_ENV_BUILD_NETWORK_MODE=default       # 仅构建安装阶段可选 host
DAI_ENV_BUILD_HTTP_PROXY=                 # 不隐式继承 Worker 宿主机代理
DAI_ENV_PLATFORM_BUNDLE_VERSION=v1
DAI_ENV_BUILD_CPU_LIMIT=2
DAI_ENV_BUILD_MEMORY_MB=4096
DAI_ENV_BUILD_PIDS_LIMIT=512
DAI_ENV_BUILD_MAX_IMAGE_BYTES=21474836480
DAI_ENV_BUILDER_HEARTBEAT_TTL_SECONDS=30
DAI_ENV_BUILDER_HEARTBEAT_INTERVAL_SECONDS=10
```

Registry 登录使用 Compose 的只读 Docker Secret（标准 `config.json`）。文件只允许 `auths` 及其中的 `auth`/`identitytoken`，不允许 `credsStore`、`credHelpers` 或 `proxies`；真实文件不提交 Git。匿名 Registry 必须显式设置 `DAI_ENV_REGISTRY_ALLOW_ANONYMOUS=true`。`GET /build-readiness` 还会检查 `environment:v2:builder:heartbeat` 的 Redis TTL；Worker 只有在数据库对账和 Docker daemon 检查都成功后才开始续租。

系统包源由平台按基础镜像绑定 Debian 快照；管理员不能提交 Dockerfile、shell、pip/apt 源或 URL/VCS 依赖。Python 包版本为空表示构建时解析最新兼容稳定版；直接依赖克隆到草稿时会固定当前已解析版本。平台固定的 `ipykernel`、`pytest` 和运行器不能从草稿删除。

### 0.2 管理 API 和排障

V2 管理端点均位于现有 `/environments` Router：`GET /editor-options`、`GET /build-readiness`、`GET/POST/PATCH /profiles`、`GET/PUT/DELETE /profiles/{id}/draft`、`POST /profiles/{id}/draft/builds`、`GET /profiles/{id}/versions`、`POST /profiles/{id}/publications`、`GET /builds/{id}`、`GET /builds/{id}/log` 和 `POST /builds/{id}/retry`。`GET /available` 只返回每个 active Profile 的 current version；已有绑定补充历史摘要使用 `GET /versions/{version_id}/summary`，响应不含镜像 digest、tag、基础镜像或源地址。

常见错误码：

- `DRAFT_REVISION_CONFLICT`：刷新服务器草稿，或在最新 revision 上重新应用本地修改。
- `DRAFT_BUILD_ACTIVE` / `NO_ENVIRONMENT_CHANGES`：等待当前构建，或保存实际修改后再构建。
- `PIP_PACKAGE_NOT_FOUND` / `PIP_RESOLUTION_FAILED` / `DEPENDENCY_CONFLICT`：检查包名和精确版本；最终以 Worker 在目标基础镜像中的解析报告为准。
- `APT_PACKAGE_DENIED` / `APT_PACKAGE_NOT_FOUND`：检查平台 denylist、包名和快照版本。
- `BUILD_PROXY_UNREACHABLE`：默认 Docker 网络不能访问 `127.0.0.1`/`localhost` 代理；配置显式可达代理，或经审核后仅为构建安装阶段启用 `host` 网络。
- `VERSION_NOT_PUBLISHABLE` / `CURRENT_VERSION_CONFLICT`：目标必须是本草稿 ready 候选或历史已发布镜像，并携带最新 current version 做并发保护。

历史失败 job 的“重试”按钮由服务端 capability 决定：只有它仍是当前 Draft 候选、最近一次 attempt、候选尚未成功且草稿未改动时才可重试。若草稿已修改，必须创建新的版本号；旧失败版本和日志保留。

### 0.3 V2 迁移

当前 V2 迁移链从 `20260820_0001` 到 `20260820_0003`，基于 `20260819_0003`。迁移会新增 Draft/Publication 表、回填 requested/resolved spec、固定历史 Python 3.12、设置 current pointer 和 migration baseline 审计记录，并为 Profile/Version 建立同 Profile 复合外键；不删除旧包目录、镜像、构建日志或业务外键。

**全新库不能直接执行 `upgrade head`。** 旧的业务绑定迁移 `c5d6e7f8a901` 会在升级必填环境外键前检查 `basic` 是否已有真实 `available + image_digest`。请在已备份、可回滚的维护窗口严格按以下顺序执行：

```bash
# 0. 只启动数据库和 Redis，不启动 API/Worker
docker compose -f docker-compose.prod.yml up -d mysql redis

# 1. 迁移到控制面（迁移 A）
docker compose -f docker-compose.prod.yml run --rm migrate \
  alembic upgrade b4c5d6e7f890

# 2. 写入已经通过 smoke、并已保存到 Registry/备份的 basic 镜像 digest
#    生产禁止省略该变量，也不要使用 000.../111... 占位值。
DAI_ENVIRONMENT=production \
DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST=sha256:<64位hex> \
DAI_DATABASE_URL=mysql+pymysql://... \
  python scripts/seed-basic-environment-mysql.py

# 3. 完成旧业务绑定迁移及 V2 additive migration
docker compose -f docker-compose.prod.yml run --rm migrate \
  alembic upgrade head

# 4. 迁移后检查，确认旧 digest/外键不变，再启动完整栈
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml up -d
```

`seed-basic-environment-mysql.py` 在非生产环境可用于一次性空库烟测；生产必须提供 `DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST`，脚本会拒绝占位值。若没有可信的 basic 预构建产物，应停止在步骤 1，先用发布版本对应的旧构建流程生成并验证产物，不能为了通过迁移检查伪造 digest。

降级默认被拒绝，因为会删除 V2 业务列和审计数据；只有一次性、已备份的测试库显式设置开关后才允许升级/降级循环：

```bash
export DAI_ALLOW_ENVIRONMENT_V2_DOWNGRADE=true
.venv/bin/python -m alembic downgrade 20260819_0003
.venv/bin/python -m alembic upgrade head
```

生产环境不设置该变量；异常时关闭 V2 功能开关并保留数据库、版本和 Registry 镜像，不执行 downgrade。

关闭 V2 开关可恢复旧读/写流程；开启 V2 后旧包目录和旧版本创建写接口返回 `LEGACY_ENVIRONMENT_API_DISABLED`，读取接口保留。不要通过删除迁移、版本或镜像来回滚。

### 0.4 部署机、Docker daemon 与 Registry 的最终验收

这三个概念必须分开：

- **Docker daemon** 是实际创建容器和构建镜像的后台引擎（通常由 `dockerd` 提供）；Docker CLI 只是客户端。
- **Docker socket**（通常是 `/var/run/docker.sock`）是 CLI/Worker 与 daemon 通信的 Unix socket。生产 Compose 只给确需容器生命周期权限的 `api`、`worker`、`environment-builder` 挂载它；它的权限等价于较高的主机控制权。
- **部署机** 是真正运行 Docker daemon、MySQL/Redis 和 Compose 的服务器或虚拟机，不是 API 容器，也不是 Codex/CI 的受限执行沙箱。
- **Registry** 是保存环境镜像的仓库（Harbor、云 Registry 或 Docker Hub 等）。构建成功后必须推送到仓库并按 digest 回拉，教师和学生运行时不依赖可变 `latest` 标签。

#### 部署前检查

以下检查必须在部署机执行：

```bash
# Docker daemon 可用；permission denied 表示主机权限或 daemon 配置问题
docker info

# Compose、必填变量和 Registry Secret 文件可解析
docker compose -f docker-compose.prod.yml config --quiet
test -r "$DAI_ENV_REGISTRY_DOCKER_CONFIG_FILE"

# 确认 daemon 没有对外暴露未经保护的 Docker TCP API（Linux）
ss -lnt | grep -E ':(2375|2376)\b' && echo '拒绝：Docker TCP API 不应公网监听' || true
```

rootful Docker 通常通过受控的 `docker` 用户组访问 socket；rootless Docker 使用 rootless socket 路径，需同步调整 Compose 的 socket 挂载和 `DOCKER_HOST`。无论采用哪种方式，都不要使用 `chmod 666 /var/run/docker.sock` 绕过权限，也不要把 Docker API 发布到 2375/2376。部署主机应专机专用，并按 [`docs/security/docker-socket-isolation.md`](security/docker-socket-isolation.md) 完成风险确认。

#### Registry Secret

`DAI_ENV_REGISTRY_DOCKER_CONFIG_FILE` 指向部署机上的真实 `config.json`，Compose 将其作为只读 Secret 挂载到 `/run/secrets/config.json`。文件只能包含顶层 `auths` 以及每个仓库的 `auth` 或 `identitytoken`；禁止提交真实凭据，也不要使用 `credsStore`、`credHelpers` 或 `proxies`。匿名 Registry 只有在明确设置 `DAI_ENV_REGISTRY_ALLOW_ANONYMOUS=true` 时才允许，生产默认应保持 `false`。

#### 真实构建与推送验收

```bash
# 启动数据库和 Redis；迁移命令按本手册 0.3 的分阶段顺序执行
docker compose -f docker-compose.prod.yml up -d mysql redis
docker compose -f docker-compose.prod.yml run --rm migrate alembic upgrade b4c5d6e7f890
# 准备并验证 basic 真实 digest 后，再执行 upgrade head
docker compose -f docker-compose.prod.yml run --rm migrate alembic upgrade head

# 启动完整栈并观察构建 Worker
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f environment-builder
```

随后用管理员账号创建测试 Profile，加入一个轻量 Python 包和 Debian 包，保存草稿并点击构建。验收必须同时满足：

| 检查点 | 通过标准 |
|---|---|
| readiness | API 显示 Registry 可用、Worker heartbeat 未过期、Docker daemon 可用 |
| build | job 从 `queued` 进入 `running`，完成依赖解析、smoke 和 `pip check` |
| push/pull | Worker 推送到 `DAI_ENV_REGISTRY_REPOSITORY`，再按远端 digest 回拉成功 |
| 数据落库 | 版本进入 `available`，`image_digest` 为真实 `sha256:<64 位 hex>`，旧版本未被修改 |
| 教师链路 | 教师新建作业只看到当前发布版本；旧作业仍绑定原版本 |
| 回滚链路 | 回滚只改变 Profile current pointer，不删除旧版本或镜像 |

如果 `docker info` 在本机失败，或者 Registry 只是占位地址/没有真实凭据，只能完成 API、模型和自动化测试，不能把该结果写成“真实 Docker 构建和 Registry 推送已通过”。当前受限开发环境尚未完成新的生产 Registry 推送；严格上线前还应按支持矩阵补跑 Python 3.10、3.11、3.12 的真实构建，并按需补做浏览器端构建/发布/回滚全链路。

---

## 1. 生产组件

### 1.1 Compose 服务

`docker-compose.prod.yml` 在 `api`/`worker`/`frontend`/`mysql`/`redis` 之外新增 `environment-builder`：

| 服务 | 职责 | 关键点 |
|---|---|---|
| `environment-builder` | 单副本、单并发的环境构建 Worker | `command: python -m app.worker.environment_builder_worker`；只挂载 `/var/run/docker.sock`，**不挂载学生工作目录**；DB 是任务事实源，Redis list 只负责唤醒 |
| `api` / `worker` | 不执行环境构建 | V2 开启时读取三版本 digest 映射；V2 关闭时使用 `DAI_ENV_BASE_IMAGE` 兼容配置 |

现有 `dai-judge-python:latest` / `dai-kernel-python:latest` 仅保留为未绑定环境版本的存量兼容路径与回滚窗口；新提交与新实验一律使用环境版本 digest。

### 1.2 环境变量（.env.example 已收录）

```text
# V2=false 时使用；V2=true 时由 DAI_ENV_PYTHON_BASE_IMAGES 取代
DAI_ENV_BASE_IMAGE=python:3.12-slim@sha256:<64位hex>
DAI_ENV_BUILD_QUEUE_NAME=environment:build:queue
DAI_ENV_BUILD_TIMEOUT_SECONDS=3600                     # 单次构建超时上限（60~86400）
DAI_ENV_IMAGE_REPOSITORY=dai-env                       # 镜像仓库前缀
DAI_ENV_BUILD_LOG_MAX_BYTES=61440                      # 构建日志 60 KiB 尾部上限
```

**生产校验（`backend/app/config.py`）**：V2 关闭时 `DAI_ENV_BASE_IMAGE` 必须匹配 `<ref>@sha256:[0-9a-f]{64}`；V2 开启时改为强制 `DAI_ENV_PYTHON_BASE_IMAGES` 恰好包含 3.10、3.11、3.12 且每项固定 digest。

### 1.3 构建链路

```text
管理员 seed/API → DB 写入 build job(queued) → Redis rpush 唤醒
environment-builder 消费 → claim(条件更新防抢占) → docker build(临时 tag)
→ 离线 smoke(import + pip check + runner) → 生成 pip hash lock → 推送并回拉 Registry digest
→ 只有远端 digest 可拉取校验后 DB 事务内写 digest + 版本转 available
```

- 构建失败/超时只影响当前版本，不修改旧 available 版本；未修改草稿的重试复用已持久化 lock，修改后由管理 API 创建新版本和新 job（`retry_of_id`）。
- Worker 崩溃后由 lease（60 秒）恢复：超时 → `timed_out`，未超时 → 回 `queued`。
- 构建日志逐行脱敏（URL 凭据 / token / secret / 宿主机绝对路径）并按 60 KiB 截尾入库，仅管理员可见。

---

## 2. 历史环境与旧绑定迁移（Legacy 兼容说明）

> 本节保留旧环境控制面/业务绑定迁移的背景。新部署的 V2 additive migration 顺序和命令以 **0.3 V2 迁移** 为准；不要把本节的旧 revision 当作当前 head。

**旧控制面/业务绑定的背景顺序如下；新库实际命令以 0.3 的分阶段 runbook 为准，不可一次跳过：**

```text
迁移 A（控制面表） → 准备并校验 basic 真实 digest → 迁移 B（业务绑定）
→ V2 additive migration → 启动 API/Worker → 管理员按需创建和发布新 Profile/Version
```

1. **备份**：MySQL 全量、`.env`、现有 Docker 镜像清单（`docker images --format ...` 落盘）。
2. **迁移 A**：`alembic upgrade b4c5d6e7f890`。迁移 A **不触发任何 Docker 构建**。
3. **basic 前置**：生产使用 `DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST` 调用 `scripts/seed-basic-environment-mysql.py`；脚本会拒绝占位 digest。不要用 `seed-environments --enqueue` 绕过前置检查。
4. **迁移 B + V2**：`alembic upgrade head`。迁移 B 会主动检查 `basic` 最新 available 版本的 `image_digest` 非空，**不满足则拒绝升级**——不要绕过该检查。
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
4. 生产不执行 `alembic downgrade`；关闭 V2 开关并回滚应用/Compose 配置即可，数据库和镜像保持可审计状态。
5. 只有一次性、已备份的测试库才允许设置 `DAI_ALLOW_ENVIRONMENT_V2_DOWNGRADE=true`，并按 `20260820_0003 → 20260819_0003` 做验证循环；不要在现有生产库试验。
6. **不删除已生成镜像**；待系统恢复并核对引用后人工处理。

> 生产回滚不依赖降级迁移，不删除控制面表、不删除 Docker 镜像——避免不可恢复地破坏镜像审计数据。

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
| 生产启动被拒 | V2 关闭时检查 `DAI_ENV_BASE_IMAGE`；V2 开启时检查 3.10/3.11/3.12 的 `DAI_ENV_PYTHON_BASE_IMAGES` digest 映射，见 0.1 |
