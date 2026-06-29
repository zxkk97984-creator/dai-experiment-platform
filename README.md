# DAI 实验平台

面向人工智能课程的在线实验平台，支持课程管理、作业提交、Python 函数判题、考试成绩、JupyterLab 实验入口和实验记录。

> 当前重点：后端接口已经实现并验收，`frontend/` 由前端同学继续开发。前端对接请优先看本文档和 Swagger。

## 开发分工

| 模块 | 负责人 | 说明 |
|------|--------|------|
| 后端 | zxk | FastAPI、MySQL、Redis、Docker 判题、Jupyter 入口、Swagger |
| 前端 | wyh | Vue 页面、登录态、课程/作业/考试/实验页面、接口对接 |

## 技术栈

| 层面 | 技术 |
|------|------|
| 前端 | Vue.js |
| 后端 | FastAPI / Python |
| 数据库 | MySQL |
| 缓存与队列 | Redis |
| 判题隔离 | Docker + pytest |
| 交互实验 | 单 JupyterLab iframe 接入 |
| 接口文档 | Swagger UI |

## 项目结构

```text
.
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/              # API 路由
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务服务
│   │   └── worker/           # 判题 Worker
│   ├── alembic/              # 数据库迁移
│   ├── docker/judge/         # 判题镜像
│   └── tests/                # 后端测试
├── frontend/                 # Vue 前端，由 wyh 开发
├── docs/                     # 架构与对接文档
├── docker-compose.yml        # MySQL / Redis / JupyterLab
└── README.md
```

## 前端同学先看这里

后端启动后，打开：

- Swagger：<http://localhost:8000/docs>
- OpenAPI JSON：<http://localhost:8000/openapi.json>
- 健康检查：<http://localhost:8000/health>
- JupyterLab：<http://localhost:8888/lab>

默认管理员账号：

```text
username: admin
password: Passw0rd!
```

前端请求统一 API 前缀：

```text
http://localhost:8000/api/v1
```

推荐前端环境变量：

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

前端项目启动方式由前端实际工程决定。如果使用 Vite，通常是：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\frontend"
npm install
npm run dev
```

后端只提供 API，不负责托管前端静态页面。

后端默认允许这些前端开发地址跨域：

```text
http://localhost:5173
http://127.0.0.1:5173
```

## 后端启动方式

### 1. 首次初始化

Windows 本机的 `python` 命令可能被 Microsoft Store 别名劫持。本项目统一使用 `py -3` 创建虚拟环境，之后固定使用 `backend\.venv\Scripts\python.exe`。

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

启动 MySQL、Redis、JupyterLab：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform"
docker compose up -d mysql redis jupyter
```

执行数据库迁移，并创建或刷新管理员账号：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator
```

构建判题镜像：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
docker build -t dai-judge-python:latest docker\judge
```

### 2. 每次联调启动

启动后端 API：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

需要测试代码提交和判题时，另开一个终端启动 Worker：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -m app.worker.judge_worker
```

如果 Docker 服务没开，先执行：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform"
docker compose up -d mysql redis jupyter
```

## 前端鉴权方式

### 1. 登录

接口：

```http
POST /api/v1/auth/login
```

请求体：

```json
{
  "username": "admin",
  "password": "Passw0rd!"
}
```

