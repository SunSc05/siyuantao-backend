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
# from app.utils.auth import verify_password, get_password_hash, create_access_token # 如果需要在这里处理token，需要导入

# Instantiate DAL and Service (consider dependency injection container for larger apps)
# 注意：这里的实例化UserDAL和UserService可能需要在获取数据库连接后再进行
# user_dal_instance = UserDAL()
# user_service_instance = UserService(user_dal_instance)

# Dependency to get a database connection
async def get_db_conn():
    """Dependency that provides a database connection."""
    # Assuming get_db_connection manages context (e.g., is a context manager)
    # If not, this needs adjustment based on how get_db_connection works
    conn = get_db_connection() # Get the connection
    # You might want to add exception handling and closing the connection here
    try:
        yield conn
    finally:
        if conn: # Ensure conn is not None before closing
            conn.close()


# Dependency to get a UserService instance
# Inject execute_query into UserDAL when creating UserService
async def get_user_service() -> UserService: # No longer needs conn here
    """Dependency injector for UserService, injecting UserDAL with execute_query."""
    # Instantiate UserDAL, injecting the execute_query function
    user_dal_instance = UserDAL(execute_query_func=execute_query)
    # Instantiate UserService, injecting the UserDAL instance
    return UserService(user_dal=user_dal_instance) 

# 从配置文件获取 JWT 密钥和算法
SECRET_KEY = settings.SECRET_KEY # Assumes settings is imported
# ALGORITHM = settings.ALGORITHM # Assuming ALGORITHM is in settings now - This is also in settings, but maybe it's defined here for jwt.encode/decode?
ALGORITHM = "HS256" # Assuming ALGORITHM is consistently "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login") # 指向登录API端点

# 获取当前活动用户
async def get_current_user(token: str = Depends(oauth2_scheme), conn: pyodbc.Connection = Depends(get_db_conn), user_service: UserService = Depends(get_user_service)): # Inject UserService
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
        token_data = TokenData(user_id=user_uuid)
    except JWTError:
        raise credentials_exception

    # 根据用户ID从数据库获取用户数据，通过Service层调用
    # Pass the connection and user_id to the service method
    user = await user_service.get_user_profile_by_id(conn, token_data.user_id)
    if user is None: # User found in token but not in database (e.g., deleted user) - considered invalid credentials
        raise credentials_exception # 用户不存在
    return user # 返回用户字典数据

# 获取当前活动用户（仅限管理员）
async def get_current_active_admin_user(current_user: dict = Depends(get_current_user)):
    # 检查 IsStaff 字段，需要先确保 get_current_user 返回的用户字典中包含 'IsStaff' 键
    if current_user is None or not current_user.get('IsStaff', False): # 检查 IsStaff 字段
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user

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