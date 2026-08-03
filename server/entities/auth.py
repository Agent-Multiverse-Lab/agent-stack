"""认证接口的请求与响应 Schema。"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """用户登录请求。"""

    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    """认证接口返回的用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    uid: str
    email: EmailStr
    is_active: bool


class TokenResponse(BaseModel):
    """登录成功后的访问令牌。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
