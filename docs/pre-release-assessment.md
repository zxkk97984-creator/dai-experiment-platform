# 上线前最终评估

评估基线：`e1e804bf65ec6d9d0e841541edca9638e313469e`（2026-08-22）  
评估范围：当前实际源码、数据库模型与迁移、前后端接口、Docker/环境配置、CI、测试及现行文档。除本报告外未修改代码、配置或数据。

## 摘要

项目的主要业务功能不是 Demo：课程、教务、作业、考试、判题、Notebook/实验、环境版本、文件存储、通知和 AI 评分均有真实前后端、数据库与权限控制。隔离副本中的后端全量测试、前端检查和生产构建均通过。

但当前仍缺少正式发布必需的生产证据，并且现有 Docker smoke 流水线存在确定性失败、全新数据库不能按默认 Compose 命令直接启动。因此，本次结论是 **NO-GO**。这不否定代码完成度，而是表示“现在直接上线”不满足可恢复、可验证、可运维的发布条件。

## 1. 当前项目实际架构概览

| 层次 | 当前实际实现 |
| --- | --- |
| Web 前端 | Vue 3 + Vite + Pinia + Vue Router + Axios，106 个 Vue 文件；学生、教师、管理员三类工作区；CodeMirror、Notebook Player、Markdown + DOMPurify。生产由 Nginx 提供 SPA 并反向代理 `/api`。 |
| API 后端 | Python 3.12 + FastAPI + SQLAlchemy 2 + Pydantic Settings，共 23 个 API Router；同步业务接口、定时考试收卷、健康检查、日志和 Redis 小时窗口指标。 |
| 数据库 | MySQL，48 个 ORM 表；39 个 Alembic 迁移文件、单一 head `20260820_0003`。覆盖账号、教务班级、课程/课时、作业、考试、提交/成绩、实验、环境版本、媒体对象、通知等。 |
| 异步与运行时 | Redis 用于 Refresh Token、令牌黑名单、登录限流、判题/AI/环境构建队列和短期指标；Judge Worker 串行消费普通判题、考试判题和 AI 队列。 |
| 隔离执行 | Worker/API 通过 Docker socket 创建判题或 Kernel 容器；学生容器已有非 root、只读文件系统、`network none`、cap-drop、CPU/内存/PID 限制。环境 V2 以不可变版本和镜像 digest 绑定业务数据。 |
| 文件存储 | 本地持久卷或 S3-compatible 后端；课程封面、视频、Studio 资源有类型/大小/路径校验、对象登记、隔离区和回收机制；视频通过短期签名 URL 播放。 |
| 生产编排 | `docker-compose.prod.yml` 编排 MySQL、Redis、一次性 migrate、API、Judge Worker、Environment Builder、Frontend；持久化 MySQL、Redis AOF、Studio、视频、封面和日志。TLS 预期由仓库外的学校网关/LB/Ingress 终止。 |

核心业务链路总体完整：管理员维护用户/教务/环境，教师管理课程、内容、名单、作业、考试和实验，学生学习、提交、考试与运行 Notebook，教师复核成绩。AI 默认关闭，关闭时仍保留确定性判题和人工评分。

## 2. 当前完成度评估

以下百分比是基于代码闭环、验证证据和上线条件的工程判断，不是代码覆盖率：

| 维度 | 评估 | 说明 |
| --- | --- | --- |
| 业务功能实现 | **85%–90%** | 主流程完整；主要缺口是大数据量分页、少量兼容假实现和部分未完成管理能力。 |
| 前后端/API/数据库一致性 | **约 85%** | 主接口、模型、迁移和权限测试较完整；发现代理协议、名单搜索、监控队列等真实契约问题。 |
| 自动化测试与构建 | **约 80%** | 单元/接口测试量大且本轮通过；但 Docker smoke 当前配置会失败，生产 MySQL/真实 Docker/Registry/E2E 本轮无可用的最终发布证据。 |
| 生产部署准备度 | **55%–65%** | Compose 和 fail-fast 配置已有基础，但备份恢复、TLS、证书、宿主机隔离、Registry、容量与告警仍未验收。 |
| 文档一致性 | **约 85%** | README 与专项文档大多诚实描述现状；本地空库迁移说明和默认启动方式与真实迁移前置条件不一致。 |

分模块判断：

