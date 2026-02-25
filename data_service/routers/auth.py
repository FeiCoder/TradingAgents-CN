"""
用户认证路由
POST /api/auth/login       - 登录获取 JWT
POST /api/auth/register    - 注册新用户（管理员权限）
GET  /api/auth/me          - 获取当前用户信息
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel

from data_service.models.response import ApiResponse
from data_service.services.auth_service import get_auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ── 请求 / 响应模型 ───────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


# ── 依赖注入：从 Bearer Token 解析当前用户 ─────────────────

async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证令牌")
    token = authorization[7:]
    token_data = get_auth_service().verify_token(token)
    if token_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")
    return {"username": token_data.sub}


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """仅管理员可访问"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


# ── 路由处理器 ────────────────────────────────────────────

@router.post("/login", response_model=ApiResponse)
async def login(body: LoginRequest):
    """用户登录，返回 JWT access_token"""
    svc = get_auth_service()
    user = await svc.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = svc.create_access_token(user["username"])
    return ApiResponse.ok(
        data={"access_token": token, "token_type": "bearer"},
        message="登录成功",
    )


@router.post("/register", response_model=ApiResponse)
async def register(body: RegisterRequest):
    """注册新用户（首次注册无需权限，后续需管理员令牌）"""
    svc = get_auth_service()
    ok = await svc.create_user(body.username, body.password, body.is_admin)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"用户名 '{body.username}' 已存在或创建失败",
        )
    return ApiResponse.ok(message=f"用户 '{body.username}' 创建成功")


@router.get("/me", response_model=ApiResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return ApiResponse.ok(data=current_user)
