# app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt # 导入 JWT 相关的库
from datetime import datetime, timedelta # 导入时间相关的库
from typing import Optional
from uuid import UUID
import pyodbc

from app.config import settings # 导入配置
from app.schemas.user_schemas import TokenData # 导入 TokenData schema
from app.dal.connection import get_db_connection # 导入数据库连接依赖
from app.dal.user_dal import UserDAL # 导入UserDAL
from app.services.user_service import UserService # 导入UserService
from app.dal.base import execute_query # Import execute_query from base.py
from app.dal.orders_dal import OrdersDAL # 导入 OrdersDAL
from app.services.order_service import OrderService # 导入 OrderService
from app.dal.evaluation_dal import EvaluationDAL # 导入 EvaluationDAL
from app.services.evaluation_service import EvaluationService # 导入 EvaluationService
# from app.utils.auth import verify_password, get_password_hash, create_access_token # 如果需要在这里处理token，需要导入

import logging # Import logging
logger = logging.getLogger(__name__) # Get logger instance

# Instantiate DAL and Service (consider dependency injection container for larger apps)
# 注意：这里的实例化UserDAL和UserService可能需要在获取数据库连接后再进行
# user_dal_instance = UserDAL()
# user_service_instance = UserService(user_dal_instance)

# Dependency to get a database connection
# 直接使用 get_db_connection，无需在此重复定义 get_db_conn
# async def get_db_conn():
#     """Dependency that provides a database connection."""
#     # Assuming get_db_connection manages context (e.g., is a context manager)
#     # If not, this needs adjustment based on how get_db_connection works
#     conn = get_db_connection() # Get the connection
#     # You might want to add exception handling and closing the connection here
#     try:
#         yield conn
#     finally:
#         if conn: # Ensure conn is not None before closing
#             conn.close()


# Dependency to get a UserService instance
# Inject execute_query into UserDAL when creating UserService
async def get_user_service() -> UserService: # No longer needs conn here
    """Dependency injector for UserService, injecting UserDAL with execute_query."""
    logger.debug("Attempting to get UserService instance.") # Add logging
    # Instantiate UserDAL, injecting the execute_query function
    user_dal_instance = UserDAL(execute_query_func=execute_query)
    logger.debug("UserDAL instance created.") # Add logging
    # Instantiate UserService, injecting the UserDAL instance
    service = UserService(user_dal=user_dal_instance)
    logger.debug("UserService instance created.") # Add logging
    return service # Return the UserService instance

# Dependency to get OrderService instance
async def get_order_service() -> OrderService:
    """Dependency injector for OrderService, injecting OrderDAL with execute_query."""
    logger.debug("Attempting to get OrderService instance.")
    # Instantiate OrderDAL, injecting the execute_query function
    order_dal_instance = OrdersDAL(execute_query_func=execute_query)
    logger.debug("OrderDAL instance created.")
    # Instantiate OrderService, injecting the OrderDAL instance
    service = OrderService(order_dal=order_dal_instance)
    logger.debug("OrderService instance created.")
    return service # Return the OrderService instance

async def get_evaluation_service() -> EvaluationService:
    """Dependency injector for EvaluationService, injecting EvaluationDAL with execute_query."""
    logger.debug("Attempting to get EvaluationService instance.")
    # Instantiate EvaluationDAL, injecting the execute_query function
    evaluation_dal_instance = EvaluationDAL(execute_query_func=execute_query)
    logger.debug("EvaluationDAL instance created.")
    # Instantiate EvaluationService, injecting the EvaluationDAL instance
    service = EvaluationService(evaluation_dal=evaluation_dal_instance)
    logger.debug("EvaluationService instance created.")
    return service # Return the EvaluationService instance

# 从配置文件获取 JWT 密钥和算法
SECRET_KEY = settings.SECRET_KEY # Assumes settings is imported
# ALGORITHM = settings.ALGORITHM # Assuming ALGORITHM is in settings now - This is also in settings, but maybe it's defined here for jwt.encode/decode?
ALGORITHM = "HS256" # Assuming ALGORITHM is consistently "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login") # 指向登录API端点

# 获取当前活动用户
# 将 conn 依赖项从这里移除，因为 get_user_profile_by_id 方法需要 conn，应该在调用服务方法时传递
# service 方法本身接收 conn，而不是依赖项获取 conn 再传给 service
# async def get_current_user(token: str = Depends(oauth2_scheme), user_service: UserService = Depends(get_user_service), conn: pyodbc.Connection = Depends(get_db_connection)): # Inject DB connection here
# 修改 get_current_user 依赖项，使其返回一个包含用户关键信息（如 user_id, is_staff, is_verified）的字典
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证的凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 解析 JWT payload
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("user_id")
        if user_id is None: # Token payload is invalid
            raise credentials_exception
        # Ensure user_id from token is a valid UUID string before conversion
        try:
            user_uuid = UUID(user_id) # Convert user_id string from token to UUID
        except ValueError:
             raise credentials_exception # Invalid user_id format in token
        # token_data = TokenData(user_id=user_uuid) # TokenData schema might not be needed here
    except JWTError:
        raise credentials_exception

    # Return a dict containing user key information from the token payload
    user_payload = {
        "user_id": user_uuid, # Return UUID object consistent with test mocks
        "is_staff": payload.get("is_staff", False),
        "is_verified": payload.get("is_verified", False) # Include verification status
    }
    
    # Optional: Add a quick check if the user actually exists in the DB if needed for stricter security,
    # but avoid fetching the full profile here. This would require injecting get_db_connection here.
    # For now, we rely on the router/service to handle cases where the user ID from the token doesn't exist in DB.

    return user_payload # 返回包含用户ID、is_staff等的字典数据

# 获取当前活动用户（仅限管理员）
# This dependency now depends on get_current_user, which returns a dict.
# We only need the current_user dict to check for 'is_staff'.
# We don't need to inject conn here as the admin check is based on the token payload info provided by get_current_user.
async def get_current_active_admin_user(current_user: dict = Depends(get_current_user)):
    # 检查 IsStaff 字段，需要先确保 get_current_user 返回的用户字典中包含 'IsStaff' 键
    # The key in the dict returned by get_current_user should be 'is_staff' (snake_case)
    # based on the expected keys from the token payload and test mocks.
    if current_user is None or not current_user.get('is_staff', False): # Check 'is_staff' field
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user # Return the user dict (containing user_id, is_staff, etc.)

# TODO: Add get_db_connection dependency injector (Already done by importing get_db_connection)
# TODO: Implement authentication dependency get_current_user (Done, adjusted return type)
# TODO: Implement admin authentication dependency get_current_active_admin_user (Done)

# TODO: Add get_db_connection dependency injector
# async def get_db():
#     with get_db_connection() as db:
#         yield db

# TODO: Implement authentication dependency get_current_user
# async def get_current_user():
#     # This will involve decoding the JWT token
#     pass

# TODO: Implement admin authentication dependency get_current_active_admin_user
# async def get_current_active_admin_user():
#     # This will involve checking if the user is authenticated and is staff
#     pass