- 账号、RBAC、课程、作业、考试、成绩、媒体存储：**基本可用**，适合继续验收。
- 判题、实验与 Notebook Player：**代码已实现**，但正式可用性依赖真实 Docker 主机、镜像和容量验收。
- 环境编辑器 V2：**控制面已实现，生产运行条件未完成**；当前文档明确承认尚未完成真实 Registry push/pull 及 Python 3.10/3.11/3.12 构建验证。
- AI 评分：**实现存在但不具备启用条件**；数据治理尚未批准，生产应继续保持 `DAI_AI_ENABLED=false`。
- 运维发布：**未完成**；这是当前总体完成度的主要短板。

## 3. 已经达到上线要求的部分

- 生产配置会拒绝默认 JWT 密钥、开发 CORS、默认业务数据库密码和非 digest 环境基础镜像；Refresh Token 使用 HttpOnly/Secure/SameSite Cookie，并有轮换、会话版本撤销和 Redis 黑名单。
- RBAC、资源归属与学生可见范围在 API 层实施；没有发现仅靠前端隐藏按钮进行授权的核心接口。
- 数据模型具有较完整的唯一约束、外键、状态字段、幂等/租约机制；迁移链为单 head，CI 设计包含 MySQL 迁移和 `alembic check`。
- 判题/Kernel 容器的学生代码隔离参数较完整，业务任务以数据库为事实源，Redis 丢失后可恢复队列任务。
- 上传路径具备大小、扩展名、Magic Bytes、路径穿越和原子落盘/对象状态控制；Markdown 渲染后由 DOMPurify 清洗。
- AI 默认关闭；启用路径有超时、重试、输出结构校验、失败转人工复核和治理文档，不会因 AI 不可用而阻断全部评分能力。
- 本轮隔离验证结果：
  - 后端：`1293 passed, 3 skipped`，Ruff 高信号检查通过；
  - 前端：95 个测试文件、`890 passed`，ESLint 与 Vite 生产构建通过；
  - 前端生产依赖 `npm audit --omit=dev --audit-level=high` 为 0；
  - `docker compose -f docker-compose.prod.yml config -q` 在完整必填变量下通过；
  - Alembic 只有一个 head；高信号密钥扫描未发现已提交密钥。
- CI 已覆盖 SQLite、MySQL、前端测试/构建、Playwright、Compose smoke 和安全头的设计框架；问题是其中一个发布 job 当前无法按现配置成功执行，见 P0。

## 4. 仍存在的问题和风险

### 发布与数据安全

- `docs/backup-restore.md` 的真实主机/卷清单、备份介质与加密、RPO/RTO、隔离恢复演练和发布签字全部仍为“待确认/待执行”。迁移文档又要求发布前必须先有可读备份；当前没有可恢复性证据。
- 全新数据库不能直接 `alembic upgrade head`。必须先升级到 `b4c5d6e7f890`、准备经过验证的 basic 镜像 digest、seed 后再升级 head；默认 `migrate` 服务和 `scripts/dev-up.sh` 仍直接执行 head，首发启动会失败。
- `.github/workflows/ci.yml` 的 `docker-smoke` job 设置了 `DAI_ENVIRONMENT=production`，却没有传 `DAI_BASIC_ENVIRONMENT_IMAGE_DIGEST`；`scripts/seed-basic-environment-mysql.py` 会在连接数据库前确定性退出。本轮已静态和命令级复现，故不能把当前流水线视为全绿。

### 基础设施与安全边界

- `docs/security/tls-topology.md` 仍未确认真实 TLS 终止点、HSTS、证书签发/续期/到期监控。内层 Nginx 的 CSP 仍为 Report-Only。
- API、Worker、Environment Builder 挂载 Docker socket；这是等价于宿主机高权限的边界。专用主机、Docker TCP 端口未暴露和风险接受仍未由部署方签字。
- 应用及基础服务镜像使用可变 tag（如 `python:3.12-slim`、`node:20-alpine`、`nginx:alpine`、`mysql:8.0`），后端生产镜像还安装 pytest、moto、fakeredis、ruff、radon 等非运行依赖；构建不可完全复现，镜像攻击面偏大。
- Python SCA 当前仍报告 4 个包共 17 项已知漏洞，均以临时接受方式放行至 2026-09-30。接受理由基本合理，但必须在到期前升级或重新评审。

### 功能、稳定性与性能

