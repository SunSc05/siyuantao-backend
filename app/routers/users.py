# app/routers/users.py
from fastapi import APIRouter, Depends, status, HTTPException
from app.schemas.user_schemas import UserCreate, UserResponse, UserLogin, Token, UserUpdate
from app.dal import users as user_dal # 直接调用 DAL
# from app.services import user_service # 如果引入了 Service 层
from app.dal.connection import get_db_connection
from app.exceptions import NotFoundError, IntegrityError, DALError
import pyodbc
from uuid import UUID

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    新用户注册。
    """
    try:
        # 实际应用中：调用密码哈希函数
        hashed_password = user_data.password # 这里仅作示例，实际需哈希
        created_user = await user_dal.create_user(conn, user_data.username, user_data.email, hashed_password)
        # 如果有 user_service 层，可以这样调用：
        # created_user = await user_service.register_user_service(conn, user_data)
        return created_user
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: UserLogin,
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    用户登录并获取 JWT Token。
    """
    user_data = await user_dal.get_user_by_username(conn, form_data.username)
    if not user_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    # 实际应用中：验证密码
    if not (form_data.password == user_data['password_hash']): # 示例，实际应 bcrypt.check_password_hash
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    # 生成 JWT token (需要单独实现，这里简化)
    access_token = "fake-jwt-token-for-" + user_data['username']
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: UUID, # FastAPI 会自动验证 UUID 格式
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    根据用户 ID 获取用户个人资料。
    """
    user = await user_dal.get_user_by_id(conn, user_id)
    if not user:
        # 抛出 NotFoundError，由 app.main.py 中的异常处理器捕获并返回 404
        raise NotFoundError(f"User with ID {user_id} not found.")
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user_profile(
    user_id: UUID,
    user_update: UserUpdate,
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    更新用户个人资料。
    """
    try:
        # 仅传递有值更新的字段
        update_data = user_update.model_dump(exclude_unset=True) # 获取只设置的字段
        # 如果密码有更新，需要哈希
        if 'password' in update_data:
            update_data['hashed_password'] = update_data.pop('password') # hash_password(update_data.pop('password'))

        # 调用 DAL 更新用户，传入 user_id 和具体更新字段
        updated_user = await user_dal.update_user(
            conn, user_id,
            username=update_data.get('username'),
            email=update_data.get('email'),
            hashed_password=update_data.get('hashed_password')
        )
        return updated_user
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_api(
    user_id: UUID,
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    删除用户。
    """
    try:
        await user_dal.delete_user(conn, user_id)
        return {} # 204 No Content 返回空响应体
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 