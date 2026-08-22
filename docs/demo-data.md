# Demo 演示数据体系

本项目提供一套**真实、可重复生成、适合开发测试与项目演示**的 Demo 数据。

- 入口：`python -m app.cli seed-demo`（幂等，可重复执行）
- 固定参考日期默认 2026-12-07（可 `--reference-date now` 取运行当日）
- 所有权登记表 `demo_seed_marks`：`--reset-demo` 只清理 Demo 自己创建的数据
- 与 CI / E2E / 自动化测试完全隔离（不占用 `admin/teacher/student` 用户名）

---

## 一、前置条件

1. 数据库迁移（本地 dev 库为空时必须先执行统一 bootstrap）：

   ```bash
   cd backend
   .venv/bin/python ../scripts/bootstrap_database.py
   ```

   > 注意：bootstrap 会按 `base → 迁移 A → basic → head` 顺序执行；生产环境还要求
   > 真实 basic 镜像 digest，不能用占位值。若仅做 SQLite fixture 演示，可使用项目
   > 的开发 `.env` 和 disposable 模式。

2. 环境档位（basic 必须 available 且带**真实镜像 ID**；data/torch-cpu 可选）：

   ```bash
   .venv/bin/python -m app.cli seed-environments --enqueue   # 创建档位 + 入队构建
   # 方式 A（推荐，真实镜像）：启动环境构建 Worker 完成 basic v1 构建
   #   .venv/bin/python -m app.worker.environment_builder_worker
   # 方式 B（仅 disposable 烟测，占位 digest）：空库一次性初始化
   #   DAI_DATABASE_URL='mysql+pymysql://dai:dai_password@localhost:3306/dai_platform' \
   #     ../scripts/seed-basic-environment-mysql.py
   ```

   > 方式 B 只用于本地/CI disposable 烟测，不能作为生产 basic 产物或上线证据。
   > **真实判题前置**：`seed-demo` 的真实 Docker 判题要求 basic 的 `image_digest`
   > 是本机真实存在的镜像 ID（`docker image inspect sha256:...` 能查到）。
   > 占位 digest（如 `sha256:aaa...`）会被 `real_judge_available` 判定为不可用，
   > 种子自动降级为 seed_fixture，**不会**再把整批提交写成 system_error。
   > 如果当前机器已经构建并 smoke `dai-env:basic-v1`，必须读取**当前 Docker daemon**
   > 返回的 image ID；不要复制其他机器文档或数据库中的 `sha256`：

   ```bash
   docker image inspect dai-env:basic-v1 --format '{{.Id}}'
   # 将上一条命令的完整输出替换到 <TARGET_MACHINE_IMAGE_ID>
   docker exec dai-mysql mysql -uroot -proot_password dai_platform \
     -e "UPDATE environment_versions SET image_digest='<TARGET_MACHINE_IMAGE_ID>' \
          WHERE profile_id=(SELECT id FROM environment_profiles WHERE slug='basic') AND version_number=1;"
   ```

---

## 二、运行与重置

```bash
cd backend

# 播种（默认固定参考日期 2026-12-07，任意时刻运行产出一致）
.venv/bin/python -m app.cli seed-demo

# 演示当日时效（截止临近/即将考试等按真实当前时间计算）
.venv/bin/python -m app.cli seed-demo --reference-date now

# 重建：先按所有权登记表清理 Demo 数据，再重新播种
.venv/bin/python -m app.cli seed-demo --reset-demo

# 其他选项
#   --skip-env-check   跳过 basic 环境版本前置校验（仅供测试）
#   --force-fixture    强制全部提交使用 seed_fixture（不做真实 Docker 判题）
```

> `--reset-demo` 只删除 `demo_seed_marks` 登记过的行（按外键拓扑逆序）。
> 未登记业务行（即使用户手动给 Demo 题目提交过）绝不删除；外键阻断时整体回滚并报告。
> 为保障可重复重置，以下 API/审计运行态会随 Demo 数据一并清理：
> `notifications` / `notification_reads` / `user_preferences`（引用 Demo 用户）、
> `grade_overrides`（引用 Demo code_grades）。
> `exam_grades` 是考试汇总派生数据，会按 Demo 考试删除；环境控制面保留，仅将指向
> Demo 用户的可空审计外键置空。未知的 `demo_seed_marks.table_name` 会使 reset 失败，
> 不会被静默忽略。当前 seed 不创建 StorageObject 或上传文件，因此课程封面使用
> `Course.cover` 中明确的 data URI 兼容数据，Studio 的 legacy 资源目录保持为空；
> 手工上传的封面、视频和 Studio Asset 不会被此 reset 触碰。
> 绝不 DROP DATABASE、不动环境控制面、不动 E2E 数据。

