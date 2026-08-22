# 上线前修复计划

依据：[`pre-release-assessment.md`](pre-release-assessment.md)  
目标：关闭仓库内可修复的 P0/P1，形成可重复验证的发布流程；对于只能在真实生产环境完成的事项，提供验收入口和证据模板，但不得伪造完成状态。  
执行方式：OpenCode 按阶段实施，Codex 独立审查与验收。每一阶段必须保持可构建、可测试、可回滚；未经验收不得进入下一阶段。

## 1. 范围与完成定义

### 本轮必须实现

- 修复当前 Docker smoke CI 的确定性失败。
- 统一全新数据库的两阶段迁移流程，修复 `dev-up.sh`、Compose 默认行为和 README 之间的矛盾。
- 修复超过 100 条时名单、教务和考试页面静默漏数，以及学号搜索失效。
- 修复视频签名地址在外层 HTTPS/内层 HTTP 拓扑下可能返回 HTTP 的问题。
- 修复登录限流对代理链的错误 IP 归属，默认配置必须 fail-safe。
- 修复 readiness/Redis 连接生命周期、异步定时任务阻塞事件循环、错误队列指标。
- 为考试成绩列表增加可扩展的分页/查询策略，消除逐提交 lazy-load 风险。
- 将 AI 慢调用与确定性判题的消费能力解耦，AI 保持默认关闭。
- 收敛生产镜像依赖、可变配置和遗留兼容面中仓库内可处理的部分。
- 为以上每个行为修复增加先失败后通过的回归测试，并更新真实文档。

### 本轮不能伪造完成

以下事项必须保留为发布方外部门禁：真实备份与隔离恢复演练、RPO/RTO 签字、生产 TLS/HSTS/证书续期、Docker 专用宿主机与 daemon 配置验收、真实 Registry push/pull、Python 3.10/3.11/3.12 镜像构建、目标用户规模压测、漏洞风险接受签字、AI 数据治理审批。

### Definition of Done

- 所有仓库内 P0 关闭，P1 要么修复，要么有明确且不影响首发的延期理由。
- 所有 bug 修复都有能在旧代码上失败的回归测试。
- 后端全量 pytest、Ruff、前端 lint/test/build、依赖审计和 Compose 配置检查通过。
- Docker smoke 与 E2E 使用明确的 disposable/production 语义，不把占位 digest 伪装成生产镜像证据。
- `git diff` 不包含 `.env`、密钥、构建产物、用户已有的未跟踪文件或无关重构。
- `docs/pre-release-assessment.md` 中被关闭的问题有对应代码、测试或真实外部证据；没有证据的项目仍保持未完成。

## 2. 实施原则

1. 采用 RED → GREEN → REFACTOR：先增加复现测试，再写最小修复。
2. 每次只完成一个可验证的纵向切片；每 2–3 个任务设置一次全量检查点。
3. 不新增不必要依赖，不批量格式化，不顺手重构无关模块。
4. 不读取、覆盖或提交真实 `.env`、Registry Secret、数据库数据和用户已有的未跟踪文档。
5. 不使用假 digest、假恢复记录或假压测结果满足生产门禁；CI disposable smoke 必须在名称和注释中明确其性质。
6. 行为或 API 契约发生变化时，同步修改前端消费者、测试和正式文档。

## 3. 分阶段任务

### Phase 0：基线与发布安全护栏

#### Task 0.1：锁定修复基线

**内容**：记录当前分支、工作区已有未跟踪文件和基线测试结果；后续只审查本计划涉及的文件。

**验收标准**：

- [ ] 明确保留 `docs/手动测试数据与AI判题指南.md`，不得修改或提交。
- [ ] 明确保留本轮评估与修复计划文档。
- [ ] 不执行 destructive Git 命令，不提交真实凭据。

**验证**：`git status --short`、`git diff --check`。

### Phase 1：关闭发布流水线与迁移 P0

#### Task 1.1：修复 Docker smoke 的 basic digest 前置

**内容**：让 disposable Docker smoke 明确使用可验证的 CI bootstrap 语义；生产 seed 仍必须要求真实 digest。不得仅在 production job 中塞入 `111...` 等假 digest 并宣称生产通过。

**验收标准**：

- [ ] CI workflow 测试可证明 production seed 缺少真实 digest 时仍 fail-closed。
- [ ] Docker smoke 可以在 disposable 环境完成迁移和健康检查，且名称/注释不声称完成 Registry 生产验收。
- [ ] E2E 与 smoke 复用同一条受支持的 bootstrap 入口，避免两套迁移命令继续漂移。

