# 人工智能基础实验平台开发

在线 AI 教学实验平台，面向机器学习/深度学习教学场景。支持在线编程判题、JupyterLab 交互式实验、课程管理与作业考试。

## 技术栈

| 层面 | 技术 |
|------|------|
| 前端 | Vue.js |
| 后端 | FastAPI（Python） |
| 数据库 | MySQL + Redis |
| 判题隔离 | Docker |
| 交互实验 | JupyterLab（嵌入式） |

## 项目结构

```
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # API 路由
│   │   ├── models/   # 数据模型
│   │   ├── schemas/  # Pydantic Schema
│   │   ├── services/ # 业务逻辑
│   │   └── worker/   # 判题 Worker
│   └── docker/       # Docker 判题镜像
├── frontend/         # Vue.js 前端
└── docs/             # 文档
```

## 快速开始

```bash
# 后端（zxk）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端（wyh）
cd frontend
npm install
npm run dev
```

## 详细文档

- [架构设计总览](docs/架构设计总览.md)
