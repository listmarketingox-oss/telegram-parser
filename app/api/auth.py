from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import AppUser
from app.schemas.user import LoginRequest, TokenResponse, UserResponse
from app.services.auth import authenticate_user, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return TokenResponse(message="ok")


@router.post("/logout", response_model=TokenResponse)
async def logout(response: Response):
    response.delete_cookie("access_token")
    return TokenResponse(message="ok")


@router.get("/me", response_model=UserResponse)
async def me(user: AppUser = Depends(get_current_user)):
    return user
