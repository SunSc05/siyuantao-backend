# app/routers/users.py
from fastapi import APIRouter, Depends, status, HTTPException
# from app.schemas.user_schemas import UserCreate, UserResponse, UserLogin, Token, UserUpdate, RequestVerificationEmail, VerifyEmail, UserPasswordUpdate # Import schemas from here
from app.schemas.user_schemas import (
    UserResponseSchema, 
    UserProfileUpdateSchema, 
    UserPasswordUpdate, # Import necessary schemas
    UserStatusUpdateSchema, # Added for new admin endpoint
    UserCreditAdjustmentSchema, # Added for new admin endpoint
    RequestVerificationEmail # Import the schema for requesting verification email
)
# from app.dal import users as user_dal # No longer needed
# from app.services import user_service # No longer needed (using dependency)
from app.services.user_service import UserService # Import Service class for type hinting
from app.dal.connection import get_db_connection
# from app.exceptions import NotFoundError, IntegrityError, DALError # Import exceptions directly or via dependencies
import pyodbc
from uuid import UUID
# from datetime import timedelta # Not directly needed in router for this logic

# Import auth dependencies from dependencies.py
from app.dependencies import (
    get_current_user, # For authenticated endpoints
    get_current_active_admin_user, # For admin-only endpoints
    get_user_service, # Dependency for UserService
    get_current_authenticated_user, # For active authenticated users
    get_current_super_admin_user # Added for super admin authentication
)
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError # Import necessary exceptions