**验证**：相关 Python/脚本测试、workflow 静态测试、`docker compose ... config -q`；Docker 可用时跑 smoke job 等价命令。

**依赖**：Task 0.1。  
**预计范围**：M，CI + 1 个脚本 + 测试。

#### Task 1.2：统一全新库与已有库迁移入口

**内容**：提供一个幂等 bootstrap/migrate 入口，识别当前 revision 与 basic 前置；非生产空库可以显式生成 disposable seed，生产必须传真实 basic image/base digest。让 `dev-up.sh`、Compose/CI 和 README 调用或引用同一流程。

**验收标准**：

- [ ] 全新非生产库可按一条受支持命令完成 `base -> b4c5d6e7f890 -> basic -> head`。
- [ ] 已在 head 的数据库重复执行为无害 no-op。
- [ ] 生产缺失/占位 digest、basic 状态冲突或中间步骤失败时停止，API/Worker 不启动。
- [ ] README 本地与生产说明不再建议全新库直接 `upgrade head`。

**验证**：迁移脚本单元测试、SQLite/MySQL 迁移测试、shell 静态检查；Docker 可用时分别演练空库和重复执行。

**依赖**：Task 1.1。  
**预计范围**：M。

#### Checkpoint A

- [ ] 迁移与 CI focused tests 通过。
- [ ] Compose 配置可解析。
- [ ] 没有放松生产 fail-closed 校验。
- [ ] Codex 审查通过后再进入 Phase 2。

### Phase 2：修复核心数据完整性问题

#### Task 2.1：教学班与课程名单服务端分页

**内容**：ClassRoster、AcademicManage、CourseRosterManager 不再固定读取前 100 条；使用后端 `page/page_size/total` 契约完成真实分页或逐页加载，并保持搜索、人数和移除操作一致。

**验收标准**：

- [ ] 第 101 名学生和第 101 个教学班可以被查看、搜索和管理。
- [ ] UI 显示后端 `total`，不能以当前数组长度冒充总数。
- [ ] 分页切换、增加/移除后会刷新正确页且不会产生重复项。

**验证**：对应 Vue 单元测试（构造 `total > 100`）、后端分页测试、前端 lint/test/build。

**依赖**：Checkpoint A。  
**预计范围**：M；如超过 5 个文件，拆成“教学班名单”和“课程名单”两个增量。

#### Task 2.2：考试管理服务端分页与筛选

**内容**：考试列表不能只加载 100 条后前端切片。优先扩展已有列表 API 的 `q/status/course_id/sort` 参数并由后端分页，前端以响应的 `total/page/page_size` 驱动。

**验收标准**：

- [ ] 第 101 个考试可见；状态、课程、关键词筛选在全数据集上生效。
- [ ] 统计卡片不再用当前页数组推断全局总量；如无法低成本提供全局分项统计，应明确显示当前筛选总量而非假数据。
- [ ] API 参数有边界校验，教师仍只能看到自己有权管理的考试。

**验证**：后端授权/筛选/分页测试、ExamManageView 测试、前端全套。

**依赖**：Checkpoint A。  
**预计范围**：M。

#### Task 2.3：修复学生学号搜索契约

**内容**：`list_students` 的模糊搜索加入 `student_no`，并使 UI 提示与后端行为一致。

**验收标准**：

- [ ] 教师和管理员可用姓名、用户名、学号搜索 active student。
- [ ] 角色/状态过滤和返回字段不放宽。

**验证**：先增加失败的 API 回归测试，再运行用户/名单相关测试。

**依赖**：无。  
**预计范围**：S。

#### Checkpoint B

- [ ] 后端名单/考试 focused tests 通过。
- [ ] 前端 lint、相关 Vitest、生产 build 通过。
- [ ] 人工检查所有 `page_size: 100` 用法，区分“明确上限”与“错误截断”。
- [ ] Codex 审查 API 契约、权限与大数据量行为。

### Phase 3：修复反向代理与认证边界

#### Task 3.1：视频播放地址改为同源安全地址

**内容**：优先返回同源相对 URL，避免依赖内层 `request.base_url` 猜测外部 scheme；若契约必须绝对 URL，则只接受经过明确可信代理链归一化的外部 origin。

**验收标准**：

- [ ] 外层 HTTPS/内层 HTTP 时，浏览器不会得到 `http://` 播放地址。
- [ ] 签名参数、TTL、用户/课程二次鉴权和 Range 行为不变。
- [ ] 直接本地 HTTP 开发仍可播放。

