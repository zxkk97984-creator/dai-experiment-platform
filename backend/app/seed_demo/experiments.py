# -*- coding: utf-8 -*-
"""实验模块：Notebook 模板（含版本）、实验模块、实验记录、实验提交。

模板与版本之间是循环外键（current_version_id 与 versions 引用同一张表），
插入顺序：先建 template（current_version_id=None）→ flush → 建 version →
回填 template.current_version_id → flush。
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ExperimentModule,
    ExperimentRecord,
    ExperimentSubmission,
    Lesson,
    NotebookTemplate,
    NotebookTemplateVersion,
    User,
)

from .constants import ARCHETYPES, BACKGROUND_ARCHETYPE, FIXED_STUDENT_DEFS
from .marks import mark
from .rng import make_rng
from .tasks import EXPERIMENT_SPECS
from .timeline import DemoClock

logger = logging.getLogger("dai.seed_demo.experiments")


def _experiment_cells(spec: dict) -> list[dict]:
    return [
        {
            "id": "intro",
            "type": "markdown",
            "source": f"# {spec['name']}\n\n{spec['objective']}\n\n预期输出：{spec['expected']}",
            "order": 0,
            "student_editable": False,
            "source_hidden": False,
        },
        {
            "id": "setup",
            "type": "code",
            "source": spec["setup"],
            "order": 1,
            "student_editable": False,
            "source_hidden": True,
        },
        {
            "id": "exercise",
            "type": "code",
            "source": spec["exercise"],
            "order": 2,
            "student_editable": True,
            "source_hidden": False,
        },
        {
            "id": "reflection",
            "type": "markdown",
            "source": "## 实验报告\n记录一次运行结果、一个边界条件和一个你认为值得改进的实现细节。",
            "order": 3,
            "student_editable": False,
            "source_hidden": False,
        },
    ]


def create_experiments(
    db: Session, clock: DemoClock, users: dict, env_by_slug: dict,
) -> dict:
    """创建 Notebook 模板 + 实验模块。返回 {"templates": [...], "modules": [...], "versions_by_template": {...}}。"""
    teacher = users["teacher_zhang"]
    env = env_by_slug["basic"]
    templates: list[NotebookTemplate] = []
    modules: list[ExperimentModule] = []
    versions_by_template: dict[int, NotebookTemplateVersion] = {}

    for index, spec in enumerate(EXPERIMENT_SPECS):
        cells = _experiment_cells(spec)
        cell_order = [c["id"] for c in cells]
        digest = hashlib.sha256(
            json.dumps(cells, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        template = db.scalar(
            select(NotebookTemplate).where(NotebookTemplate.name == spec["name"])
        )
        created = template is None
        if created:
            template = NotebookTemplate(
                name=spec["name"],
                description=spec["objective"],
                status="published",
                owner_id=teacher.id,
                draft_cells=cells,
                draft_revision=1,
                draft_metadata={"seed": True, "environment": "basic"},
                draft_assets_dir=None,
                draft_environment_version_id=env.id,
                draft_import_policy_mode="restricted",
                draft_allowed_imports=spec["imports"],
            )
            db.add(template)
            db.flush()
            logger.info("[创建] 实验模板 %s", spec["name"])
        else:
            template.status = "published"
            template.owner_id = teacher.id
            template.draft_cells = cells
            template.draft_environment_version_id = env.id
            db.flush()
            logger.info("[更新] 实验模板 %s", spec["name"])
        mark(db, "notebook_templates", template.id)
        templates.append(template)

        # 版本 v1（不可变快照）
        version = db.scalar(
            select(NotebookTemplateVersion).where(
                NotebookTemplateVersion.template_id == template.id,
                NotebookTemplateVersion.version_number == 1,
            )
        )
        if version is None:
            version = NotebookTemplateVersion(
                template_id=template.id,
                version_number=1,
                sha256=digest,
                cells=cells,
                cell_order=cell_order,
                notebook_metadata={"seed": True, "environment": "basic"},
                assets_dir=None,
                published_by_id=teacher.id,
                environment_version_id=env.id,
                import_policy_mode="restricted",
                allowed_imports=spec["imports"],
            )
            db.add(version)
            db.flush()
            logger.info("[创建] 模板版本 %s v1", spec["name"])
        mark(db, "notebook_template_versions", version.id)
        versions_by_template[template.id] = version
        if template.current_version_id != version.id:
            template.current_version_id = version.id
            db.flush()

        # 实验模块
        module = db.scalar(
            select(ExperimentModule).where(ExperimentModule.name == spec["name"])
        )
        if module is None:
            module = ExperimentModule(
                name=spec["name"],
                description=spec["objective"],
                template_id=template.id,
                owner_id=teacher.id,
                status="published",
            )
            db.add(module)
            db.flush()
            logger.info("[创建] 实验模块 %s", spec["name"])
        else:
            module.template_id = template.id
            module.owner_id = teacher.id
            module.status = "published"
            db.flush()
            logger.info("[更新] 实验模块 %s", spec["name"])
        mark(db, "experiment_modules", module.id)
        modules.append(module)

    db.flush()
    return {
        "templates": templates,
        "modules": modules,
        "versions_by_template": versions_by_template,
    }


def create_experiment_records(
    db: Session, clock: DemoClock, users: dict, experiments: dict, courses: dict,
) -> None:
    """为学生创建实验记录与提交（实验模块维度）。

    画像学生按画像 experiment_level 控制；背景学生按固定种子抽样。
    """
    modules = experiments["modules"]
    versions_by_template = experiments["versions_by_template"]
    students: list[User] = users["students"]
    archetype_map = {uname: a for uname, _n, a in FIXED_STUDENT_DEFS}

    for module in modules:
        template = db.get(NotebookTemplate, module.template_id)
        if template is None:
            continue
        version = versions_by_template.get(template.id)
        if version is None:
            continue
        cells_sources = {c["id"]: c["source"] for c in (version.cells or [])}

        for student in students:
            rng = make_rng("experiment", student.username, module.name)
            archetype = archetype_map.get(student.username, BACKGROUND_ARCHETYPE)
            profile = ARCHETYPES[archetype]
            # 新学生 / 困难学生只做前 2 个模块
            if archetype in ("new", "struggling") and module is modules[0]:
                level = 1
            else:
                # 0~1 之间按画像权重决定是否做该模块
                level = profile["experiment_level"]
            if level == 0 or rng.random() > (level / 3.0):
                continue

            record = db.scalar(
                select(ExperimentRecord).where(
                    ExperimentRecord.module_id == module.id,
                    ExperimentRecord.student_id == student.id,
                )
            )
            start_time = _random_time_before_ref(clock, rng)
            if record is None:
                record = ExperimentRecord(
                    module_id=module.id,
                    template_version_id=version.id,
                    student_id=student.id,
                    status="started",
                    cells_sources=cells_sources,
                    record_revision=1,
                    started_at=start_time,
                    environment_version_id=version.environment_version_id,
                )
                db.add(record)
                db.flush()
                logger.info("[创建] 实验记录 %s / %s", student.username, module.name)
            else:
                record.environment_version_id = version.environment_version_id
                db.flush()
            mark(db, "experiment_records", record.id)

            # 状态推进：started -> submitted -> graded（按画像）
            if level >= 2:
                submitted = _random_time_after(clock, rng, start_time)
                record.status = "submitted"
                record.submitted_at = submitted
                # 提交记录（每个学生每模块 1 次提交）
                sub = db.scalar(
                    select(ExperimentSubmission).where(
                        ExperimentSubmission.record_id == record.id,
                        ExperimentSubmission.attempt_number == 1,
                    )
                )
                if sub is None:
                    sub = ExperimentSubmission(
                        record_id=record.id,
                        attempt_number=1,
                        client_request_id=f"demo-{record.id}-1",
                        cells_snapshot={"cells": cells_sources},
                        submitted_at=submitted,
                    )
                    db.add(sub)
                    db.flush()
                    logger.info("[创建] 实验提交 %s / %s", student.username, module.name)
                mark(db, "experiment_submissions", sub.id)

                # 教师复核：elite 全部已复核；average/background 约半数；struggling 少量
                reviewed = rng.random() < {
                    "elite": 1.0, "average": 0.5, "struggling": 0.2, "new": 0.3,
                }.get(archetype, 0.5)
                if reviewed:
                    score = rng.randint(60, 100) if archetype != "struggling" else rng.randint(40, 70)
                    sub.score = score
                    sub.feedback = "实现正确，逻辑清晰，继续保持！" if score >= 85 else "整体不错，注意边界情况处理。"
                    sub.reviewed_by_id = users["teacher_zhang"].id
                    sub.reviewed_at = _random_time_after(clock, rng, submitted)
                    record.status = "graded"
                    record.completed_at = sub.reviewed_at
    db.flush()


def _random_time_before_ref(clock: DemoClock, rng):
    start, end = clock.experiment_activity_window()
    span = (end - start).total_seconds()
    return start + timedelta(seconds=rng.uniform(0, span))


def _random_time_after(clock: DemoClock, rng, after):
    start, end = clock.experiment_activity_window()
    span = (end - start).total_seconds()
    t = start + timedelta(seconds=rng.uniform(0, span))
    return t if t > after else after + timedelta(hours=rng.randint(1, 24))
