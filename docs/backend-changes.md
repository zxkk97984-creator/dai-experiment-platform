# 后端修改记录

> 本次开发对后端所做的所有修改。按文件排列，标注修改位置、原代码和新代码。

---

## 1. backend/app/api/judge.py

### 1.1 sample_run 端点 — 补充 Redis 判题队列推送

**位置**：`sample_run` 函数（约第102行）

**问题**：`POST /api/v1/judge/questions/{question_id}/sample-run` 创建了提交记录但没有推送到 Redis 判题队列，导致自测功能提交后永远停在 `queued` 状态。

**修改内容**：
- 函数签名增加参数：`redis_client` 和 `settings`
- 在 `db.commit()` 后增加 `redis_client.lpush(settings.judge_queue_name, str(submission.id))`

**原代码**：
```python
@router.post("/questions/{question_id}/sample-run", response_model=SubmissionRead)
def sample_run(
    question_id: int,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if question_id != payload.question_id:
        raise api_error(400, "QUESTION_MISMATCH", "题目 ID 不一致")
    question = db.get(JudgeQuestion, question_id)
    if not question:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    submission = Submission(
        question_id=question_id,
        student_id=current_user.id,
        code=payload.code,
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission
```

**新代码**：
```python
@router.post("/questions/{question_id}/sample-run", response_model=SubmissionRead)
def sample_run(
    question_id: int,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    if question_id != payload.question_id:
        raise api_error(400, "QUESTION_MISMATCH", "题目 ID 不一致")
    question = db.get(JudgeQuestion, question_id)
    if not question:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    submission = Submission(
        question_id=question_id,
        student_id=current_user.id,
        code=payload.code,
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    redis_client.lpush(settings.judge_queue_name, str(submission.id))
    return submission
```

### 1.2 create_submission 端点 — 增加最大提交次数检查

**位置**：`create_submission` 函数，权限校验之后、创建提交之前（约第47行后）

**问题**：学生可以无限次提交，没有次数限制。

**修改内容**：在创建提交前检查 `question.max_attempts`，如果学生提交次数已达上限则返回 400 错误。

**新增代码**（插入在 `can_view_course` 检查之后）：
```python
    # check max attempts
    if question.max_attempts is not None:
        count = db.scalar(
            select(func.count()).select_from(Submission).where(
                Submission.question_id == payload.question_id,
                Submission.student_id == current_user.id,
            )
        ) or 0
        if count >= question.max_attempts:
            raise api_error(400, "MAX_ATTEMPTS_REACHED", f"已达到最大提交次数（{question.max_attempts}次）")
```

---

## 2. backend/app/models/__init__.py

### 2.1 JudgeQuestion 模型 — 增加 max_attempts 字段

**位置**：`JudgeQuestion` 类，`memory_limit_mb` 之后（约第122行）

**修改内容**：新增 `max_attempts` 字段，`Integer` 类型，默认 `None`（表示不限制）。

**新增代码**：
```python
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
```

**插入位置**（`memory_limit_mb` 和 `assignment` 属性之间）：
```python
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=10000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)  # 新增

    assignment: Mapped[Assignment] = relationship(back_populates="questions")
```

---

## 3. backend/.env

### 3.1 判题模式改为本地执行

**位置**：`DAI_JUDGE_USE_DOCKER`（第12行）

**原值**：`true`
**新值**：`false`

**原因**：当前环境未构建 `dai-judge-python` Docker 镜像，且 Docker Hub 拉取不稳定。改为 `false` 后判题 Worker 直接在本地 Python 环境中执行 pytest。

---

## 4. backend/alembic/versions/ce783604b070_add_max_attempts.py

### 4.1 数据库迁移 — judge_questions 表新增 max_attempts 列

**自动生成**：`alembic revision --autogenerate -m "add max_attempts"`

**生成的迁移**：
```python
def upgrade() -> None:
    op.add_column('judge_questions', sa.Column('max_attempts', sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column('judge_questions', 'max_attempts')
```

---

## 变更总结

| # | 文件 | 变更类型 | 说明 |
|---|------|----------|------|
| 1 | `app/api/judge.py:102-125` | 修改 | sample_run 补上 Redis 队列推送 |
| 2 | `app/api/judge.py:47-55` | 新增 | create_submission 增加 max_attempts 检查 |
| 3 | `app/models/__init__.py:122` | 新增 | JudgeQuestion 新增 max_attempts 字段 |
| 4 | `.env:12` | 修改 | DAI_JUDGE_USE_DOCKER = false（本地判题） |
| 5 | `alembic/versions/ce783...py` | 新增 | 数据库迁移文件 |
