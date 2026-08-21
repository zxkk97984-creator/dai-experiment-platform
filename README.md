# DAI 实验平台

DAI 实验平台面向人工智能、机器学习和深度学习课程，提供课程学习、在线 Python 实验、作业与考试、Docker 隔离判题、AI 辅助评分、Notebook/Studio、环境档位和教师工作台。

当前仓库已标记为 `V0.1`。核心代码、数据库迁移、自动化测试和生产 Compose 已具备；真实部署机上的 Docker daemon、Registry、镜像推送/回拉和生产数据恢复演练仍需按部署环境完成，不能用受限开发沙箱替代。

## 项目定位

平台解决教学过程中“课程内容、在线实验、自动判题、考试评分和教师复核”分散的问题：

```text
课程学习 → 在线实验 / 作业 / 考试 → Docker 判题 → 成绩与反馈 → 教师工作台分析
```

系统有三类业务角色：

- 学生：浏览课程、学习课时、运行 Notebook、提交作业、参加考试和查看成绩；
- 教师：管理课程/课时/作业/考试/实验，查看统一提交中心，进行 AI 复核和成绩管理；
- 管理员：管理用户、教务数据、环境档位、实验模块和全局提交。

## 当前核心功能

- 课程、章节、Markdown/视频课时、课程封面、学习进度和名单 CSV 导入；
- Python 函数题、公开样例自测、隐藏测试、异步 Redis 队列和 Docker 沙箱；
- 限时考试、选择题/代码题、自动交卷、重判、成绩汇总和教师逐题改分；
- 实验模块、不可变 Notebook 模板版本、内置 Notebook Player、Studio 编辑器、导入/导出和资源清单；
- AI 代码评分的测试组、Rubric、`legacy`/`shadow`/`active` 模式、输出校验和教师终审；
- 环境 Profile/Draft/immutable Version、Python/pip/apt 包校验、异步构建、Registry digest 校验、发布和回滚；
- 教师 Dashboard、统一提交中心、全局搜索、通知、成绩统计、班级/学员、设置和环境选择；
- JWT Access Token + HttpOnly Refresh Token、Redis 限流/黑名单、角色和资源级权限。

AI 生产开关默认关闭。开启前必须完成 [`docs/ai-data-governance.md`](docs/ai-data-governance.md) 中的审批门；关闭时不产生外部 AI 调用，人工评分路径仍可用。

## 技术栈

| 层 | 当前实现 |
| --- | --- |
| 前端 | Vue 3.5.13、Vite 6.0.5、Pinia 2.2.6、Vue Router 4.5.0、CodeMirror 6、Marked |
| 前端测试 | Vitest 4.1.10、Vue Test Utils、Playwright 1.55.0、ESLint 10 |
| 后端 | Python 3.12、FastAPI 0.115.6、Uvicorn 0.32.1、SQLAlchemy 2.0.36、Pydantic Settings 2.7.0 |
| 数据库迁移 | Alembic 1.14.0；生产/CI 使用 MySQL 8.0，本地 Compose 使用 MySQL 8.4 |
| 缓存/队列 | Redis 7（本地镜像 7.4-alpine，生产/CI 镜像 7-alpine） |
| 判题与交互实验 | Docker、pytest、ipykernel、jupyter-client |
| 文件存储 | 本地 Storage backend 或 S3-compatible backend（boto3） |
| CI 基线 | Node.js 20、Python 3.12、SQLite/MySQL 双库测试、Docker Compose smoke |

## 系统架构

本地开发时，MySQL 和 Redis 运行在 Docker，FastAPI、Judge Worker、Environment Builder Worker 和 Vite 在宿主机运行。生产时使用 `docker-compose.prod.yml` 将迁移、API、两个 Worker 和 Nginx 前端容器化。

