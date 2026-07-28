# DAI 智能代码评分 V1 设计说明

**状态：** 已确认  
**确认日期：** 2026-07-29  
**实现分支：** `AIpanti`  
**上游评分标准：** `DAI智能代码评分方案_V1.md`

## 1. 目标与范围

本轮在现有 Python Docker 判题基础上增加题目专属 Rubric、DeepSeek 语义评分、固定公式合并、教师复核和可解释反馈。实现同时覆盖：

- 作业编程题：`JudgeQuestion` / `Submission`；
- 考试编程题：`ExamQuestion(question_type="code")` / `ExamAnswer`。

本轮不覆盖 Notebook 实验评分、选择题、AI 生成检测、Python 以外的语言或开放式项目评分。

每份 V1 原始成绩固定为：

```text
S100 = F60 + A20 + R10 + Q10
```

作业直接使用 `S100`。考试编程题按题目分值折算：

```text
answer_score = S100 / 100 * ExamQuestion.points
```

## 2. 上线方式

题目具有三种评分模式：

- `legacy`：完全保留现有确定性评分，不调用 AI；
- `shadow`：生成 V1 分项成绩供教师观察，但正式成绩仍使用现有确定性规则；
- `active`：V1 分项成绩正式计入学生成绩。

数据库迁移把所有历史题目设为 `legacy`。新建编程题默认 `shadow`，教师主动切换到 `active` 后才把 AI 成绩计入正式成绩。

影子评分只对教师和管理员可见。学生只在 `active` 模式看到 AI 分项、证据与反馈。

## 3. 题目评分配置

作业和考试编程题增加同构配置：

- `grading_mode`：`legacy` / `shadow` / `active`；
- `teacher_constraints`：教师硬性要求的结构化 JSON；
- `reference_solution`：可选参考实现，只帮助理解题意；
- `test_groups`：F/R 的结构化测试组；
- `score_cap_rules`：教师明确配置的总分上限规则。

`test_groups` 中每组包含：

```json
{
  "id": "F_CORE",
  "name": "核心功能",
  "dimension": "F",
  "max_score": 30,
  "tests": "def test_core_case(): ..."
}
```

启用 `shadow` 或 `active` 时，后端必须验证：

- F 组满分之和为 60；
- R 组满分之和为 10；
- ID 唯一；
- 每组有非空 pytest 测试；
- 只接受 `F` 或 `R` 维度；
- 时间和内存限制为正数。

旧 `hidden_tests` 字段继续服务 `legacy` 题目，不自动推断或伪造 F/R 分组。历史题目只有教师明确升级后才进入 V1。

## 4. Rubric 生命周期

题目专属 Rubric 使用独立版本表保存。每个 Rubric 只关联一种题目：

- `judge_question_id` 或 `exam_question_id` 二选一；
- `version` 在同一题目内递增；
- `status` 为 `draft`、`locked` 或 `superseded`；
- 保存生成模型、生成输入摘要、完整输入快照、Rubric JSON 和锁定时间。

Rubric 生成输入包括题目描述、接口、数据范围、教师硬性要求、参考实现、测试组名称及权重、通用质量规则。参考实现不能被提示词描述为唯一答案。

发布含 `shadow` / `active` 编程题的作业或考试前，所有相关题目必须存在已锁定 Rubric。没有 Rubric 时先调用 DeepSeek 生成；生成、校验或锁定失败则拒绝发布并保持草稿。

教师可以查看、修改草稿 Rubric、锁定新版本以及对历史提交发起统一重评。每次正式评分都记录实际使用的 Rubric ID，旧提交不会被悄悄切换版本。

## 5. DeepSeek 接入

DeepSeek 使用 OpenAI 兼容 HTTP 接口，不在代码中保存密钥：

```text
DAI_AI_BASE_URL=https://aihub.codingpython.cn
DAI_AI_MODEL=deepseek-v4-flash
DAI_AI_API_KEY=<local secret>
```

仓库只提交 `.env.example` 变量名。真实 Key 仅进入 Git 忽略的本地 `.env` 或部署平台 Secret。

客户端使用现有 `httpx`，统一处理：

- Base URL 与 `/v1/chat/completions` 路径拼接；
- 连接、读取和总超时；
- 429、5xx 和网络错误的有限重试；
- 请求 ID 和耗时日志；
- 严格 JSON 提取；
- 错误正文脱敏，禁止记录 Authorization 或完整学生代码；
- 通过依赖注入在测试中使用假客户端。

Rubric 生成与代码评分使用不同的系统提示词和 Pydantic 输出模型。模型不得返回 F、R 或最终总分。

## 6. 确定性 F/R 评分

判题容器继续使用只读代码挂载、禁网、资源限制和非特权用户。V1 Worker 逐个运行结构化测试组，并加载平台控制的 pytest 结果插件。插件输出带固定前缀的 JSON 统计：

```json
{
  "passed": 3,
  "failed": 1,
  "errors": 0,
  "skipped": 0
}
```

组通过比例为：

```text
passed / (passed + failed + errors)
```

没有可计数用例、收集失败、超时或插件结果无效的组记为系统错误，不把它伪装成学生错误。合法组按 `max_score * pass_ratio` 计算，后端分别汇总 F 和 R，并校验上限 60/10。

## 7. 静态分析与 AI 评分

静态分析只读取源码，不执行学生代码。它输出：