**验证**：API 回归测试覆盖代理头与相对 URL；前端视频相关测试。

**依赖**：Checkpoint B。  
**预计范围**：S。

#### Task 3.2：建立明确的可信代理/IP 解析策略

**内容**：取消 production Compose 中无条件 `DAI_TRUSTED_PROXY=true`。使用明确的可信代理配置（可信 CIDR/跳数或边界已清洗的单一 header），默认不信任客户端可伪造的 XFF；为“浏览器 -> 外层 LB -> 内层 Nginx -> API”和“浏览器 -> 内层 Nginx -> API”分别定义行为。

**验收标准**：

- [ ] 不能通过伪造 XFF 绕过 IP 限流。
- [ ] 多层代理下不同客户端不会落入同一个 LB 限流桶。
- [ ] 配置缺失时 fail-safe，部署文档明确需要配置的代理边界。

**验证**：登录限流测试覆盖直连、单层、多层和伪造 XFF；Compose 配置测试。

**依赖**：Task 3.1。  
**预计范围**：M。

#### Checkpoint C

- [ ] Auth、Cookie、CORS、视频媒体测试全部通过。
- [ ] 安全头脚本和 Compose 配置通过。
- [ ] Codex 按安全边界审查，不接受“信任所有 XFF”的简化方案。

### Phase 4：稳定性、性能与可观测性

#### Task 4.1：统一 Redis/健康检查资源生命周期

**内容**：API 进程复用受控 Redis client/pool，并在 lifespan shutdown 关闭；readiness 使用上下文或 `finally` 关闭数据库 Session，健康检查不得泄漏客户端。

**验收标准**：

- [ ] 多请求不会每次新建独立 Redis pool。
- [ ] MySQL/Redis 检查成功与异常路径都释放资源。
- [ ] 测试依赖覆盖仍可注入 fakeredis，不破坏现有测试隔离。

**验证**：资源生命周期单元测试、health/auth 全套测试。

**依赖**：Checkpoint C。  
**预计范围**：M。

#### Task 4.2：避免事件循环执行同步扫描

**内容**：考试过期扫描和 Kernel 清理通过 `asyncio.to_thread` 或独立 worker 执行同步 DB/Docker 工作；保持取消、租约、异常日志语义。

**验收标准**：

- [ ] 慢扫描期间 event loop 仍可响应轻量 coroutine。
- [ ] shutdown 能取消任务，异常不会终止后续轮询。

**验证**：可控慢函数的 async 回归测试、考试过期扫描测试。

**依赖**：Task 4.1。  
**预计范围**：S。

#### Task 4.3：修复指标并建立队列可见性

**内容**：`judge_queue_depth` 读取普通判题队列，并分别暴露 exam/AI 队列；字段名与真实队列一一对应，保留低基数和 Redis 故障降级。

**验收标准**：

- [ ] 三类队列分别写入不同深度后，指标返回对应值。
- [ ] 不泄露任务内容，Redis 不可用时接口仍安全降级。

**验证**：metrics API 回归测试。

**依赖**：Task 4.1。  
**预计范围**：S。

#### Task 4.4：考试成绩分页与查询收敛

**内容**：成绩列表 items 使用服务端分页和显式 eager/bulk 查询；汇总统计在数据库或固定数量查询中计算，不随当前页失真。保持缺考学生的派生状态。

**验收标准**：

- [ ] `page/page_size/total` 对全体受众正确，超大班级不返回无界响应。
- [ ] 查询数不随提交人数线性增加。
- [ ] 平均分、分布、状态计数和缺考项与分页前结果一致。

**验证**：API 行为测试 + 查询计数上限测试 + GradeView 前端测试。

**依赖**：Checkpoint B。  
**预计范围**：M。

#### Task 4.5：拆分确定性判题与 AI 消费能力

**内容**：Worker 支持通过配置选择队列；生产 Compose 至少有确定性 judge worker 和可选 AI worker。AI 默认关闭时不启动外呼消费能力；启用时 AI 慢调用不能阻塞普通/考试判题。

**验收标准**：

- [ ] judge worker 只消费普通/考试队列，AI worker 只消费 AI 队列。
- [ ] stale recovery 仍只有一个租约持有者执行，不能造成重复评分。
- [ ] AI 未审批/未启用时系统保持人工复核路径，不外呼。

**验证**：worker 队列选择、租约和 AI-disabled 测试；Compose 静态测试。

**依赖**：Task 4.3。  
**预计范围**：M。

#### Checkpoint D

