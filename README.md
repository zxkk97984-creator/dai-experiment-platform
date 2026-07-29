# DAI 实验平台

面向人工智能课程的一站式在线实验平台。支持课程学习、在线编程实验、作业自动判题、考试系统（选择题 + 编程题）和 Notebook 交互式实验。

---

## 快速开始

### 环境要求

- **Docker Desktop**（运行 MySQL、Redis、判题沙箱）
- **Python 3.11+**（后端）
- **Node.js 18+**（前端）

### 1. 克隆项目

```bash
git clone <repo-url>
cd "DAI Experiment Platform"
```

### 2. 启动基础服务（MySQL + Redis）

```bash
docker compose up -d mysql redis
```

### 3. 初始化后端

```bash
cd backend

# 创建虚拟环境
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 配置环境变量
copy .env.example .env

# 数据库迁移
.venv\Scripts\python.exe -m alembic upgrade head

# 创建管理员账号
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator

# 构建判题镜像（仅首次需要）
docker build -t dai-judge-python:latest docker\judge
docker build -t dai-kernel-python:latest docker\kernel
```

### 4. 启动后端服务

需要打开三个终端窗口：

```bash
# 终端 1：后端 API
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：判题 Worker（按需启动）
cd backend
.venv\Scripts\python.exe -m app.worker.judge_worker

# 终端 3：前端开发服务器
cd frontend
npm install
npm run dev
```

### 5. 访问

- 前端页面：<http://localhost:5173>
- Swagger 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/health>

### 6. 默认账号

配置统一密码，登录后按角色进入不同页面。

| 用户名 | 密码 | 角色 | 说明 |
|--------|------|------|------|
| `admin` | `Passw0rd!` | 管理员 | 管理用户、课程和实验模块 |
| `teacher_john` | `Test1234!` | 教师 | 张教授，管理课程与作业 |
| `teacher_li` | `Test1234!` | 教师 | 李老师，管理课程与作业 |
| `student_alice` | `Test1234!` | 学生 | 已选课、已完成部分作业和考试 |
| `student_bob` | `Test1234!` | 学生 | 已选课、部分作业答错 |
| `student_charlie` | `Test1234!` | 学生 | 已选课 |
| `developer_wang` | `Test1234!` | 开发者 | 管理实验模板和模块 |

> 基础种子数据包含 2 门课程（8 个课时含完整教学内容）、3 个作业（7 道编程题含答案）、2 个考试、2 个实验模块。如果没有种子数据，运行：
> ```bash
> cd backend
> .venv\Scripts\python.exe -m app.seed_data
> ```
>
> **注意**：以上为基础演示数据。如需创建包含完整作业/考试/判题/AI 评分的验收数据，请使用下方的「完整验收数据」脚本。

---

---
## 完整验收数据

用于验收课程管理、作业、考试、代码判题和 AI 评分全流程的幂等演示数据脚本。

### 前置条件

- Docker 服务已启动（`docker compose up -d`）
- 后端环境已配置 DeepSeek API Key（环境变量 `DAI_AI_API_KEY`），模型为 `deepseek-v4-flash`
- 后端 API 在 <http://localhost:8080> 可访问
- 不需要把 API Key 放进命令行参数

### 运行

```bat
cd backend
.venv\Scripts\python.exe seed_acceptance_data.py --base-url http://localhost:8080/api/v1
```

### 验收账号

| 角色 | 用户名 | 默认密码 | 用途 |
|------|--------|----------|------|
| 教师 | `teacher` | `Passw0rd!` | 课程、作业、考试和成绩验收 |
| 学生甲 | `accept_student_a` | `Passw0rd!` | 正确/高质量提交 |
| 学生乙 | `accept_student_b` | `Passw0rd!` | 错误或部分正确提交 |
| 管理员 | `admin` | `Passw0rd!` | 仅用于创建学生账号 |

密码可通过环境变量覆盖：`DAI_SEED_ADMIN_PASSWORD`、`DAI_SEED_TEACHER_PASSWORD`、`DAI_SEED_STUDENT_PASSWORD`。

### 创建的课程

