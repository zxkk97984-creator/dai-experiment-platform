"""bind environment versions to business records

业务绑定迁移（Phase 3：迁移 B）——为作业/题目/提交/Notebook/实验记录绑定不可变环境版本：

- assignments：environment_version_id（作业默认环境，必填）
- judge_questions：environment_version_id（题目覆盖环境，可空=继承作业）
- submissions：environment_version_id + import_policy 快照（提交时冻结实际环境与策略）
- notebook_templates：draft_environment_version_id（草稿环境，发布时复制到模板版本）
- notebook_template_versions：environment_version_id（发布快照，不可变）
- experiment_records：environment_version_id（从模板版本复制，便于运行时直接读取）

升级步骤（plan 5「迁移 B」）：
1. 查询 basic 档位最新 available 版本并验证 image_digest 非空；
   不满足时主动失败并提示先完成 seed build（fail-closed）。
2. 以 nullable 方式添加绑定字段。
3. 存量作业/题目/提交/Notebook 草稿/Notebook 历史版本全部回填 basic v1；
   存量 import 策略：作业/提交/Notebook 为 unrestricted，题目为 inherit。
4. ExperimentRecord 优先复制其 NotebookTemplateVersion 的环境版本；孤儿记录兜底 basic。
5. 验证所有必填列无 NULL 后改成 non-null。
6. 添加外键和索引。

降级只删除新增业务绑定列，不删除控制面表和 Docker 镜像（保留镜像审计数据）。

Revision ID: c5d6e7f8a901
Revises: b4c5d6e7f890
Create Date: 2026-08-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c5d6e7f8a901"
down_revision = "b4c5d6e7f890"
branch_labels = None
depends_on = None


# 各业务表：绑定列定义（环境列 / 策略列 / 白名单列）
# allowed_imports 系列 JSON 列不加 server_default（MySQL JSON 默认表达式兼容性），
# 由 ORM Python default 提供值；import_policy_mode 系列加 server_default。
_ASSIGNMENTS = [
    sa.Column("environment_version_id", sa.BigInteger(), nullable=True),
    sa.Column("import_policy_mode", sa.String(length=16), nullable=True, server_default="unrestricted"),
    sa.Column("allowed_imports", sa.JSON(), nullable=True),
]
_JUDGE_QUESTIONS = [
    sa.Column("environment_version_id", sa.BigInteger(), nullable=True),
    sa.Column("import_policy_mode", sa.String(length=16), nullable=True, server_default="inherit"),
    sa.Column("allowed_imports", sa.JSON(), nullable=True),
]
_SUBMISSIONS = [
    sa.Column("environment_version_id", sa.BigInteger(), nullable=True),
    sa.Column("import_policy_mode_snapshot", sa.String(length=16), nullable=True),
    sa.Column("allowed_imports_snapshot", sa.JSON(), nullable=True),
]
_NOTEBOOK_TEMPLATES = [
    sa.Column("draft_environment_version_id", sa.BigInteger(), nullable=True),
    sa.Column("draft_import_policy_mode", sa.String(length=16), nullable=True, server_default="unrestricted"),
    sa.Column("draft_allowed_imports", sa.JSON(), nullable=True),
]
_NOTEBOOK_TEMPLATE_VERSIONS = [
    sa.Column("environment_version_id", sa.BigInteger(), nullable=True),
    sa.Column("import_policy_mode", sa.String(length=16), nullable=True, server_default="unrestricted"),
    sa.Column("allowed_imports", sa.JSON(), nullable=True),
]
_EXPERIMENT_RECORDS = [
    sa.Column("environment_version_id", sa.BigInteger(), nullable=True),
]


def _require_basic_available_version(conn) -> int:
    """查询 basic 档位最新 available 版本（image_digest 非空），不满足时主动失败。"""
    basic_id = conn.execute(
        sa.text(
            "SELECT ev.id FROM environment_versions ev"
            " JOIN environment_profiles ep ON ep.id = ev.profile_id"
            " WHERE ep.slug = 'basic'"
            "   AND ev.status = 'available'"
            "   AND ev.image_digest IS NOT NULL"
            " ORDER BY ev.version_number DESC LIMIT 1"
        )
    ).scalar()
    if basic_id is None:
        raise RuntimeError(
            "迁移 B 前置不满足：basic 档位不存在 available 且带 image_digest 的版本。"
            "请先部署迁移 A 并运行 seed-environments --enqueue，等待 basic v1 构建完成。"
        )
    return basic_id


def _assert_no_null(conn, table: str, columns: list[str]) -> None:
    """防御性校验：回填后必填绑定列不允许残留 NULL（plan 5 步骤 6）。"""
    for col in columns:
        count = conn.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
        ).scalar()
        if count:
            raise RuntimeError(
                f"迁移 B 回填校验失败：{table}.{col} 仍有 {count} 行为 NULL，请人工核查存量数据"
            )


def upgrade() -> None:
    conn = op.get_bind()
    basic_id = _require_basic_available_version(conn)

    # ── 1. 以 nullable 方式添加绑定字段 ───────────────────────
    # 裸列（无 FK）：SQLite 的 ADD COLUMN 不支持 REFERENCES，
    # 外键统一在 batch 重建表阶段补充。
    for table, columns in (
        ("assignments", _ASSIGNMENTS),
        ("judge_questions", _JUDGE_QUESTIONS),
        ("submissions", _SUBMISSIONS),
        ("notebook_templates", _NOTEBOOK_TEMPLATES),
        ("notebook_template_versions", _NOTEBOOK_TEMPLATE_VERSIONS),
        ("experiment_records", _EXPERIMENT_RECORDS),
    ):
        for column in columns:
            op.add_column(table, column)

    # ── 2. 存量回填（plan 5 步骤 3/4/5）───────────────────────
    # 作业/题目/提交：全部绑定 basic v1
    op.execute(
        sa.text(
            "UPDATE assignments SET environment_version_id = :basic_id,"
            " import_policy_mode = 'unrestricted', allowed_imports = '[]'"
        ).bindparams(basic_id=basic_id)
    )
    op.execute(
        sa.text(
            "UPDATE judge_questions SET environment_version_id = :basic_id,"
            " import_policy_mode = 'inherit', allowed_imports = '[]'"
        ).bindparams(basic_id=basic_id)
    )
    op.execute(
        sa.text(
            "UPDATE submissions SET environment_version_id = :basic_id,"
            " import_policy_mode_snapshot = 'unrestricted', allowed_imports_snapshot = '[]'"
        ).bindparams(basic_id=basic_id)
    )
    # Notebook 草稿与历史版本：全部绑定 basic v1
    op.execute(
        sa.text(
            "UPDATE notebook_templates SET draft_environment_version_id = :basic_id,"
            " draft_import_policy_mode = 'unrestricted', draft_allowed_imports = '[]'"
        ).bindparams(basic_id=basic_id)
    )
    op.execute(
        sa.text(
            "UPDATE notebook_template_versions SET environment_version_id = :basic_id,"
            " import_policy_mode = 'unrestricted', allowed_imports = '[]'"
        ).bindparams(basic_id=basic_id)
    )
    # 实验记录：优先复制其模板版本的环境（模板版本此时已回填 basic）；
    # 孤儿记录（模板版本缺失）兜底绑定 basic。
    op.execute(
        sa.text(
            "UPDATE experiment_records SET environment_version_id = COALESCE("
            "  (SELECT ntv.environment_version_id FROM notebook_template_versions ntv"
            "   WHERE ntv.id = experiment_records.template_version_id),"
            "  :basic_id)"
        ).bindparams(basic_id=basic_id)
    )

    # ── 3. 验证必填列无 NULL ──────────────────────────────────
    _assert_no_null(conn, "assignments", ["environment_version_id", "import_policy_mode", "allowed_imports"])
    _assert_no_null(conn, "judge_questions", ["environment_version_id", "import_policy_mode", "allowed_imports"])
    _assert_no_null(conn, "submissions", ["environment_version_id", "import_policy_mode_snapshot", "allowed_imports_snapshot"])
    _assert_no_null(conn, "notebook_templates", ["draft_environment_version_id", "draft_import_policy_mode", "draft_allowed_imports"])
    _assert_no_null(conn, "notebook_template_versions", ["environment_version_id", "import_policy_mode", "allowed_imports"])
    _assert_no_null(conn, "experiment_records", ["environment_version_id"])

    # ── 4. 改 non-null + 外键 + 索引（batch：SQLite 重建表 / MySQL 直接 ALTER）────
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.alter_column("environment_version_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("import_policy_mode", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("allowed_imports", existing_type=sa.JSON(), nullable=False)
        batch_op.create_foreign_key(
            "fk_assignments_env_version", "environment_versions", ["environment_version_id"], ["id"]
        )
        batch_op.create_index("ix_assignments_environment_version_id", ["environment_version_id"])

    with op.batch_alter_table("judge_questions") as batch_op:
        batch_op.alter_column("environment_version_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("import_policy_mode", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("allowed_imports", existing_type=sa.JSON(), nullable=False)
        batch_op.create_foreign_key(
            "fk_judge_questions_env_version", "environment_versions", ["environment_version_id"], ["id"]
        )
        batch_op.create_index("ix_judge_questions_environment_version_id", ["environment_version_id"])

    with op.batch_alter_table("submissions") as batch_op:
        batch_op.alter_column("environment_version_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("import_policy_mode_snapshot", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("allowed_imports_snapshot", existing_type=sa.JSON(), nullable=False)
        batch_op.create_foreign_key(
            "fk_submissions_env_version", "environment_versions", ["environment_version_id"], ["id"]
        )
        batch_op.create_index("ix_submissions_environment_version_id", ["environment_version_id"])

    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.alter_column("draft_environment_version_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("draft_import_policy_mode", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("draft_allowed_imports", existing_type=sa.JSON(), nullable=False)
        batch_op.create_foreign_key(
            "fk_notebook_templates_env_version",
            "environment_versions", ["draft_environment_version_id"], ["id"],
        )
        batch_op.create_index(
            "ix_notebook_templates_draft_environment_version_id", ["draft_environment_version_id"]
        )

    with op.batch_alter_table("notebook_template_versions") as batch_op:
        batch_op.alter_column("environment_version_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.alter_column("import_policy_mode", existing_type=sa.String(length=16), nullable=False)
        batch_op.alter_column("allowed_imports", existing_type=sa.JSON(), nullable=False)
        batch_op.create_foreign_key(
            "fk_template_versions_env_version",
            "environment_versions", ["environment_version_id"], ["id"],
        )
        batch_op.create_index("ix_template_versions_environment_version_id", ["environment_version_id"])

    with op.batch_alter_table("experiment_records") as batch_op:
        batch_op.alter_column("environment_version_id", existing_type=sa.BigInteger(), nullable=False)
        batch_op.create_foreign_key(
            "fk_experiment_records_env_version",
            "environment_versions", ["environment_version_id"], ["id"],
        )
        batch_op.create_index("ix_experiment_records_environment_version_id", ["environment_version_id"])


def downgrade() -> None:
    # 只删除新增业务绑定字段（逆序：先索引/外键后列）；保留控制面表与 Docker 镜像。
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_index("ix_assignments_environment_version_id")
        batch_op.drop_constraint("fk_assignments_env_version", type_="foreignkey")
        batch_op.drop_column("allowed_imports")
        batch_op.drop_column("import_policy_mode")
        batch_op.drop_column("environment_version_id")

    with op.batch_alter_table("judge_questions") as batch_op:
        batch_op.drop_index("ix_judge_questions_environment_version_id")
        batch_op.drop_constraint("fk_judge_questions_env_version", type_="foreignkey")
        batch_op.drop_column("allowed_imports")
        batch_op.drop_column("import_policy_mode")
        batch_op.drop_column("environment_version_id")

    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_index("ix_submissions_environment_version_id")
        batch_op.drop_constraint("fk_submissions_env_version", type_="foreignkey")
        batch_op.drop_column("allowed_imports_snapshot")
        batch_op.drop_column("import_policy_mode_snapshot")
        batch_op.drop_column("environment_version_id")

    with op.batch_alter_table("notebook_templates") as batch_op:
        batch_op.drop_index("ix_notebook_templates_draft_environment_version_id")
        batch_op.drop_constraint("fk_notebook_templates_env_version", type_="foreignkey")
        batch_op.drop_column("draft_allowed_imports")
        batch_op.drop_column("draft_import_policy_mode")
        batch_op.drop_column("draft_environment_version_id")

    with op.batch_alter_table("notebook_template_versions") as batch_op:
        batch_op.drop_index("ix_template_versions_environment_version_id")
        batch_op.drop_constraint("fk_template_versions_env_version", type_="foreignkey")
        batch_op.drop_column("allowed_imports")
        batch_op.drop_column("import_policy_mode")
        batch_op.drop_column("environment_version_id")

    with op.batch_alter_table("experiment_records") as batch_op:
        batch_op.drop_index("ix_experiment_records_environment_version_id")
        batch_op.drop_constraint("fk_experiment_records_env_version", type_="foreignkey")
        batch_op.drop_column("environment_version_id")
