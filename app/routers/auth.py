# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
import pyodbc
from uuid import UUID

from app.schemas.user_schemas import (
    UserRegisterSchema,
    UserLoginSchema, # Keep for schema definition reference if needed elsewhere, but not for login input
    UserResponseSchema,
    Token,
    VerifyEmail,
    RequestVerificationEmail,
    UserPasswordUpdate # Ensure all necessary schemas are imported
)
from app.services.user_service import UserService
from app.dal.connection import get_db_connection # Import the DB connection dependency
from app.dependencies import get_user_service # Import the Service dependency
from app.exceptions import AuthenticationError, ForbiddenError, IntegrityError, DALError # Import exceptions

from fastapi.security import OAuth2PasswordRequestForm # Import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserResponseSchema, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterSchema,
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    新用户注册。
    """
    try:
        # Call Service layer function, passing the connection
        created_user = await user_service.create_user(conn, user_data)
        return created_user
    except IntegrityError as e:
        # Catch specific DAL errors and convert to HTTP exceptions
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DALError as e:
        # Catch other DAL errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), # Use OAuth2PasswordRequestForm for form data
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    用户登录并获取 JWT Token。
    """
    try:
        # Call Service layer function, passing the connection
        # Service returns the access token string
        access_token_string = await user_service.authenticate_user_and_create_token(conn, form_data.username, form_data.password)
        
        # If authentication fails, service.authenticate_user_and_create_token should ideally raise an exception
        # If it returns None or similar on failure, handle that case
        if not access_token_string:
             # This case might be covered by exceptions from Service, but as a safeguard
             raise HTTPException(
                 status_code=status.HTTP_401_UNAUTHORIZED,
                 detail="用户名或密码不正确",
                 headers={"WWW-Authenticate": "Bearer"},
             )

        return {"access_token": access_token_string, "token_type": "bearer"}
    except (AuthenticationError, ForbiddenError) as e:
         # Catch authentication and forbidden errors from Service
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_403_FORBIDDEN,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"} if isinstance(e, AuthenticationError) else None
        )
    except DALError as e:
        # Catch DAL errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.post("/request-verification-email", status_code=status.HTTP_200_OK)
async def request_verification_email_api(
    request_data: RequestVerificationEmail,
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    请求发送邮箱验证邮件。
    如果邮箱存在且未认证，则生成并发送验证链接。如果已认证或不存在，行为取决于存储过程。
    """
    try:
        # Call Service layer function, passing the connection
        await user_service.request_verification_email(conn, request_data.email)
        # The service/DAL handles the logic and potential errors (like disabled account)
        # If it reaches here without raising an exception, we assume the request was processed.
        # Returning a generic success message is good practice to prevent email enumeration.
        return {"message": "如果邮箱存在或已注册，验证邮件已发送。请检查您的收件箱。"}
    except DALError as e:
        # Catch specific DAL errors from Service
        # For disabled account error specifically:
        if "账户已被禁用" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"请求验证邮件失败: {e}")
        # Handle other potential DAL errors as 500 or another appropriate status
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except (AuthenticationError, ForbiddenError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        # Catch other unexpected errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email_api(
    verify_data: VerifyEmail,
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    使用邮箱验证令牌进行验证。
    """
    try:
        # Call Service layer function, passing the connection
        verification_result = await user_service.verify_email(conn, verify_data.token)

        # Service/DAL handles the verification logic and raises errors for invalid/expired token or disabled account.
        # If it reaches here, verification was successful.
        # The service returns a dict with UserID, IsVerified=True on success.

        # Ensure the service returned a successful verification result
        if verification_result and verification_result.get('IsVerified') is True:
             return {"message": "邮箱验证成功！您现在可以登录。", "user_id": str(verification_result.get('UserID')), "is_verified": True}
        else:
             # This case should ideally be covered by Service/DAL raising an exception
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="邮箱验证失败：内部处理异常。")

    except DALError as e:
        # Catch specific DAL errors from Service
        if "魔术链接无效或已过期" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"邮箱验证失败: {e}")
        if "账户已被禁用" in str(e):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"邮箱验证失败: {e}")
        # Handle other potential DAL errors as 500 or another appropriate status
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except (AuthenticationError, ForbiddenError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        # Catch other unexpected errors
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Note: We need to add the authenticate_user_and_create_token method to UserService 
# and ensure it handles the logic of calling DAL and creating the token. 