---

## 三、固定演示账号（默认密码 `Demo1234!`，`DAI_DEMO_PASSWORD` 可覆盖）

| 用户名 | 姓名 | 角色 | 演示用途 |
|---|---|---|---|
| `demo_admin` | 系统管理员 | admin | 管理端：用户 / 教务 / 课程 / 环境档位 |
| `teacher_zhang` | 张明远 | teacher | **旗舰教师**：完整课程 / 作业 / 考试 / AI 复核链路 |
| `teacher_chen` | 陈思远 | teacher | 第二教师：支撑课程 + 章节测验 |
| `teacher_zhao` | 赵清禾 | teacher | 第三教师：含 1 门草稿课程 + 1 门白名单课程 |
| `demo_student_elite` | 林书瑶 | student | 优秀学生：全勤、高分、AI 无复核 |
| `demo_student_average` | 周子涵 | student | 普通学生：偶尔迟交、AI 建议较多 |
| `demo_student_struggling` | 王雨桐 | student | 学习困难：缺交、多次修改、待复核集中 |
| `demo_student_new` | 赵晨曦 | student | 新加入：数据少、部分课程未开始 |
| `student_24621601_01` … `student_24621606_10` | 生成 | student | 56 名背景学生（固定种子） |

> 账号不占用 `admin/teacher/student`，与 E2E 种子完全隔离；固定画像学生数据完全稳定。

---

## 四、故事线（Demo 数据如何互相解释）

**链路 A：Python 全链路（旗舰课程「Python 与 AI 实验全流程」）**
学期第 1 周（ref-91d）→ 教师建课发布（ref-93d）→ 学生选课 → 逐章学习（lesson_progress）
→ 作业一/二/三（普通判题，accepted/wrong_answer 混合）→ 期中考试（ref-35d 考试、
ref-28d 复核发布；单选/多选/填空/编程，AI 评分 + 教师复核）→ AI 评分作业一（due ref-10d）、
AI 评分作业二（due ref+4d，教师首页 7 天截止窗口可见）→ 期末（ref+35d 考试，已发布未开始）。

**链路 B：实验与反馈**
Notebook 模板（published）→ 挂课时 + 独立模块 → 学生打开（started）→ 提交（submitted）
→ 教师评分反馈（部分已复核进入学生「最新反馈」，部分未复核进入教师「待复核」队列）。

**链路 C：公告与教务**
学期初全局公告 → 课程公告 → 已读回执 → 学生首页未读数真实变化；教务页展示当前学期
与已关闭历史学期。

**链路 D：白名单课程与权限边界**
教师赵清禾发布「AI 创新实践（白名单）」课程（不绑定教学班）→ 仅 elite / average / new
三名学生进入白名单 → elite 已手动选课可访问内容，average / new 仅可发现未选课，
struggling 不在白名单（课程列表不可见），用于验证课程可见性、白名单管理和选课权限。

---

## 五、数据规模（播种后真实计数）

| 表 | 数量 | 表 | 数量 |
|---|---|---|---|
| users | 64 | lesson_progress | ~1065 |
| academic_terms | 2 | assignments | 10 |
| teaching_classes | 6 | judge_questions | 15 |
| teaching_class_students | 60 | submissions | ~636 |
| courses | 8 | exams / exam_questions | 3 / 15 |
| chapters | 21 | exam_submissions / exam_answers / exam_grades | 72 / 360 / 55 |
| lessons | 69 | notebook_templates / versions | 25 / 25 |
| course_enrollments | 211 | experiment_modules / records / submissions | 4 / ~157 / ~156 |
| question_rubrics | 5 | code_grades | 180（completed 147 / review_required 33） |
| course_whitelist_students | 3 | announcements | 5 |
| storage_objects / storage_quarantines | 0 / 0 | demo_seed_marks | 3276 |

