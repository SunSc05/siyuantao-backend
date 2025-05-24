# app/routers/users.py
from fastapi import APIRouter, Depends, status, HTTPException
# from app.schemas.user_schemas import UserCreate, UserResponse, UserLogin, Token, UserUpdate, RequestVerificationEmail, VerifyEmail, UserPasswordUpdate # Import schemas from here
from app.schemas.user_schemas import (
    UserResponseSchema, 
    UserProfileUpdateSchema, 
    UserPasswordUpdate, # Import necessary schemas
    UserStatusUpdateSchema, # Added for new admin endpoint
    UserCreditAdjustmentSchema # Added for new admin endpoint
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
    get_user_service # Dependency for UserService
)
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError # Import necessary exceptions

router = APIRouter(prefix="/users", tags=["Users"])

# Removed /register and /login as they are in auth.py
# @router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
# async def register_user(
# ... removed ...

# @router.post("/login", response_model=Token)
# async def login_for_access_token(
# ... removed ...

@router.get("/me", response_model=UserResponseSchema)
async def read_users_me(
    # current_user: dict = Depends(get_current_user) # Requires JWT authentication
    current_user: dict = Depends(get_current_user), # Use dependency from dependencies.py
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    获取当前登录用户的个人资料。
    """
    # get_current_user dependency should provide the user ID (e.g., in a dict)
    user_id = current_user.get('UserID') or current_user.get('user_id') # Adapt based on how get_current_user returns ID
    if not user_id:
         # This should not happen if get_current_user works correctly, but as a safeguard
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法获取当前用户信息")
    
    try:
        # Call Service layer function, passing the connection and user_id
        user_profile = await user_service.get_user_profile_by_id(conn, UUID(str(user_id))) # Ensure user_id is UUID
        return user_profile
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/me", response_model=UserResponseSchema)
async def update_current_user_profile(
    user_update_data: UserProfileUpdateSchema, # Use the new schema name
    # current_user: dict = Depends(get_current_user) # Requires JWT authentication
    current_user: dict = Depends(get_current_user), # Use dependency from dependencies.py
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    更新当前登录用户的个人资料 (不包括密码)。
    """
    user_id = current_user.get('UserID') or current_user.get('user_id') # Adapt based on how get_current_user returns ID
    if not user_id:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法获取当前用户信息")

    try:
        # Call Service layer function, passing the connection and user_id
        updated_user = await user_service.update_user_profile(conn, UUID(str(user_id)), user_update_data)
        return updated_user # Service should return the updated user profile
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def update_current_user_password(
    password_update_data: UserPasswordUpdate,
    # current_user: dict = Depends(get_current_user) # Requires JWT authentication
    current_user: dict = Depends(get_current_user), # Use dependency from dependencies.py
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service) # Inject Service
):
    """
    更新当前登录用户的密码。
    """
    user_id = current_user.get('UserID') or current_user.get('user_id') # Adapt based on how get_current_user returns ID
    if not user_id:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法获取当前用户信息")

    try:
        # Call Service layer function, passing the connection and user_id
        update_success = await user_service.update_user_password(conn, UUID(str(user_id)), password_update_data)
        # Service.update_user_password should return True on success and raise exception on failure
        if not update_success:
             # This case should ideally be covered by exceptions from Service, but as a safeguard
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="密码更新失败")

        # Password update successful returns 204 No Content
        return {}
    except (NotFoundError, AuthenticationError, DALError) as e:
         # Catch specific errors from Service
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else 
                           (status.HTTP_401_UNAUTHORIZED if isinstance(e, AuthenticationError) else status.HTTP_500_INTERNAL_SERVER_ERROR),
             detail=str(e)
         )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Admin endpoints for user management by ID

@router.get("/{user_id}", response_model=UserResponseSchema)
async def get_user_profile_by_id(
    user_id: UUID, # FastAPI will validate UUID format
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service), # Inject Service
    # current_admin_user: dict = Depends(get_current_active_admin_user) # Requires admin authentication
    # Note: Authentication check is handled by the dependency itself.
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 获取用户个人资料。
    """
    try:
        # Call Service layer function, passing the connection
        user = await user_service.get_user_profile_by_id(conn, user_id)
        return user
    except NotFoundError as e:
        # This exception is raised by the Service layer if user is not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/{user_id}", response_model=UserResponseSchema)
async def update_user_profile_by_id(
    user_id: UUID,
    user_update_data: UserProfileUpdateSchema, # Use the new schema name
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service), # Inject Service
    # current_admin_user: dict = Depends(get_current_active_admin_user) # Requires admin authentication
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 更新用户个人资料。
    """
    try:
        # Call Service layer function, passing the connection
        updated_user = await user_service.update_user_profile(conn, user_id, user_update_data)
        return updated_user
    except (NotFoundError, IntegrityError, DALError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else 
                          (status.HTTP_409_CONFLICT if isinstance(e, IntegrityError) else status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(
    user_id: UUID,
    conn: pyodbc.Connection = Depends(get_db_connection), # Inject DB connection
    user_service: UserService = Depends(get_user_service), # Inject Service
    # current_admin_user: dict = Depends(get_current_active_admin_user) # Requires admin authentication
    current_admin_user: dict = Depends(get_current_active_admin_user)
):
    """
    管理员根据用户 ID 删除用户。
    """
    try:
        # Call Service layer function, passing the connection
        await user_service.delete_user(conn, user_id)
        return {} # 204 No Content returns an empty body
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Removed email verification routes as they are in auth.py
# @router.post("/request-verification-email", status_code=status.HTTP_200_OK)
# async def request_verification_email_api(
# ... removed ...

# @router.post("/verify-email", status_code=status.HTTP_200_OK)
# async def verify_email_api(
# ... removed ...

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

        users = await user_service.get_all_users(conn, UUID(str(admin_id)))
        return users
    except (ForbiddenError, DALError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Admin endpoint to change user status
@router.put("/{user_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def change_user_status_by_id(
    user_id: UUID,
    status_update_data: UserStatusUpdateSchema, # Use the new schema
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
        
        await user_service.change_user_status(conn, user_id, status_update_data.status, UUID(str(admin_id)))
        return {} # 204 No Content
    except (NotFoundError, ForbiddenError, DALError) as e:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else 
                           (status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else status.HTTP_500_INTERNAL_SERVER_ERROR),
             detail=str(e)
         )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# Admin endpoint to adjust user credit
@router.put("/{user_id}/credit", status_code=status.HTTP_204_NO_CONTENT)
async def adjust_user_credit_by_id(
    user_id: UUID,
    credit_adjustment_data: UserCreditAdjustmentSchema, # Use the new schema
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
            
        await user_service.adjust_user_credit(conn, user_id, credit_adjustment_data.credit_adjustment, UUID(str(admin_id)), credit_adjustment_data.reason)
        return {} # 204 No Content
    except (NotFoundError, ForbiddenError, DALError) as e:
         raise HTTPException(
             status_code=status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else 
                           (status.HTTP_403_FORBIDDEN if isinstance(e, ForbiddenError) else status.HTTP_500_INTERNAL_SERVER_ERROR),
             detail=str(e)
         )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}") 