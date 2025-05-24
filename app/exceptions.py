# app/exceptions.py
from fastapi import HTTPException, status, Request
from fastapi.responses import JSONResponse

class DALError(Exception):
    """Base exception for Data Access Layer errors."""
    def __init__(self, message="Database operation failed", detail=None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)

class NotFoundError(DALError):
    """Raised when a specific resource is not found in the database."""
    def __init__(self, message="Resource not found"):
        super().__init__(message)

class IntegrityError(DALError):
    """Raised when a database integrity constraint is violated (e.g., duplicate unique key)."""
    def __init__(self, message="Integrity constraint violation"):
        super().__init__(message)

# ... 您可以根据业务需求添加更多特定异常，例如 AuthorizationError, ValidationError (for business logic)

# FastAPI 异常处理器 - 确保将 DAL 异常转换为标准 HTTP 响应
async def not_found_exception_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.message}
    )

async def integrity_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, # Conflict
        content={"message": exc.message}
    )

async def dal_exception_handler(request: Request, exc: DALError):
    # 捕获所有未被更具体处理器捕获的 DAL 错误
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": f"An unexpected database error occurred: {exc.message}"}
    )

# 映射 SQLSTATE 错误码到自定义异常 (在 dal/base.py 中使用)
SQLSTATE_ERROR_MAP = {
    '23000': IntegrityError, # Integrity Constraint Violation (通用)
    '23001': IntegrityError, # Restrict Violation
    '23502': IntegrityError, # Not Null Violation
    '23503': IntegrityError, # Foreign Key Violation
    '23505': IntegrityError, # Unique Violation
    # 可以在这里添加更具体的 SQL Server 错误码
    # 例如，对于重复键错误，SQL Server 可能是 2627 或 2601
    '2627': IntegrityError, # Unique constraint violation (SQL Server)
    '2601': IntegrityError, # Cannot insert duplicate key (SQL Server)
} 