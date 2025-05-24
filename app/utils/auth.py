# app/utils/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from app.config import settings
from app.schemas.user_schemas import TokenData
# from app.services.user_service import UserService # 移除对UserService的导入

# 从配置文件获取 JWT 密钥和算法
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # 访问令牌过期时间（分钟）

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login") # 指向登录API端点

# 密码哈希（使用 passlib 库，需要在 requirements.txt 中添加）
# from passlib.context import CryptContext
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# def verify_password(plain_password, hashed_password):
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password):
#     return pwd_context.hash(password)

# 开发阶段：使用明文密码（请在部署的项目中替换为安全的哈希）
def verify_password(plain_password, stored_password_hash):
    # WARNING: In production, replace with secure password hashing (e.g., bcrypt)
    return plain_password == stored_password_hash

def get_password_hash(password):
     # WARNING: In production, replace with secure password hashing (e.g., bcrypt)
     return password # 返回明文，仅为示例

# 创建访问令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 获取当前活动用户 (移动到 dependencies.py)
# async def get_current_user(...):
# ... removed ...

# 获取当前活动用户（仅限管理员）(移动到 dependencies.py)
# async def get_current_active_admin_user(...):
# ... removed ... 