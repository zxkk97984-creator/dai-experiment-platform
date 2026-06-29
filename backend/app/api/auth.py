from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_current_payload, get_current_user, get_db, get_redis_client
from app.models import User
from app.schemas import LoginRequest, LogoutRequest, RefreshRequest, TokenResponse, UserRead
from app.services.auth_service import authenticate_user, issue_token_pair, refresh_token_pair, revoke_tokens

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    user = authenticate_user(db, payload.username, payload.password)
    return issue_token_pair(user, redis_client, settings)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    return refresh_token_pair(db, payload.refresh_token, redis_client, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    response: Response,
    access_payload: dict = Depends(get_current_payload),
    redis_client=Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    revoke_tokens(access_payload, payload.refresh_token, redis_client, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