响应里会返回：

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "username": "admin",
    "real_name": "Administrator",
    "role": "admin",
    "status": "active"
  }
}
```

### 2. 后续请求带 Token

登录成功后，前端把 `access_token` 放到请求头：

```http
Authorization: Bearer <access_token>
```

示例：

```http
GET /api/v1/auth/me
Authorization: Bearer eyJ...
```

如果在 Swagger 页面里手动测试，先调用 `/api/v1/auth/login` 拿到 `access_token`，再点右上角 `Authorize`，填入：

```text
Bearer <access_token>
```

### 3. 刷新和登出

| 用途 | 接口 | 说明 |
|------|------|------|
| 获取当前用户 | `GET /api/v1/auth/me` | 页面刷新后恢复登录态 |
| 刷新 Token | `POST /api/v1/auth/refresh` | 使用 `refresh_token` 换新 token |
| 登出 | `POST /api/v1/auth/logout` | 需要带 access token，可传 `refresh_token` |

登出后，当前 access token 会进入 Redis 黑名单。

## 角色说明

| 角色 | 值 | 主要权限 |
|------|----|----------|
| 学生 | `student` | 看课程、选课、提交作业、参加考试、打开 Jupyter、保存实验记录 |
| 教师 | `teacher` | 管理自己的课程、章节、课时、作业、题目、考试和成绩 |
| 管理员 | `admin` | 管理用户和全部资源 |
| 开发者 | `developer` | 用于实验模块等开发管理场景 |

没有公开注册接口，账号由管理员通过 `/api/v1/users` 创建。

## 常用接口分组

| 页面/功能 | 接口分组 | 说明 |
|-----------|----------|------|
| 登录页 | `/api/v1/auth` | 登录、刷新 token、登出、当前用户 |
| 用户管理 | `/api/v1/users` | 管理员创建教师/学生账号，修改状态和密码 |
| 课程列表/详情 | `/api/v1/courses` | 课程、章节、课时、选课/退课 |
| 作业列表/详情 | `/api/v1/assignments` | 作业、题目、发布状态 |
| 代码提交/结果 | `/api/v1/judge` | 学生提交代码、查看判题状态和结果 |
| 考试 | `/api/v1/exams` | 创建考试、开始考试、提交考试、查询成绩 |
| 实验模块 | `/api/v1/experiments` | 实验模块和学生实验记录 |
| Jupyter 入口 | `/api/v1/jupyter` | iframe 地址、Notebook 模板、复制模板 |

## 前端页面和接口对应关系

### 登录页

1. 调 `POST /api/v1/auth/login`
2. 保存 `access_token`、`refresh_token` 和 `user`
3. 根据 `user.role` 跳转到学生端、教师端或管理员端首页

### 学生端

| 页面 | 建议接口 |
|------|----------|
| 课程列表 | `GET /api/v1/courses` |
| 选课 | `POST /api/v1/courses/{course_id}/enroll` |
| 课程章节 | `GET /api/v1/courses/{course_id}/chapters` |
| 作业列表 | `GET /api/v1/assignments?course_id={course_id}` |
| 题目列表 | `GET /api/v1/assignments/{assignment_id}/questions` |
| 提交代码 | `POST /api/v1/judge/submissions` |
| 判题结果 | `GET /api/v1/judge/submissions/{submission_id}/result` |
| 考试列表 | `GET /api/v1/exams` |
| 开始考试 | `POST /api/v1/exams/{exam_id}/start` |
| 提交考试 | `POST /api/v1/exams/{exam_id}/submit` |
| Jupyter 入口 | `GET /api/v1/jupyter/entry` |
| 实验记录 | `POST /api/v1/experiments/records` |

### 教师端

| 页面 | 建议接口 |
|------|----------|
| 我的课程 | `GET /api/v1/courses` |
| 创建课程 | `POST /api/v1/courses` |
| 创建章节 | `POST /api/v1/courses/{course_id}/chapters` |
| 创建课时 | `POST /api/v1/chapters/{chapter_id}/lessons` |
| 创建作业 | `POST /api/v1/assignments` |
| 发布作业 | `POST /api/v1/assignments/{assignment_id}/publish` |
| 创建题目 | `POST /api/v1/assignments/{assignment_id}/questions` |
| 创建考试 | `POST /api/v1/exams` |
| 查看成绩 | `GET /api/v1/exams/{exam_id}/grades` |

### 管理员端

| 页面 | 建议接口 |
|------|----------|
| 用户列表 | `GET /api/v1/users` |
| 创建用户 | `POST /api/v1/users` |
| 修改用户 | `PATCH /api/v1/users/{user_id}` |
| 修改密码 | `PATCH /api/v1/users/{user_id}/password` |
| 禁用/启用 | `PATCH /api/v1/users/{user_id}/status` |
| 实验模块 | `POST /api/v1/experiments/modules` |

## 代码提交格式

当前判题模式是 Python 函数测试。前端提交代码到：

```http
POST /api/v1/judge/submissions
```

请求体：

```json
{
  "question_id": 1,
  "code": "def add(a, b):\n    return a + b\n"
}
```

提交成功后返回的初始状态通常是：

```json
{
  "id": 1,
  "question_id": 1,
  "student_id": 2,
  "code": "def add(a, b):\n    return a + b\n",
  "status": "queued",
  "score": null,
  "stdout": null,
  "stderr": null,
  "result_details": null,
  "execution_time_ms": null
}
```

前端可以轮询：

```http
GET /api/v1/judge/submissions/{submission_id}/result
```

判题状态枚举：

| 状态 | 含义 |
|------|------|
| `queued` | 已入队，等待 Worker |
| `running` | 正在判题 |
| `accepted` | 通过 |
| `wrong_answer` | 答案错误 |
| `runtime_error` | 运行错误 |
| `time_limit_exceeded` | 超时 |
| `system_error` | 系统错误 |

## Jupyter iframe 对接

前端不要写死 Jupyter 地址，先调：

```http
GET /api/v1/jupyter/entry
```

响应：

```json
{
  "iframe_url": "http://localhost:8888"
}
```

页面里用这个地址放到 iframe。当前阶段是单 JupyterLab 实例接入，不做 JupyterHub 多用户隔离。

## 统一响应约定

分页接口统一返回：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

错误响应统一返回：

```json
{
  "detail": {
    "code": "FORBIDDEN",
    "message": "没有权限访问该资源",
    "fields": {}
  }
}
```

常见 HTTP 状态码：

| 状态码 | 含义 |
|--------|------|
| `200` | 请求成功 |
| `201` | 创建成功 |
| `204` | 成功，无响应体 |
| `400` | 请求参数或业务状态不合法 |
| `401` | 未登录、token 失效或 token 被登出拉黑 |
| `403` | 已登录但角色权限不足 |
| `404` | 资源不存在 |
| `409` | 资源冲突，例如用户名重复 |
| `422` | 请求体字段格式不符合 Pydantic Schema |

## 前后端联调建议流程

1. 后端启动 Docker：`docker compose up -d mysql redis jupyter`
2. 后端启动 API：`.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
3. 需要判题时启动 Worker：`.venv\Scripts\python.exe -m app.worker.judge_worker`
4. 前端配置 `VITE_API_BASE_URL=http://localhost:8000/api/v1`
5. 前端先完成登录，并确认 `/auth/me` 可以拿到当前用户
6. 再按学生端流程联调：课程列表 -> 选课 -> 作业 -> 提交代码 -> 判题结果 -> Jupyter
7. 最后联调教师/Admin：创建用户、课程、作业、题目、考试、成绩