```text
浏览器
  ├─ 本地：Vite :5173 ───────────────┐
  └─ 生产：Nginx :8080 ─ /api ───────┤
                                     ▼
                           FastAPI :8000
                             ├─ MySQL
                             ├─ Redis
                             ├─ Judge Worker → Docker 判题容器
                             ├─ Kernel Manager → Docker Kernel 容器
                             ├─ Environment Builder → Docker / Registry
                             └─ AI-compatible API（显式启用时）
```

详细模块边界、数据流和兼容路径见 [`docs/架构设计总览.md`](docs/架构设计总览.md)。

## 仓库结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI Router
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务、判题、AI、环境、存储和 Studio 服务
│   │   ├── seed_demo/        # 幂等 Demo 数据播种与校验
│   │   └── worker/           # Judge Worker、Environment Builder Worker
│   ├── alembic/versions/     # 数据库迁移
│   ├── docker/judge/         # 判题镜像
│   ├── docker/kernel/        # Notebook Kernel 镜像
│   ├── lesson_content/       # 课程教学内容
│   ├── storage/              # 本地运行/业务文件存储
│   └── tests/automated/      # 后端自动化测试
├── frontend/
│   ├── src/                  # Vue 页面、组件、API、Store 和工具
│   ├── e2e/                  # Playwright 端到端测试
│   └── public/               # 静态资源
├── deploy/                   # Registry Secret 示例
├── docker/                   # 本地兼容 Jupyter 配置
├── docs/                     # 当前架构、运维、安全和设计规范
├── scripts/                  # 启动、关闭、seed、检查和回填脚本
├── docker-compose.yml        # 本地 MySQL/Redis，含 legacy Jupyter profile
├── docker-compose.prod.yml   # 生产全栈编排
├── docker-compose.e2e-local.yml # E2E 本地端口覆盖
└── README.md
```

`docs/archive/` 只保存历史调查、收口报告和已完成计划，不作为当前运行或部署依据。构建产物、依赖目录、测试截图、`.env` 和 `judge-work/` 均不应提交。

## 环境要求

- Docker Engine/Desktop，且当前用户有权访问 Docker daemon；
- Python 3.12（版本基线见 `backend/.python-version`）；
- Node.js 20（CI、Vitest 和 Playwright 基线）；
- Docker Compose v2；
- Linux/macOS 使用 Bash 脚本时还需要 `curl`、`setsid`、`ps`；Windows 可手动启动服务。

## 本地开发

### 1. 安装后端依赖与开发配置

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Windows PowerShell 对应命令：

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`backend/app/config.py` 从当前工作目录的 `.env` 加载配置，因此开发配置应放在 `backend/.env`。至少检查数据库、Redis、密钥和 CORS：

```env
DAI_DATABASE_URL=mysql+pymysql://dai:dai_password@localhost:3306/dai_platform
DAI_REDIS_URL=redis://localhost:6379/0
DAI_SECRET_KEY=replace-with-a-long-random-secret
DAI_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

`backend/.env.example` 还包含判题、Kernel、Storage 和 AI 开发配置。不要把真实 API key 或生产密钥写入 Git。

### 2. 启动基础设施、迁移和管理员

手动模式先启动本地 MySQL/Redis：

```bash
cd ..
docker compose up -d mysql redis

cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m app.cli create-admin \
  --username admin \
  --password 'Test1234!' \
  --real-name Administrator
```

首次需要判题和 Notebook 镜像时构建：

```bash
cd ..
docker build -t dai-judge-python:latest backend/docker/judge
docker build -t dai-kernel-python:latest backend/docker/kernel
```

### 3. 推荐：一键启动完整开发栈

```bash
DAI_DEV_NO_BROWSER=1 ./scripts/dev-up.sh
```

脚本会按顺序执行 MySQL/Redis 健康检查、`alembic upgrade head`、判题镜像构建、API、Judge Worker、Environment Builder Worker 和 Vite 启动，并检查 API ready 与前端 HTTP 状态。