| 课程 | 章节 | 课时 | 作业 | 考试 |
|------|------|------|------|------|
| `[验收] Python 算法与工程实践` | 3 章 | 6 课时 | 2 份（6 道编程题） | 1 份（6 道题，含 AI 评分） |
| `[验收] 数据分析与机器学习入门` | 3 章 | 6 课时 | 1 份（3 道编程题） | 1 份（6 道题，含 AI 评分） |

教师管理页 URL（脚本结束后输出课程 ID）：
```text
http://localhost:8080/teacher/courses/<脚本输出的课程ID>/manage
```

### 幂等性

脚本可重复执行，第二次不会重复创建数据。所有资源按精确的 `[验收]` 标题和用户名识别，已存在的课程、章节、课时、作业、题目、考试和提交全部复用。

---

## 判题架构

### 正式提交（异步）

```text
学生提交代码 → API 创建 Submission(status=queued) → 入队 Redis judge:queue
                                                        ↓
                                               Worker brpop 消费
                                                        ↓
                                              Docker sandbox 运行 pytest
                                                        ↓
                                              更新 Submission status/score
                                                        ↓
                                              前端轮询 GET /result 获取结果
```

### 自测（同步）

```text
学生点击自测 → API sample-run → 仅用公开样例构建测试 → Docker sandbox 同步运行
                                                              ↓
                                                    直接返回 output/status/execution_time_ms
                                                    （不创建 Submission，不计次数）
```

### 考试判题

```text
学生交卷 → 选择题立即评分 → 代码题入队 Redis judge:exam:queue
                                    ↓
                           Worker 消费判题（与普通作业共用进程）
                                    ↓
                          全部答案 completed → 生成 ExamGrade
```

### 判题队列可靠性

- **原子抢占**：`claim_job()` 条件 UPDATE `queued→running`，多 Worker 不会重复执行同一任务
- **恢复扫描**：15 秒间隔扫描 `pending`/`running` 超时任务，重新入队为 `queued`
- **最大重试**：达到 `MAX_ATTEMPTS` 后写入 `system_error` 终态，考试答案立即触发 `finalize_if_ready`
- **去重**：相同 `queued` 任务重复推送时更新 `queued_at` 而非创建新记录

### 后台任务（FastAPI lifespan）

| 任务 | 间隔 | 说明 |
|------|------|------|
| 过期考试扫描 | 15 秒 | 自动交卷超时考试 |
| 判题任务恢复 | 15 秒 | `requeue_stale_jobs` 恢复超时 pending/running 任务 |
| Kernel 清理 | 5 分钟 | 销毁 15 分钟无活动的 Kernel 会话 |

### 启动方式

```bash
# 终端 1：后端 API（含 lifespan 后台任务）
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：判题 Worker（消费 judge:queue 和 judge:exam:queue）
cd backend
.venv/Scripts/python.exe -m app.worker.judge_worker

# 终端 3：前端
cd frontend
npm run dev
```

---
## 认证机制

- **Access Token**：JWT，30 分钟过期，存于 Pinia 内存（不写 localStorage）
- **Refresh Token**：JWT，7 天过期，仅存于 HttpOnly + Secure + SameSite=Lax Cookie（`Path=/api/v1/auth`）
- **登录响应**：JSON body 仅返回 `access_token`/`expires_in`/`user`，不返回 `refresh_token`
- **刷新**：`POST /auth/refresh` 优先从 Cookie 读取，备选 JSON body；使用 GETDEL 原子消费旧 token（防并发重放）
- **登出**：`POST /auth/logout` 撤销 refresh token + access token 加入黑名单
- **Origin 校验**：refresh/logout 端点校验 Origin 头，跨域请求返回 403

## 实验提交

```text
学生点击提交 → POST /experiments/records/{id}/submit
                    ↓
              加载 record + 所有权校验
                    ↓
              client_request_id 幂等检查（已存在 → 直接返回）
                    ↓
              SELECT FOR UPDATE 锁定 record 行
                    ↓
              锁内二次幂等 + 计算 attempt_number
                    ↓
              深复制 cells_sources 为不可变快照 → 写入 experiment_submissions
```