import logging # Import logging
logger = logging.getLogger(__name__) # Get logger instance

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponseSchema)
async def read_users_me(
    # current_user: dict = Depends(get_current_user) # Requires JWT authentication
    current_user: dict = Depends(get_current_authenticated_user), # Use dependency from dependencies.py - ensures user is active
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    获取当前登录用户的个人资料。
    """
    # get_current_authenticated_user dependency should provide the user ID (e.g., in a dict)
    # It also ensures the user is active and handles exceptions.
    user_id = current_user['user_id'] # Access user_id from the dependency's dictionary result

    try:
        # Call Service layer function, passing the connection and user_id
        user_profile = await user_service.get_user_profile_by_id(conn, user_id) # Pass user_id directly (expected to be UUID)
        return user_profile
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # Authentication and Forbidden errors are handled by get_current_authenticated_user dependency
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/me", response_model=UserResponseSchema)
async def update_current_user_profile(
    user_update_data: UserProfileUpdateSchema, # Request body here
    # current_user: dict = Depends(get_current_user) # Requires JWT authentication
    current_user: UserResponseSchema = Depends(get_current_authenticated_user), # Use dependency from dependencies.py
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    更新当前登录用户的个人资料 (不包括密码)。
    """
    user_id = current_user['user_id'] # Access user_id from the dependency's dictionary result

    try:
        # Call Service layer function, passing the connection and user_id
        updated_user = await user_service.update_user_profile(conn, user_id, user_update_data) # Pass user_id directly (expected to be UUID)
        return updated_user # Service should return the updated user profile
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    # Authentication and Forbidden errors are handled by get_current_authenticated_user dependency
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_current_user_password(
    password_update_data: UserPasswordUpdate, # Request body here
    # current_user: dict = Depends(get_current_user) # Requires JWT authentication
    current_user: UserResponseSchema = Depends(get_current_authenticated_user), # Use dependency from dependencies.py
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    更新当前登录用户的密码。
    """
    user_id = current_user['user_id'] # Access user_id from the dependency's dictionary result

    try:
        # Call Service layer function, passing the connection and user_id
        update_success = await user_service.update_user_password(conn, user_id, password_update_data) # Pass user_id directly (expected to be UUID)
        # Service.update_user_password should return True on success and raise exception on failure
        if not update_success:
             # This case should ideally be covered by exceptions from Service, but as a safeguard
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="密码更新失败")

        # Password update successful returns 204 No Content
        return {}
    except (NotFoundError, AuthenticationError, DALError, ForbiddenError) as e:
         # Catch specific errors from Service
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else
                           (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else
                            (status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else status.HTTP_500_INTERNAL_SERVER_ERROR)),
             detail=str(e),
             # Include WWW-Authenticate header for AuthenticationError (401)
             headers={"WWW-Authenticate": "Bearer"} if isinstance(e, AuthenticationError) else None
         )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Admin endpoints for user management by ID

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_profile_by_id(
    user_id: UUID, # Path parameter here
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service), # Inject Service
    # Note: Authentication check is handled by the dependency itself.
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 获取用户个人资料。
    """
    try:
        # Call Service layer function, passing the connection
        user = await user_service.get_user_profile_by_id(conn, user_id) # Pass user_id directly
        return user
    except NotFoundError as e:
        # This exception is raised by the Service layer if user is not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (AuthenticationError, ForbiddenError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_403_FORBIDDEN, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user_profile_by_id(
    user_id: UUID, # Path parameter here
    user_update_data: UserProfileUpdateSchema, # Request body here
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service), # Inject Service
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 更新用户个人资料。
    """
    try:
        # Call Service layer function, passing the connection
        updated_user = await user_service.update_user_profile(conn, user_id, user_update_data) # Pass user_id directly
        return updated_user
    except (NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else
                          (status.HTTP_409_CONFLICT if isinstance(e, IntegrityError) else
                           (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else
                            (status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else status.HTTP_500_INTERNAL_SERVER_ERROR))),
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(
    user_id: UUID, # Path parameter here
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service), # Inject Service
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 删除用户。
    """
    try:
        # Call Service layer function, passing the connection
        await user_service.delete_user(conn, user_id) # Pass user_id directly
        return {} # 204 No Content returns an empty body
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (AuthenticationError, ForbiddenError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_403_FORBIDDEN, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Removed email verification routes as they are in auth.py
# @router.post("/request-verification-email", status_code=status.HTTP_200_OK)
# async def request_verification_email_api(

# TODO: Add admin-only endpoints for user management like listing all users, disabling/enabling accounts, etc. 

# Admin endpoint to get all users
@router.get("/", response_model=list[UserResponseSchema])
async def get_all_users_api(
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: UserService = Depends(get_user_service),
    current_admin_user: dict = Depends(get_current_active_admin_user) # Requires admin authentication
):
    """
    管理员获取所有用户列表。
    """
    try:
        admin_id = current_admin_user.get('UserID') or current_admin_user.get('user_id')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法获取管理员用户信息")

        users = await user_service.get_all_users(conn, admin_id) # Pass admin_id directly
        return users
    except (ForbiddenError, DALError, AuthenticationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else 
                          (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Admin endpoint to change user status
@router.put("/{user_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def change_user_status_by_id(
    user_id: UUID, # Path parameter here
    status_update_data: UserStatusUpdateSchema, # Request body here
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: UserService = Depends(get_user_service),
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 更改用户状态（禁用/启用）。
    """
    try:
        admin_id = current_admin_user.get('UserID') or current_admin_user.get('user_id')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法获取管理员用户信息")
        
        await user_service.change_user_status(conn, user_id, status_update_data.status, admin_id) # Pass admin_id directly
        return {} # 204 No Content
    except (ForbiddenError, DALError, AuthenticationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else 
                          (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else 
                            (status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_500_INTERNAL_SERVER_ERROR)),
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Super Admin endpoint to toggle user staff status
@router.put("/{user_id}/toggle_staff", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_user_staff_status(
    user_id: UUID, # Path parameter
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: UserService = Depends(get_user_service),
    current_super_admin: dict = Depends(get_current_super_admin_user) # Requires super admin authentication
):
    """
    超级管理员切换用户的管理员 (is_staff) 状态。
    """
    try:
        super_admin_id = current_super_admin.get('UserID') or current_super_admin.get('user_id')
        if not super_admin_id:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法获取超级管理员用户信息")

        # Call a new Service method to toggle is_staff status
        # This service method will need to fetch the user, check current status, and update it.
        await user_service.toggle_user_staff_status(conn, user_id, super_admin_id)

        return {} # 204 No Content

    except (NotFoundError, ForbiddenError, DALError) as e:
        # Corrected error handling structure
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if isinstance(e, NotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(e, ForbiddenError):
            status_code = status.HTTP_403_FORBIDDEN
        # DALError defaults to 500

        raise HTTPException(
             status_code=status_code,
             detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Admin endpoint to adjust user credit
@router.put("/{user_id}/credit", status_code=status.HTTP_204_NO_CONTENT)
async def adjust_user_credit_by_id(
    user_id: UUID, # Path parameter here
    credit_adjustment_data: UserCreditAdjustmentSchema, # Request body here
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: UserService = Depends(get_user_service),
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 调整用户信用分。
    """
    try:
        admin_id = current_admin_user.get('UserID') or current_admin_user.get('user_id')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法获取管理员用户信息")
            
        await user_service.adjust_user_credit(conn, user_id, credit_adjustment_data.credit_adjustment, admin_id, credit_adjustment_data.reason) # Pass admin_id directly
        return {} # 204 No Content
    except (NotFoundError, ForbiddenError, DALError, AuthenticationError) as e:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else 
                           (status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else 
                            (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_500_INTERNAL_SERVER_ERROR)),
             detail=str(e)
         )
    except ValueError as e:
        # Catch ValueError from Service layer (e.g., invalid status, credit limit, missing reason)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DALError as e:
        # Catch DAL errors that were not specifically handled before
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# New endpoint for requesting student verification email
@router.post("/me/request-student-verification-email", status_code=status.HTTP_200_OK, summary="请求学生身份验证邮件")
async def request_student_email_verification_api(
    request_data: RequestVerificationEmail, # Reuse RequestVerificationEmail schema
    current_user: UserResponseSchema = Depends(get_current_authenticated_user), # Needs authenticated user
    user_service: UserService = Depends(get_user_service),
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    当前登录用户请求发送学生身份验证邮件到其校园邮箱。
    """
    user_id = current_user['user_id'] # Access user_id from the dependency's dictionary result
    email = request_data.email # Use the email from the request body

    logger.info(f"API: User {user_id} requesting student verification email for {email}")
    try:
        # Call Service layer function
        result = await user_service.request_verification_email(conn, user_id, email) # Pass user_id and email
        # Service layer handles validation, token generation, email update in DB, and sending email
        return {"message": result.get("message", "验证邮件已发送。")} # Return message from service

    except (IntegrityError, ValueError, DALError, AuthenticationError, ForbiddenError) as e:
         # Catch specific errors from Service
         raise HTTPException(
             status_code=status.HTTP_409_CONFLICT if isinstance(e, IntegrityError) else # Email already in use
                           (status.HTTP_400_BAD_REQUEST if isinstance(e, ValueError) else # Invalid email format or bad request
                            (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else
                             (status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else status.HTTP_500_INTERNAL_SERVER_ERROR))),
             detail=str(e)
         )
    except Exception as e:
        logger.exception("API: Unexpected error during request student verification email")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"发送验证邮件时发生内部错误: {e}")

# Removed email verification routes as they are in auth.py
# @router.post("/request-verification-email", status_code=status.HTTP_200_OK)
# async def request_verification_email_api(

# TODO: Add admin-only endpoints for user management like listing all users, disabling/enabling accounts, etc. 

# Admin endpoint to get all users
@router.get("/", response_model=list[UserResponseSchema])
async def get_all_users_api(
    conn: pyodbc.Connection = Depends(get_db_connection),
    user_service: UserService = Depends(get_user_service),
    current_admin_user: dict = Depends(get_current_active_admin_user) # Requires admin authentication
):
    """
    管理员获取所有用户列表。
    """
    try:
        admin_id = current_admin_user.get('UserID') or current_admin_user.get('user_id')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无法获取管理员用户信息")

        users = await user_service.get_all_users(conn, admin_id) # Pass admin_id directly
        return users
    except (ForbiddenError, DALError, AuthenticationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else 
                          (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}") 