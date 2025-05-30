from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
import pyodbc # 导入 pyodbc

from app.schemas.evaluation_schemas import EvaluationCreateSchema, EvaluationResponseSchema
from app.dependencies import get_evaluation_service, get_current_user # 导入 Service 的依赖函数
from app.services.evaluation_service import EvaluationService
from app.exceptions import IntegrityError, ForbiddenError, NotFoundError, DALError
from app.dal.connection import get_db_connection # 导入 get_db_connection

router = APIRouter()

@router.post("/", response_model=EvaluationResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_new_evaluation(
    evaluation_data: EvaluationCreateSchema, # 请求体数据
    current_user: dict = Depends(get_current_user), # 认证依赖
    conn: pyodbc.Connection = Depends(get_db_connection), # 数据库连接依赖
    evaluation_service: EvaluationService = Depends(get_evaluation_service) # Service 依赖
):
    """
    发布一个新的评价，需要用户登录。
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取当前用户信息")

    try:
        # 调用业务逻辑层 Service 方法
        new_evaluation = await evaluation_service.create_evaluation(conn, evaluation_data, user_id)
        return new_evaluation
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        # 捕获其他未预期错误
        # 考虑在这里添加日志记录
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# 您可以在此添加更多评价相关的路由，例如：
# - 获取某个商品的所有评价
# - 获取用户的所有评价
# - 用户删除自己的评价
# - 管理员管理评价等