- 多个核心页面只请求前 100 条再在浏览器内筛选/分页：考试管理、教学班名单、课程名单管理、教务管理等。超过 100 个考试/班级/学生后会静默漏数据，人数、搜索和移除操作可能错误。
- 教师/管理员界面声明可按学号搜索学生，但 `backend/app/api/users.py:list_students` 只匹配用户名和姓名，没有匹配 `student_no`。
- `lesson_videos.py` 使用 `request.base_url` 生成绝对签名播放地址；内层 Nginx 总是写 `X-Forwarded-Proto $scheme`。在“外层 HTTPS、内层 HTTP”的文档拓扑中可能生成 `http://` URL，造成 HTTPS 页面混合内容或签名能力 URL 降级。
- 登录限流在可信代理模式取 X-Forwarded-For 最右一跳。外层 LB 再经过内层 Nginx 时，最右值很可能是 LB 地址，使全部用户共享同一个 30 次失败限流桶，存在集体无法登录风险。
- `/api/v1/health/ready` 的 SQLAlchemy Session 不是 `finally` 关闭，Redis 客户端也未关闭；`get_redis_client` 每个请求创建新客户端。故障或高并发探测下可能放大连接/文件描述符压力。
- `_expiry_scanner` 和 Kernel 清理任务在 async 事件循环里直接执行同步数据库/Docker 工作；过期考试批量增大或 Docker 响应慢时会阻塞 API 事件循环。
- 考试成绩接口一次性返回全体受众，无分页，并通过默认 lazy relationship 补学生，存在 N+1 查询和大响应风险。
- Judge Worker 单实例串行消费普通判题、考试和 AI 三类队列；若启用最长 60–180 秒并带重试的 AI 调用，会阻塞确定性判题。当前容量文档也明确承认没有 Kernel 准入、资源预算和 300/500 用户阶梯压测，不能承诺几百人规模。
- `/api/v1/metrics` 的 `judge_queue_depth` 实际读取 `ai_queue_name` 而非 `judge_queue_name`，会隐藏普通判题积压；当前也没有主动告警、前端错误上报或成熟的时序监控。

### 未完成、Mock、废弃与文档

- 默认关闭的 legacy Jupyter API 含两个硬编码模板，`copy_template` 只返回目标路径并没有复制文件；它只能视为兼容占位，不是真实可用功能。
- `/api/v1/notebooks` 是进程内废弃转发，Sunset 为 2026-09-01；前端未发现新依赖，但到期清理尚未完成。
- 章节排序接口明确标注“尚未实现”；前端 V2 样式迁移仍保留桥接层；`examsAPI.delete()` 没有对应后端考试删除路由且未被 UI 使用，属于死接口代码。
- README 的生产两阶段迁移说明基本准确，但本地安装与 `dev-up.sh` 仍写成直接 `upgrade head`，与全新库真实前置条件矛盾。工作区还有一份未纳入 Git 的手动测试指南，不应作为发布包的正式文档依据。
- 后端测试通过但产生 16,650 条 warning，主要是 Python 3.12/依赖弃用和测试数据适配器警告；信号噪声过高。前端构建还有一次静态/动态重复导入导致无法拆包的 warning，当前无代码覆盖率门槛。

## 5. 按 P0 / P1 / P2 分类的问题清单

