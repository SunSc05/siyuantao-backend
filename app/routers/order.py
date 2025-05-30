from fastapi import APIRouter, Depends, HTTPException, status, Path
from typing import List
import pyodbc
import uuid # For User ID and Order ID

# 假设的Schema路径，请根据您的项目结构调整
from app.schemas.order_schemas import OrderCreateSchema, OrderResponseSchema, OrderStatusUpdateSchema 
# 假设的Service和依赖路径，请根据您的项目结构调整
from app.services.order_service import OrderService
from app.dependencies import get_current_user, get_db_connection, get_order_service

# 假设的异常类路径，请根据您的项目结构调整
from app.exceptions import IntegrityError, ForbiddenError, NotFoundError, DALError

router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)

@router.post("/", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_new_order(
    order_data: OrderCreateSchema,
    current_user: dict = Depends(get_current_user),
    conn: pyodbc.Connection = Depends(get_db_connection),
    order_service: OrderService = Depends(get_order_service)
):
    """
    创建一个新订单，需要用户登录。
    对应存储过程: `sp_CreateOrder` (通过Service层调用)
    """
    user_id_str = current_user.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取当前用户信息")
    
    try:
        user_id = uuid.UUID(user_id_str) # 将str转换为UUID
        # Service层负责具体的业务逻辑和调用DAL
        new_order = await order_service.create_order(conn, order_data, user_id)
        return new_order
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.put("/{order_id}/status", response_model=OrderResponseSchema)
async def update_order_status_route(
    status_update: OrderStatusUpdateSchema, # Body first
    order_id: uuid.UUID = Path(..., title="The ID of the order to update"), # Path param with default
    current_user: dict = Depends(get_current_user),
    conn: pyodbc.Connection = Depends(get_db_connection),
    order_service: OrderService = Depends(get_order_service)
):
    """
    更新订单状态 (例如：确认、完成、拒绝)。
    需要用户登录，并验证用户是否有权限操作该订单 (通常是买家或卖家)。
    对应存储过程: `sp_ConfirmOrder`, `sp_CompleteOrder`, `sp_RejectOrder` (通过Service层调用)
    """
    user_id_str = current_user.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取当前用户信息")

    try:
        user_id = uuid.UUID(user_id_str)
        updated_order = await order_service.update_order_status(
            conn, 
            order_id=order_id, 
            new_status=status_update.status, 
            user_id=user_id,
            # 根据业务逻辑，可能还需要其他参数，如角色，在service层判断
        )
        return updated_order
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e: # 例如，无效的状态转换
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ForbiddenError as e: # 用户无权修改此订单状态
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundError as e: # 订单未找到
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.get("/mine", response_model=List[OrderResponseSchema])
async def get_my_orders(
    current_user: dict = Depends(get_current_user),
    conn: pyodbc.Connection = Depends(get_db_connection),
    order_service: OrderService = Depends(get_order_service),
    # 可以添加分页参数, e.g., skip: int = 0, limit: int = 100
):
    """
    获取当前登录用户的所有订单列表 (作为买家或卖家)。
    对应存储过程: `sp_GetOrdersByUser` (通过Service层调用)
    """
    user_id_str = current_user.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取当前用户信息")

    try:
        user_id = uuid.UUID(user_id_str)
        orders = await order_service.get_orders_by_user(conn, user_id)
        return orders
    except NotFoundError as e: # 虽然通常返回空列表，但以防service层抛出
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

# TODO: 根据《职责划分》，开发者C还负责 Evaluation (评价) 表相关的API。
# 您可能需要在此文件中添加评价相关的路由，或者创建一个新的 `evaluation_router.py`。
# 例如: POST /orders/{order_id}/evaluations/ , GET /products/{product_id}/evaluations/


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_route(
    order_id: uuid.UUID = Path(..., title="The ID of the order to delete"),
    current_user: dict = Depends(get_current_user),
    conn: pyodbc.Connection = Depends(get_db_connection),
    order_service: OrderService = Depends(get_order_service)
):
    """
    删除一个订单。
    需要用户登录，并验证用户是否有权限删除该订单。
    对应存储过程: `sp_DeleteOrder` (通过Service层调用)
    """
    user_id_str = current_user.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取当前用户信息")

    try:
        user_id = uuid.UUID(user_id_str)
        await order_service.delete_order(conn, order_id, user_id)
        # 成功删除通常返回 204 No Content
        return
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e: # 例如，订单状态不允许删除
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")

@router.post("/{order_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order_route(
    cancel_reason_data: dict, # Assuming a simple dict for reason
    order_id: uuid.UUID = Path(..., title="The ID of the order to cancel"),
    current_user: dict = Depends(get_current_user),
    conn: pyodbc.Connection = Depends(get_db_connection),
    order_service: OrderService = Depends(get_order_service)
):
    """
    取消一个订单。
    需要用户登录，并验证用户是否有权限取消该订单。
    对应存储过程: `sp_CancelOrder` (通过Service层调用)
    """
    user_id_str = current_user.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无法获取当前用户信息")

    cancel_reason = cancel_reason_data.get("cancel_reason")
    if not cancel_reason:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="取消原因不能为空")

    try:
        user_id = uuid.UUID(user_id_str)
        await order_service.cancel_order(conn, order_id, user_id, cancel_reason)
        # 成功取消通常返回 204 No Content
        return
    except ForbiddenError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except NotFoundError as e:
        # Note: The test expects a specific detail message for 404, need to ensure consistency
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e: # 例如，订单状态不允许取消
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"数据库操作失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务器内部错误: {e}")