（数量由固定随机种子决定，同一代码版本 + 同一参考日期下完全一致。）

---

## 六、验证结果

- **幂等**：连续两次 `seed-demo` 计数一致（无重复行）。
- **重置**：`--reset-demo` 清空业务表后重播，计数与首次一致；环境控制面保留。
  已实测在调用过通知/偏好/教师改分接口后仍可正常重置（自动清理引用 Demo 数据的运行态与审计行）。
- **真实判题**：basic 镜像 ID 可用时，固定核心学生（elite/average）的 legacy 作业提交
  走真实 Docker 判题（`seed_fixture=false`、真实 `execution_time_ms`）；
  其余提交为显式 seed_fixture。判题结果状态只含 accepted / wrong_answer /
  graded / running（AI 复核队列态），**零 system_error**（校验器会拦截回归）。
- **考试评分**：期中与章节测验中进入可评分历史线的提交先保持 `grading`，随后统一调用
  `app.services.exam_grading.finalize_if_ready`；只有所有答案为 `completed` 且有分数时才进入
  `graded` 并生成 `ExamGrade`。固定参考日期下为 `graded 55 / review_required 15 / submitted 2`，
  `ExamGrade` 为 55，考试答案 `system_error` 为 0。
- **环境状态**：Demo 只消费已有 `basic` `available + image_digest` 版本，不创建 BuildJob；
  校验器会拒绝 `available` 无 digest、`queued` 无活动任务以及 `succeeded` 残留错误。
- **Storage 边界**：本轮 seed 只写数据库中的 Notebook/实验 JSON 和 data URI，不调用本地文件写入，
  也不登记 `StorageObject`；真实上传链路仍由 Course/Lesson/Studio 的 StorageObject 业务服务负责。
- **API**：8 个固定账号全部可登录；SQLite disposable 数据库中的
  `/dashboard/teacher`、`/dashboard/student`、`/courses`、`/assignments`、
  `/judge/submissions`、`/ai-grading/grades`、`/exams/{id}/questions`、
  `/exams/{id}/grades`、`/experiments/records` 均返回 200 与真实数据。MySQL 的成绩排序
  与导出回归需要按仓库测试命令在 MySQL 服务上单独执行，不把 SQLite 结果冒充 MySQL 证据。
  白名单课程权限：elite/average/new 可见，struggling 不可见；elite 已选课可访问内容。
- **前端**：学生首页 / 学生作业列表 / 教师首页 / AI 评分复核 / 管理端用户 均渲染真实数据，
  零 console 错误。
- **测试**：`pytest tests/automated/test_seed_demo.py` 应通过；全量后端测试使用 `pytest -q`，结果以当前 CI 或本地执行输出为准。

---

## 七、技术债修复记录（2026-08-15）

1. **占位 digest 误判“真实判题可用”**：`real_judge_available` 原来只检查 digest 非空，
   占位 `sha256:aaa...` 也会触发真实判题 → docker 报 “No such image”（rc=125）→
   `_status_from_pytest` 不抛异常地映射为 system_error → 整批提交被写坏
   （曾出现 525 条 system_error）。修复：digest 必须通过 `docker image inspect`
   解析为本机真实镜像，否则判定不可用并降级 Fixture。
2. **判题工作目录落在沙箱私有 /tmp**：`tempfile.TemporaryDirectory()` 在受限环境
   下 /tmp 对 Docker daemon 不可见 → 空挂载 → pytest usage error（rc=4）。
   修复：优先 `settings.judge_work_dir`，否则落到仓库内 `backend/.judge_work/`
   （宿主机可见，已加入 .gitignore）。
3. **Docker 级失败未降级 Fixture**：rc>=125（镜像缺失/权限/daemon 错误）现在直接
   返回 False → 调用方写 seed_fixture，不再把 system_error 落库。
4. **真实判题范围过宽**：背景学生 archetype 也取 “average”，原条件
   `archetype in ("elite","average")` 会真实判题全部 56 名背景学生。
   修复：限定 `username in FIXED_STUDENT_DEFS`（仅 4 名固定学生中的 elite/average）。
5. **校验器补防**：`verify_demo_data` 新增 system_error 计数检查，回归即失败。