- **幂等**：同一 `client_request_id`（UUID v4）重复提交返回已有记录（201 而非 409）
- **并发安全**：行锁 + 冲突 retry（SQLite 兼容）
- **教师评分**：`PATCH /submissions/{id}/review`，评分 0-100，空 review 拒绝（422）
- **提交列表**：教师/管理员可按课程查看，返回学生姓名和入口名称，分页

## Docker Compose 生产部署

```bash
# 环境变量（必填）
export DAI_SECRET_KEY=<至少16字符的唯一密钥>
export DAI_CORS_ORIGINS=https://your-domain.com
export DAI_DB_PASSWORD=<数据库密码>

# 启动全栈
docker compose -f docker-compose.prod.yml up -d

# 验证
curl http://localhost:8080/api/v1/health/ready
# → {"status":"ready","checks":{"mysql":"ok","redis":"ok"}}
```

### DoD 判题配置

Worker 容器通过宿主机 docker.sock 启动 judge 容器。需配置宿主机工作目录：

```yaml
# docker-compose.prod.yml
environment:
  DAI_JUDGE_WORK_DIR: /judge-work              # 容器内路径（文件操作）
  DAI_JUDGE_HOST_WORK_DIR: /opt/dai/judge-work # 宿主机绝对路径（传给 Docker -v）
volumes:
  - ./judge-work:/judge-work  # bind mount，两边路径对应
```

## 技术栈

| 层面 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + CodeMirror 6 + Marked |
| 后端 | FastAPI + SQLAlchemy + Alembic + Pydantic |
| 数据库 | MySQL 8.4 |
| 缓存/队列 | Redis 7.4 |
| 判题沙箱 | Docker + pytest |
| 交互实验 | Docker ipykernel（持久化 Kernel Session） |

---

## 项目结构

```text
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由（auth/users/courses/assignments/judge/exams/experiments/studio）
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务服务
│   │   └── worker/           # 判题 Worker
│   ├── alembic/              # 数据库迁移
│   ├── docker/
│   │   ├── judge/            # 判题镜像
│   │   └── kernel/           # Kernel 镜像
│   ├── lesson_content/       # 课时教学内容（Markdown）
│   └── tests/                # 后端测试
├── frontend/
│   └── src/
│       ├── api/              # Axios API 封装
│       ├── components/       # 公共组件（CodeBlock、AppLayout 等）
│       ├── stores/           # Pinia 状态管理
│       ├── utils/            # 工具函数
│       └── views/            # 页面（按角色分目录）
├── docker-compose.yml        # MySQL + Redis
└── README.md
```

---

## 角色与权限

| 角色 | 首页 | 主要权限 |
|------|------|----------|
| 学生 `student` | 课程列表 | 选课、学习课时、提交作业、参加考试、进入实验 |
| 教师 `teacher` | 课程管理 | 创建课程/作业/考试、管理题目、查看成绩 |
| 管理员 `admin` | 用户管理 | 创建用户、管理全部资源 |
| 开发者 `developer` | 模板管理 | 管理 Notebook 模板和实验模块 |

---

## 常见问题

### `python` 命令打开 Microsoft Store

用 `py -3` 代替 `python`，或者使用虚拟环境中的 `.venv\Scripts\python.exe`。

### 登录失败

确认管理员账号已创建：
```bash
cd backend
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator
```

### 提交代码一直是 `queued`

判题 Worker 没启动，另开终端：
```bash
cd backend
.venv\Scripts\python.exe -m app.worker.judge_worker
```

### 前端跨域失败

默认允许 `localhost:5173` 和 `127.0.0.1:5173`。如果前端端口变了，修改 `backend/.env`：
```env
DAI_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 前端页面打开白屏

1. 确认 `cd frontend && npm install` 已执行
2. 确认后端 API 在 <http://localhost:8000/health> 可访问
3. 打开浏览器控制台查看具体报错

### Docker 未启动

确保 Docker Desktop 在运行，任务栏应有 Docker 图标。Windows 下可能需要以管理员身份运行。