| 级别 | 问题 | 上线判定 |
| --- | --- | --- |
| P0 | 没有真实备份成功证据、RPO/RTO 和隔离恢复演练 | 阻断上线；迁移前必须完成并签字。 |
| P0 | 当前 Docker smoke CI 缺少生产 basic digest，会确定性失败 | 阻断上线；必须修正并取得当前提交的全绿流水线证据。 |
| P0 | 全新库/首发不能按默认 Compose `migrate -> upgrade head` 启动，发布依赖手工两阶段迁移 | 阻断首发；需固化发布步骤、演练失败回滚并证明可重复。 |
| P0 | TLS/HSTS/证书监控、Docker 专用宿主机/daemon 隔离与风险接受均未完成真实环境验收 | 阻断公网或正式生产发布。 |
| P0 | 真实 Registry push/pull、Python 3.10/3.11/3.12 环境构建和目标规模压测未完成；现架构不能承诺 300–500 人 | 目标是正式多人教学时阻断；只能在明确限制人数的小范围试点后再放行。 |
| P0（条件） | AI 数据治理未审批 | 生产必须保持 AI 关闭；如计划启用 AI，则直接阻断。 |
| P1 | 核心名单/考试页面 100 条截断，学号搜索不符合 UI 契约 | 会造成真实数据漏显和名单操作错误。 |
| P1 | 外层 TLS + 内层 Nginx 下的协议/IP 代理链处理不正确 | 可能造成视频不可播放及共享限流桶导致集体登录失败。 |
| P1 | readiness/Redis 客户端生命周期、async 定时任务同步阻塞 | 故障和高负载时可能放大连接耗尽与 API 卡顿。 |
| P1 | 成绩接口无分页且可能 N+1；单 Worker 混跑 AI 与确定性判题 | 班级变大或 AI 变慢时延迟不可控。 |
| P1 | 监控读错判题队列，且无主动告警/前端错误采集 | 积压和故障可能直到用户投诉才被发现。 |
| P1 | 生产镜像/依赖未完全锁定、运行镜像包含开发依赖、17 项临时接受漏洞 | 供应链可复现性和攻击面不满足长期生产标准。 |
| P2 | legacy Jupyter 硬编码/假复制、notebooks Sunset、章节排序未实现、考试删除死客户端接口 | 不阻断核心路径，但必须明确下线或完成，不能宣传为可用能力。 |
| P2 | README 本地迁移说明、未跟踪手动测试文档、UI V2 桥接层 | 增加部署和维护误判。 |
| P2 | 16,650 条测试 warning、无覆盖率门槛、Vite 拆包 warning、生产公开 OpenAPI/Swagger | 影响长期维护、信号质量和最小暴露面。 |

## 6. 上线前还需要完成的事项

按以下顺序执行；前一阶段未通过时不要进入下一阶段：

1. **修复发布门禁**：让 Docker smoke 使用合法且可拉取的 basic digest；在当前提交上跑通 SQLite、MySQL、前端、E2E、Docker smoke、SCA 和 secret scan 全部 job。
2. **固化首发迁移**：将“两阶段 Alembic + real basic digest”形成唯一发布命令/Runbook；分别演练空库、现有数据升级、中途失败、应用回滚，记录耗时和校验结果。
3. **建立可恢复性**：确认真实卷和对象存储清单，完成加密备份、保留周期、RPO/RTO、异机/隔离恢复演练及发布签字。
4. **完成生产安全边界验收**：确认 TLS 终止、HSTS、证书自动续期/告警；验证 Docker daemon 无 TCP 暴露、宿主机专用、系统补丁与最小权限，并签署 socket 剩余风险。
5. **完成真实运行时验收**：在生产同型主机和 Registry 上构建、推送、按 digest 回拉 3.10/3.11/3.12；验证判题、考试、Notebook、视频 Range、S3（如使用）和重启后的持久化。
6. **修复 P1 功能与代理问题**：实现服务端分页/完整名单加载和学号搜索；正确保留外部协议并定义可信代理链；补相应回归测试。
7. **完成容量与稳定性验证**：实现 Kernel 准入/资源预算，拆分 AI 与确定性判题 Worker，压测目标用户规模；修复连接生命周期、事件循环阻塞、成绩接口 N+1/大响应。
8. **建立可观测性与值班机制**：修正队列指标，接入持久时序监控、5xx/队列/资源/证书/磁盘告警和前端错误采集，明确告警责任人和故障响应流程。
9. **收敛供应链与遗留项**：拆分生产/开发依赖，固定基础镜像 digest，处理 2026-09-30 前的 SCA 接受项；删除或明确禁用 legacy Jupyter/notebooks，更新 README 和正式验收文档。
10. **发布决策复核**：P0 全部关闭、P1 有负责人/期限且关键 P1 已修复后，先进行受控小流量试点，再重新作 GO/NO-GO 评审。

## 7. 最终结论：NO-GO

当前代码已经达到“功能较完整、可继续做生产验收”的阶段，但没有达到“可直接正式上线”的阶段。阻断项包括：发布流水线确定性失败、首发迁移无法按默认流程执行、备份恢复无真实证据，以及 TLS、Docker 宿主机、Registry 和容量未完成生产验收。

只有在所有 P0 关闭、关键 P1 修复并取得目标环境的完整发布证据后，结论才可提升为 **CONDITIONAL GO**；经过受控试点和回滚/恢复复核后，才适合评为 **GO**。

**如果现在直接上线，这个项目最大的风险是：在备份恢复尚未验证的情况下执行必须分阶段的数据库与环境迁移，一旦失败，可能同时造成服务无法启动和业务数据无法可靠恢复。**
