"""
[已废弃] Notebook 业务编排层

所有功能已迁移至：
- backend/app/api/experiments.py（学生端记录管理 + Cell 执行）
- backend/app/api/studio.py（教师端 Studio，第三阶段实现）
- backend/app/services/experiment_service.py（业务逻辑，待创建）

此文件仅保留空类定义以避免导入链断裂，请勿在此添加新代码。
"""
from sqlalchemy.orm import Session


class NotebookService:
    """[已废弃] 请使用新 API /api/v1/experiments 和 /api/v1/studio"""

    def __init__(self, db: Session):
        self.db = db
        raise NotImplementedError(
            "NotebookService 已废弃。请使用 /api/v1/experiments 统一 API。"
            "教师上传 Notebook 请使用 /api/v1/studio。"
        )