常用变量：

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `DAI_PYTHON` | `backend/.venv/bin/python` | 后端解释器 |
| `DAI_DEV_API_PORT` | `8000` | API 监听端口 |
| `DAI_DEV_RUN_DIR` | `/tmp/dai-dev` | PID 与日志目录 |
| `DAI_DEV_NO_BROWSER` | 未设置 | 设为 `1` 禁止自动打开浏览器 |

关闭开发栈：

```bash
./scripts/dev-down.sh
```

### 4. 手动分别启动

```bash
# 终端 1：API（在 backend 目录）
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：作业/考试/AI 判题 Worker
cd backend
.venv/bin/python -m app.worker.judge_worker

# 终端 3：环境构建 Worker（需要 Docker daemon）
cd backend
.venv/bin/python -m app.worker.environment_builder_worker

# 终端 4：前端
cd frontend
npm install
npm run dev
```

API 端口变化时同步设置前端代理：

```bash
DAI_DEV_API_PORT=8001 ./scripts/dev-up.sh
# 或手动：
VITE_API_PROXY_TARGET=http://localhost:8001 npm run dev
```

访问地址：

- 前端：<http://localhost:5173>
- API Swagger：<http://localhost:8000/docs>
- 存活检查：<http://localhost:8000/api/v1/health/live>
- 就绪检查：<http://localhost:8000/api/v1/health/ready>

### 5. Demo 数据与环境种子

环境档位种子（需要数据库；`--enqueue` 还需要 Redis 和 Environment Builder）：

```bash
cd backend
.venv/bin/python -m app.cli seed-environments
.venv/bin/python -m app.cli seed-environments --enqueue
```

Demo 数据是幂等的；`seed-demo` 默认要求 `basic` 环境已有可用版本：

```bash
cd backend
.venv/bin/python -m app.cli seed-demo
.venv/bin/python -m app.cli seed-demo --reset-demo
```

详细账号、前置条件、故事线和重置边界见 [`docs/demo-data.md`](docs/demo-data.md)。

## 环境变量与端口

### 配置文件

| 文件 | 用途 |
| --- | --- |
| `backend/.env.example` | 宿主机开发 API/Worker 配置 |
| `.env.example` | 生产 Compose 配置示例，复制为根目录 `.env` |
| `deploy/registry-docker-config.example.json` | 不含凭据的 Registry Docker config 示例 |

关键变量按职责分组如下，完整默认值以两个 `.env.example` 和 Compose 文件为准：

| 组 | 变量 |
| --- | --- |
| 基础连接 | `DAI_ENVIRONMENT`、`DAI_DATABASE_URL`、`DAI_REDIS_URL`、`DAI_SECRET_KEY`、`DAI_CORS_ORIGINS` |
| Compose 数据库 | `DAI_DB_USER`、`DAI_DB_PASSWORD`、`DAI_DB_ROOT_PASSWORD` |
| 判题 | `DAI_JUDGE_IMAGE`、`DAI_KERNEL_IMAGE`、`DAI_JUDGE_TIMEOUT_SECONDS`、`DAI_JUDGE_MEMORY_LIMIT_MB`、`DAI_JUDGE_CPU_LIMIT`、`DAI_JUDGE_HOST_WORK_DIR` |
| Storage | `DAI_STORAGE_BACKEND`、`DAI_STORAGE_S3_*`、`DAI_VIDEO_*`、`DAI_COVER_*` |
| 环境 V2 | `DAI_ENVIRONMENT_EDITOR_V2_ENABLED`、`DAI_ENV_BASE_IMAGE`、`DAI_ENV_PYTHON_BASE_IMAGES`、`DAI_ENV_REGISTRY_REPOSITORY`、`DAI_ENV_REGISTRY_DOCKER_CONFIG_FILE` 及构建资源限制变量 |
| AI | `DAI_AI_ENABLED`、`DAI_AI_BASE_URL`、`DAI_AI_API_KEY`、`DAI_AI_MODEL`、超时/重试/队列变量 |