## 后端测试和验收

运行单元测试：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp-%RANDOM%
```

检查 OpenAPI：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -c "from app.main import app; schema=app.openapi(); print(len(schema['paths']))"
```

已经验收过的核心链路：

- 管理员登录、刷新 token、登出黑名单
- 管理员创建教师和学生账号
- 教师创建课程、章节、课时、作业和判题题目
- 学生查看课程、选课、提交代码、查看判题结果
- Redis 判题队列和 Docker Worker
- 考试开始、提交和成绩查询
- Jupyter 入口和实验记录

## 常见问题

### 1. `系统找不到指定的路径`

通常是因为当前命令行不在项目根目录。请使用绝对路径：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
```

### 2. `python` 命令不可用或打开 Microsoft Store

不要直接用 `python`。首次创建虚拟环境用：

```bat
py -3 -m venv .venv
```

之后都用：

```bat
.venv\Scripts\python.exe
```

### 3. Swagger 能打开，但登录失败

先确认管理员账号已经创建：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -m app.cli create-admin --username admin --password Passw0rd! --real-name Administrator
```

### 4. 代码提交一直是 `queued`

说明 API 已经把任务放进 Redis，但 Worker 没启动。另开终端运行：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform\backend"
.venv\Scripts\python.exe -m app.worker.judge_worker
```

### 5. Jupyter iframe 打不开

确认 Docker 里的 JupyterLab 正常：

```bat
cd /d "C:\Users\zxk\Documents\DAI Experiment Platform"
docker compose up -d jupyter
```

然后访问：

```text
http://localhost:8888/lab
```

### 6. 前端跨域失败

默认只放行：

```text
http://localhost:5173
http://127.0.0.1:5173
```

如果前端端口变了，需要在 `backend/.env` 里调整：

```env
DAI_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## 详细文档

- [架构设计总览](docs/架构设计总览.md)
- [Swagger 接口文档](http://localhost:8000/docs)