- [ ] 后端全量 pytest 与 Ruff 通过。
- [ ] 前端相关测试与 build 通过。
- [ ] 资源、查询数和队列隔离有自动化证据。
- [ ] Codex 审查稳定性、性能、幂等和故障路径。

### Phase 5：生产镜像、遗留项与文档收敛

#### Task 5.1：拆分运行与开发依赖

**内容**：生产后端镜像只安装运行依赖；pytest、fakeredis、moto、ruff、radon 等进入开发/测试依赖文件。CI 仍安装完整测试依赖。

**验收标准**：

- [ ] API/worker/environment-builder 所需运行包没有遗漏。
- [ ] 生产镜像不含测试框架和测试模拟服务。
- [ ] 依赖审计仍执行，锁定策略和 SCA 接受记录一致。

**验证**：Docker build/import smoke、pytest、pip-audit 接受门禁。

**依赖**：Checkpoint D。  
**预计范围**：M。

#### Task 5.2：收敛 legacy/死代码

**内容**：在不破坏现有新前端的前提下，处理硬编码 Jupyter 模板/假复制、过期 notebooks shim、无后端对应且无调用的 `examsAPI.delete`。需要删除兼容行为时先以测试证明无当前消费者，并在文档记录迁移。

**验收标准**：

- [ ] 禁用 legacy Jupyter 时不对外宣称模板复制可用。
- [ ] Sunset 到期的接口被移除或返回清晰、测试覆盖的终止响应。
- [ ] 无调用的客户端接口被删除，不留下新的死代码。

**验证**：全仓引用搜索、路由测试、前端 lint/test。

**依赖**：Checkpoint D。  
**预计范围**：S/M。

#### Task 5.3：更新发布文档与证据清单

**内容**：README、环境手册、TLS、Docker socket、备份恢复和评估报告只记录真实状态；添加可勾选的 production evidence 清单和命令，但外部事项保持待验收。

**验收标准**：

- [ ] 本地、CI、disposable smoke、production 四种语义清晰分离。
- [ ] 每个 P0 有责任方、证据路径和阻断条件。
- [ ] 文档链接测试通过，无“已完成”但无证据的描述。

**验证**：文档链接测试、命令/环境变量交叉检查、人工审阅。

**依赖**：Tasks 5.1、5.2。  
**预计范围**：M。

#### Checkpoint E：仓库修复完成

- [ ] 后端全量测试、Ruff、前端 lint/test/build 全绿。
- [ ] npm audit 和 Python SCA 门禁通过。
- [ ] Docker Compose config、空库 bootstrap、E2E、Docker smoke 通过。
- [ ] diff 无密钥、无无关格式化、无构建产物。
- [ ] Codex 五轴审查结论为 Approve；否则 OpenCode 按 Required findings 继续修复。

## 4. 生产环境外部验收阶段

这些任务由部署方执行，OpenCode 只能完善脚本/文档，Codex 只能核验证据：

| Gate | 必需证据 | 未完成时结论 |
| --- | --- | --- |
| 备份恢复 | 加密备份记录、校验和、隔离恢复日志、RPO/RTO、签字 | NO-GO |
| TLS/证书 | TLS 终止配置、HSTS 实测、证书续期与到期告警 | NO-GO |
| Docker 主机 | 专机证明、2375/2376 未监听、daemon 配置、socket 风险接受 | NO-GO |
| Registry/环境 | 3.10/3.11/3.12 build、push、digest pull-back、运行 smoke | NO-GO |
| 容量 | 目标并发阶梯压测、Kernel 准入、队列/内存/磁盘阈值与告警 | NO-GO |
| 漏洞与 AI | SCA 接受/修复签字；AI 数据治理批准或保持关闭 | 未批准则 AI 必须关闭 |

## 5. 最终验收命令

实现方应按影响范围先跑 focused tests；最终由 Codex 独立执行或复核：

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/ruff check app/

cd ../frontend
npm run lint
npm test
npm run build
npm audit --omit=dev --audit-level=high

cd ..
docker compose -f docker-compose.prod.yml config -q
```

Docker、MySQL、E2E 和 Registry 测试必须在允许产生隔离容器/卷/镜像的环境运行；失败时保存日志，不通过删除测试或放松生产校验绕过。

## 6. 交付与审查协议

OpenCode 每完成一个 Phase 应报告：修改文件、RED/GREEN 测试、未处理事项、潜在风险，并停止等待 Codex 验收。Codex 将先审测试、再审实现，按 Correctness、Readability、Architecture、Security、Performance 五个维度给出 `Approve` 或 `Request changes`。所有 Critical/Required finding 关闭后，才进入下一 Phase。