### 端口与服务

| 场景 | 服务 | 默认端口 |
| --- | --- | --- |
| 本地 Compose | MySQL | `127.0.0.1:3306` |
| 本地 Compose | Redis | `127.0.0.1:6379` |
| 本地 Vite | 前端 | `127.0.0.1:5173` |
| 本地 API | FastAPI | `0.0.0.0:8000`，可由 `DAI_DEV_API_PORT` 改变 |
| legacy profile | Jupyter | `127.0.0.1:8888`，默认不启动 |
| 生产 Compose | Nginx 前端 | `${FRONTEND_PORT:-8080}:80` |
| E2E 覆盖 | MySQL / Redis | `3309:3306` / `6380:6379` |

生产 Compose 不发布 MySQL、Redis 或 API 的宿主机端口，应用通过内部网络访问它们。

## Docker Compose 生产部署

生产部署必须在真实部署机执行，且部署机用户能够访问 Docker daemon。先复制配置并替换所有占位值：

```bash
cp .env.example .env
mkdir -p /opt/dai/judge-work
# 编辑 .env：密钥、CORS、数据库密码、判题目录、digest 和 Registry 配置
docker compose -f docker-compose.prod.yml config -q
```

至少需要确认：

- `DAI_SECRET_KEY` 是唯一的生产密钥；
- `DAI_CORS_ORIGINS` 是实际前端来源，不能是 `*` 或 localhost；
- `DAI_DB_USER`、`DAI_DB_PASSWORD`、`DAI_DB_ROOT_PASSWORD` 已替换；
- `DAI_JUDGE_HOST_WORK_DIR` 是部署机绝对路径；
- `DAI_ENV_BASE_IMAGE` 带真实 `@sha256:` digest；
- `DAI_ENV_REGISTRY_DOCKER_CONFIG_FILE` 指向部署机 root-owned、只读的真实 Docker config；
- 生产 AI 默认保持 `DAI_AI_ENABLED=false`，启用前完成数据治理审批。

全新库或缺少 basic 可用环境版本时，必须按 [`docs/environment-profiles.md`](docs/environment-profiles.md) 的分阶段迁移顺序执行：

```bash
docker compose -f docker-compose.prod.yml up -d --wait mysql redis
docker compose -f docker-compose.prod.yml run --rm migrate alembic upgrade b4c5d6e7f890

# 生产必须提供真实 basic digest；不要使用占位值
docker compose -f docker-compose.prod.yml run --rm \
  -e DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST=sha256:<64位hex> \
  -e DAI_BASIC_ENVIRONMENT_BASE_IMAGE=python:3.12-slim@sha256:<64位hex> \
  migrate python /scripts/seed-basic-environment-mysql.py

docker compose -f docker-compose.prod.yml run --rm migrate alembic upgrade head
docker compose -f docker-compose.prod.yml up -d --wait
docker compose -f docker-compose.prod.yml ps
```

检查健康状态和环境构建日志：

```bash
curl -fsS http://localhost:8080/api/v1/health/live
curl -fsS http://localhost:8080/api/v1/health/ready
docker compose -f docker-compose.prod.yml logs --tail=200 environment-builder
```

环境 V2 的真实构建必须完成 Docker build、smoke、Registry push、按 digest pull-back、数据库 `available` 和教师旧绑定回归；仅完成 API 测试不等于生产验收。

## 数据库迁移、初始化与回滚

开发库：

```bash
cd backend
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
.venv/bin/python -m alembic heads
```

生产迁移由 Compose 的 `migrate` 一次性服务执行。生产默认只做 forward migration，不用 `downgrade` 代替业务回滚；备份、恢复和 V2 回滚约束见：

- [`docs/environment-profiles.md`](docs/environment-profiles.md)
- [`docs/backup-restore.md`](docs/backup-restore.md)

历史提交测试计数需要回填时：

