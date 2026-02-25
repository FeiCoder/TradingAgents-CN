"""统一 API 响应模型"""

from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """标准 API 响应封装"""
    success: bool = True
    data: Optional[Any] = None
    message: str = ""
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "success") -> "ApiResponse":
        return cls(success=True, data=data, message=message)

    @classmethod
    def fail(cls, error: str, message: str = "failed") -> "ApiResponse":
        return cls(success=False, error=error, message=message)
