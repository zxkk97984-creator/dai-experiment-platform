from fastapi import APIRouter

from .assignments import router as assignments_router
from .auth import router as auth_router
from .courses import router as courses_router
from .exams import router as exams_router
from .experiments import router as experiments_router
from .judge import router as judge_router
from .jupyter import router as jupyter_router
from .users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(courses_router)
api_router.include_router(assignments_router)
api_router.include_router(judge_router)
api_router.include_router(exams_router)
api_router.include_router(experiments_router)
api_router.include_router(jupyter_router)