```bash
cd backend
.venv/bin/python ../scripts/backfill_test_counts.py --dry-run
.venv/bin/python ../scripts/backfill_test_counts.py
```

## 测试、Lint 与构建

### 后端

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/ruff check app/
.venv/bin/python -m alembic check  # 需要可连接的数据库
```

CI 会分别运行 SQLite 和 MySQL 测试，并跳过需要真实 Docker/Kernel 的历史实验测试文件；完整 CI 门禁见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)。

### 前端

```bash
cd frontend
npm ci
npm run lint
npm test
npm run build

# 等 API、前端和数据库由外部提供后运行
npm run e2e
```

也可以使用：

```bash
npm run check  # lint + unit test + production build
```

### 安全与 Compose 检查

```bash
# 根目录执行
python3 scripts/check_sca.py
docker compose -f docker-compose.prod.yml config -q
./scripts/verify_host_isolation.sh

# 生产 Compose 启动后
BASE_URL=http://localhost:8080 ./scripts/check_security_headers.sh
```

`check_sca.py` 需要当前 Python 环境已安装 `pip-audit`；生产安全头检查需要运行中的 Nginx 前端。

## API 与兼容路径注意事项

- API 前缀统一为 `/api/v1`；Swagger 在 `/docs`，live/ready 在 `/api/v1/health/live` 和 `/api/v1/health/ready`。
- `/api/v1/notebooks` 已废弃，仅为旧客户端进程内转发，响应带 `Deprecation: true` 和 `Sunset: 2026-09-01`；新代码使用 `/api/v1/experiments` 和 `/api/v1/studio`。
- `/api/v1/jupyter` 与 Compose 的 `legacy-jupyter` profile 保留兼容能力，但默认关闭；新流程使用内置 Notebook Player。
- 环境已绑定版本运行时使用不可变 digest；`latest` 只允许出现在未绑定存量兼容路径或本地开发配置。
- `backend/storage/`、命名 Docker volume 和 `judge-work/` 含运行/业务数据，清理缓存时不要递归删除。
- 生产 Docker socket 具有主机级风险，不要用 `chmod 666 /var/run/docker.sock`，也不要开放 2375/2376。

## 当前状态与后续收尾

当前 V0.1 的代码和自动化门禁已完成，仍需部署环境配合的事项：

1. 在真实部署机验证 Docker daemon、socket 权限、Registry Secret 和环境 V2 真实构建/推送/回拉；
2. 完成生产数据库、Redis、Storage 的备份恢复演练，并补齐责任人和外部签字记录；
3. 逐页移除前端 `teacher-management.css` 迁移桥接层，计划见 [`docs/ui-v2-migration-plan.md`](docs/ui-v2-migration-plan.md)；
4. 在 Sunset 日期前移除新增代码对 `/api/v1/notebooks` 的依赖，之后再评估删除兼容 Router 和 legacy Jupyter 配置。

## 当前文档地图

- [`docs/架构设计总览.md`](docs/架构设计总览.md)：当前系统怎么设计；
- [`docs/environment-profiles.md`](docs/environment-profiles.md)：环境 V2、迁移、Registry 和运维；
- [`docs/demo-data.md`](docs/demo-data.md)：Demo 数据播种与验证；
- [`docs/backup-restore.md`](docs/backup-restore.md)：备份恢复上线边界；
- [`docs/ai-data-governance.md`](docs/ai-data-governance.md)：AI 数据治理上线门；
- [`docs/dai-design-system-v2.md`](docs/dai-design-system-v2.md)：前端设计系统；
- [`docs/security/`](docs/security/)：Docker socket、TLS、安全依赖和安全头；
- [`DAI智能代码评分方案_V1.md`](DAI智能代码评分方案_V1.md)：AI 代码评分公式和 Rubric 设计方案；
- [`docs/archive/`](docs/archive/)：历史报告和已完成计划，仅供追溯。