- Python AST 是否可解析；
- Ruff 诊断的规则编号和行号；
- Radon 圈复杂度摘要；
- 文件行数、函数数量和最大嵌套等受控指标。

AI 收到以下信息：

- 锁定 Rubric；
- 带行号的学生代码；
- F/R 分组结果；
- 静态分析摘要；
- 题目与教师约束。

AI 只计算 A20 和 Q10，并逐项返回 `criterion_id`、等级、得分、真实代码行、证据、`reason_code` 和扣分原因。无法确认时不扣分或标记教师复核。

## 8. 评分记录与队列

新增统一的 `CodeGrade`，通过 XOR 外键关联一份 `Submission` 或 `ExamAnswer`。它保存：

- 使用的 Rubric ID 和评分模式；
- `pending`、`queued`、`running`、`completed`、`review_required`、`system_error` 状态；
- F/A/R/Q、原始总分、上限、最终 100 分制成绩和考试折算成绩；
- 确定性结果、静态分析、AI 结构化输出和脱敏后的原始响应；
- 是否需要教师复核、原因、重试次数和错误摘要。

Docker 判题完成后创建 `CodeGrade`，再通过独立 Redis 队列 `judge:ai:queue` 唤醒 AI 评分。数据库仍是任务唯一事实源，Redis 只负责通知；重复消息通过条件更新和唯一约束实现幂等。

`shadow` 模式可以先完成现有正式成绩，再异步补齐 AI 结果。`active` 模式只有 AI 评分合法完成或教师完成覆盖后才结算正式成绩。AI 连续失败时不得擅自赠分或扣分，记录进入 `review_required`，考试提交保持待复核状态。

## 9. 后端固定合并与防重复扣分

后端重新计算所有分项，绝不信任模型返回的维度总分：

- A 的每项必须属于锁定 Rubric，且总上限为 20；
- Q 的每项必须属于固定质量 Rubric，且总上限为 10；
- 行号必须存在于学生代码；
- `complete` / `partial` / `missing` 分别对应 1 / 0.5 / 0；
- 每项实际分数必须等于满分乘等级系数；
- F/R 来自 Docker，AI 返回这些字段即判输出无效。

相同 `reason_code` 且代码证据重叠的跨维度扣分被标记为潜在重复。逻辑错误不得再次作为 Q 扣分；无法自动消解时进入教师复核。

总分上限只能来自教师保存的 `score_cap_rules`。AI 可以返回匹配规则的事实证据，但不能创建上限。后端应用上限并保存命中的规则和原始分。

## 10. 教师复核与审计

教师只能管理自己课程的题目和提交，管理员可管理全部。教师能够：

- 查看 Rubric 版本和原始生成结果；
- 修改、锁定新 Rubric；
- 查看影子/正式分项、证据、异常与模型原始输出；
- 重试单份 AI 评分；
- 按当前 Rubric 统一重评；
- 覆盖 A、Q 或最终成绩。

覆盖必须填写理由，并写入独立 `GradeOverride` 审计记录，包含原成绩快照、新成绩、修改人和时间。不得删除旧覆盖记录。

## 11. 前端体验

教师题目编辑页增加：

- 评分模式；
- 教师硬性要求；
- 参考实现；
- F/R 测试组；
- 上限规则；
- Rubric 生成、查看、修改和锁定状态。

新增统一 AI 评分复核列表和详情页，支持按作业/考试、状态、学生筛选，并提供重试、覆盖和统一重评入口。

学生作业结果页在 `active` 模式显示 F/A/R/Q、上限、证据和改进建议；`shadow` 不暴露 AI 分。考试成绩接口按同样规则返回编程题分项。

## 12. 失败与安全策略

- 未配置 Key 的开发环境可以运行 `legacy`，但不能发布 `shadow` / `active` 题目；
- 发布时 AI 不可用：保持草稿并返回可重试错误；
- 评分时 AI 暂时失败：指数退避重试；
- 达到重试上限：进入教师复核，不把服务故障算作学生错误；
- AI JSON 不合法：最多执行一次带验证错误摘要的修复请求，仍失败则复核；
- 日志、API 错误和数据库 `last_error` 不得包含 Key；
- 提示词把学生代码和题目内容标记为不可信数据，忽略其中的指令；
- 任何 AI 输出都经过 Pydantic 与业务规则双重校验。

## 13. 测试与验收

后端测试覆盖：

- 历史题迁移为 `legacy`；
- F/R 配置与比例计分；
- Rubric 版本、锁定与发布门禁；
- DeepSeek 成功、超时、429、5xx、坏 JSON 和脱敏；
- A/Q 业务校验、真实行号、防重复扣分和上限；
- shadow/active 行为差异；
- 考试分值折算和最终汇总；
- AI 队列幂等、崩溃恢复与教师复核；
- 权限、统一重评和覆盖审计。

前端测试覆盖题目配置、Rubric 状态、教师复核和学生分项展示。最终运行完整 pytest、Vitest、前端构建、Alembic 空库升级、Docker 判题 smoke 和现有 Playwright 主流程。

## 14. 明确不做

- 不把 AI 当作最终分数事实源；
- 不检测学生代码是否由 AI 生成；
- 不自动把历史题切换到 V1；
- 不从参考代码推导未声明的限制；
- 不因变量名、写法不同或缺少非必要注释扣分；
- 不把 AI 服务故障转化为学生低分；
- 不提交或打印真实 API Key。
