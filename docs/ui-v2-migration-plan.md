# 前端设计系统 V2 迁移清单

> 状态：进行中（2026-08-21）。本文只记录仍然影响维护工作的剩余迁移项；已经完成的页面改造不再以历史计划形式重复描述。

## 当前事实

- Vue 入口为 `frontend/src/main.js`，全局样式入口为 `frontend/src/style.css`。
- `frontend/src/style.css` 已导入 `frontend/src/styles/dai-ds-v2.css`，V2 token 是当前代码库内唯一的设计系统样式源。
- `frontend/src/styles/teacher-management.css` 仍作为迁移桥接层被 `main.js` 导入。
- 部分教师作业、考试、实验列表页仍使用 `teacher-management-page`、`filter-bar`、`data-panel` 等桥接类；这些类不能在没有页面级替换和回归验证前删除。
- 原始静态设计稿已从仓库移除；设计规范和真实 Vue 组件是当前参考对象。

## 已完成范围

- App Shell、侧栏、顶栏、通用面板、状态徽标、进度条和确认弹窗已接入 V2 token。
- 学生首页、教师工作台、课程管理、提交中心、AI 评分列表/详情、实验和环境管理等主要路径已使用 V2 视觉契约。
- 旧 Developer 页面和入口已从当前前端路由与视图中移除。

## 仍需保留的后续工作

1. 将仍使用 `teacher-management-page` 桥接类的教师列表页逐页迁移到 `.table-wrap`、`.toolbar`、`.ds-table`、`.pagination` 等 V2 原语。
2. 每迁移一页，删除该页不再使用的局部兼容样式，并运行前端 lint、单元测试和生产构建。
3. 当 `rg -n "teacher-management-page|teacher-management" frontend/src` 只剩历史说明或无效引用时，删除 `frontend/src/styles/teacher-management.css` 及 `style.css` 中对应的旧 token 别名。
4. 迁移完成后补一次主要角色路由的 Playwright E2E 与响应式检查。

## 验证命令

```bash
cd frontend
npm run lint
npm test
npm run build
```

端到端测试需要外部提供 API、前端和数据库环境：

```bash
npm run e2e
```

设计系统的 token、组件语义、响应式断点和可访问性约束见 [`dai-design-system-v2.md`](dai-design-system-v2.md)。
