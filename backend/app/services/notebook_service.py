"""
Notebook 业务编排层 — 组合 parser、kernel_manager，提供完整 notebook 操作
"""
import json
import os
import shutil
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lesson, NotebookRecord, NotebookSubmission, User
from app.services.kernel_manager import get_kernel_manager
from app.services.notebook_parser import parse_and_normalize


class NotebookService:
    def __init__(self, db: Session):
        self.db = db
        self.kernel_manager = get_kernel_manager()
        # storage 根目录
        self.storage_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "storage", "notebooks",
        )

    def _get_lesson(self, lesson_id: int) -> Lesson:
        lesson = self.db.get(Lesson, lesson_id)
        if not lesson or lesson.content_type != "notebook":
            raise ValueError(f"课时 {lesson_id} 不存在或不是 notebook 类型")
        return lesson

    def _get_storage_dir(self, lesson_id: int, template_hash: str) -> str:
        return os.path.join(self.storage_root, str(lesson_id), "versions", template_hash)

    # ── 教师端 ──────────────────────────────────────────────────

    def upload_notebook(self, lesson_id: int, file_path: str, user: User):
        """
        教师上传 .ipynb 或 .zip 文件。
        解析 → 归一化 → 存入版本化目录 → 更新 Lesson.notebook_path
        """
        lesson = self.db.get(Lesson, lesson_id)
        if not lesson:
            raise ValueError(f"课时 {lesson_id} 不存在")

        # 先解析到临时目录
        temp_dir = self._get_storage_dir(lesson_id, "temp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".zip":
            from app.services.notebook_parser import parse_experiment_package
            result = parse_experiment_package(file_path, temp_dir)
        else:
            result = parse_and_normalize(file_path, temp_dir)

        template_hash = result["template_hash"]

        # 移动到版本化目录
        dest_dir = self._get_storage_dir(lesson_id, template_hash)
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.move(temp_dir, dest_dir)

        # 更新 lesson
        lesson.notebook_path = dest_dir
        lesson.content_type = "notebook"
        self.db.commit()

        # 更新 current.json
        current_file = os.path.join(self.storage_root, str(lesson_id), "current.json")
        os.makedirs(os.path.dirname(current_file), exist_ok=True)
        current_data = {}
        if os.path.exists(current_file):
            with open(current_file) as f:
                current_data = json.load(f)
        versions = current_data.get("versions", [])
        if template_hash not in versions:
            versions.append(template_hash)
        current_data["latest_hash"] = template_hash
        current_data["versions"] = versions
        with open(current_file, "w") as f:
            json.dump(current_data, f)

        return {"template_hash": template_hash, "lesson_id": lesson_id}

    # ── 学生端 ──────────────────────────────────────────────────

    def get_or_create_record(self, lesson_id: int, student_id: int) -> NotebookRecord:
        """获取或创建学生 notebook 副本"""
        lesson = self._get_lesson(lesson_id)

        # 查找已有记录
        record = self.db.scalar(
            select(NotebookRecord).where(
                NotebookRecord.lesson_id == lesson_id,
                NotebookRecord.student_id == student_id,
            )
        )
        if record:
            return record

        # 首次创建：解析教师模板
        if not lesson.notebook_path or not os.path.isdir(lesson.notebook_path):
            raise ValueError("该课时尚未上传课件")

        notebook_file = os.path.join(lesson.notebook_path, "lesson.ipynb")
        if not os.path.exists(notebook_file):
            raise ValueError("课件文件不存在")

        result = parse_and_normalize(
            notebook_file,
            lesson.notebook_path,
        )

        record = NotebookRecord(
            lesson_id=lesson_id,
            student_id=student_id,
            status="started",
            template_version=1,
            template_hash=result["template_hash"],
            cells_sources={
                cid: cell["source"]
                for cid, cell in result["cells"].items()
                if cell["cell_type"] == "code"
            },
            cells_outputs={
                cid: (cell.get("outputs") or {})
                for cid, cell in result["cells"].items()
                if cell["cell_type"] == "code"
            },
            cell_order=result["cell_order"],
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_notebook_data(self, lesson_id: int, student_id: int) -> dict:
        """获取完整的 notebook 数据（含学生状态）"""
        lesson = self._get_lesson(lesson_id)
        record = self.get_or_create_record(lesson_id, student_id)

        # 构建返回数据
        notebook_file = os.path.join(lesson.notebook_path, "lesson.ipynb")
        if os.path.exists(notebook_file):
            result = parse_and_normalize(notebook_file, lesson.notebook_path)
        else:
            result = {"cells": {}, "cell_order": []}

        # 合并学生修改
        cells_out = []
        for cell_id in record.cell_order:
            cell = result["cells"].get(cell_id, {})
            entry = {
                "id": cell_id,
                "cell_type": cell.get("cell_type", "code"),
                "source": record.cells_sources.get(cell_id, cell.get("source", "")),
                "rendered_html": cell.get("rendered_html"),
                "outputs": record.cells_outputs.get(cell_id),
                "execution_count": None,
                "status": None,
            }
            cells_out.append(entry)

        # 检查模板是否过期
        current_hash = result.get("template_hash", "")
        template_outdated = (
            record.template_hash and
            current_hash and
            record.template_hash != current_hash
        )

        return {
            "record_id": record.id,
            "lesson_id": lesson_id,
            "status": record.status,
            "cells": cells_out,
            "cell_order": record.cell_order,
            "template_outdated": template_outdated,
        }

    def save_cells(self, record_id: int, student_id: int, cells: dict[str, str]):
        """保存学生修改的代码"""
        record = self._get_record(record_id, student_id)
        record.cells_sources = cells
        self.db.commit()

    def execute_cell(self, record_id: int, student_id: int, cell_id: str, code: str) -> dict:
        """执行单个代码 cell 并保存输出"""
        record = self._get_record(record_id, student_id)

        # 更新 code
        record.cells_sources[cell_id] = code

        # 执行
        lesson_storage_dir = record.lesson.notebook_path or ""
        self.kernel_manager.get_or_create_session(record_id, lesson_storage_dir)

        result = self.kernel_manager.execute(record_id, code)

        # 保存 outputs
        record.cells_outputs[cell_id] = {
            "outputs": result["outputs"],
            "execution_time_ms": result["execution_time_ms"],
        }
        self.db.commit()

        return result

    def reset_to_template(self, record_id: int, student_id: int):
        """重置为教师模板"""
        record = self._get_record(record_id, student_id)
        lesson = record.lesson

        if not lesson.notebook_path:
            raise ValueError("课件路径不存在")

        notebook_file = os.path.join(lesson.notebook_path, "lesson.ipynb")
        result = parse_and_normalize(notebook_file, lesson.notebook_path)

        record.cells_sources = {
            cid: cell["source"]
            for cid, cell in result["cells"].items()
            if cell["cell_type"] == "code"
        }
        record.cells_outputs = {}
        record.template_hash = result["template_hash"]
        self.db.commit()

        # 重启 kernel
        self.kernel_manager.restart(record_id, lesson.notebook_path or "")

    def submit(self, record_id: int, student_id: int) -> NotebookSubmission:
        """提交笔记本：生成不可变快照"""
        record = self._get_record(record_id, student_id)

        # 计算 attempt_number
        max_attempt = self.db.scalar(
            select(NotebookSubmission.attempt_number)
            .where(NotebookSubmission.record_id == record_id)
            .order_by(NotebookSubmission.attempt_number.desc())
        ) or 0
        attempt = max_attempt + 1

        # 创建快照
        snapshot = {
            "cells_sources": dict(record.cells_sources),
            "cells_outputs": dict(record.cells_outputs),
            "cell_order": list(record.cell_order),
            "template_hash": record.template_hash,
            "template_version": record.template_version,
        }

        sub = NotebookSubmission(
            record_id=record_id,
            attempt_number=attempt,
            cells_snapshot=snapshot,
            submitted_at=datetime.now(timezone.utc),
        )
        self.db.add(sub)
        record.status = "submitted"
        record.submitted_at = sub.submitted_at
        self.db.commit()
        self.db.refresh(sub)

        return sub

    def upgrade_template(self, record_id: int, student_id: int, action: str):
        """处理模板升级"""
        record = self._get_record(record_id, student_id)

        if action == "discard":
            # 放弃当前进度，加载新版
            self.reset_to_template(record_id, student_id)
        elif action == "keep":
            # 保留旧版，只更新 template_hash 指向（但实际继续用旧文件）
            pass

    # ── 内部 ────────────────────────────────────────────────────

    def _get_record(self, record_id: int, student_id: int) -> NotebookRecord:
        """获取记录并校验所有权"""
        record = self.db.get(NotebookRecord, record_id)
        if not record:
            raise ValueError(f"记录 {record_id} 不存在")
        if record.student_id != student_id:
            raise PermissionError("无权访问此记录")
        return record
