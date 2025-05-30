from fastapi import APIRouter, Depends, HTTPException
from ..services.product_service import ProductService
from ..dal.product_dal import ProductDAL
from ..schemas.product import ProductCreate, ProductUpdate
from ..dependencies import get_current_user, get_current_active_admin_user, get_product_service, get_db_connection
import pyodbc
from fastapi import status
from typing import List, Optional

router = APIRouter()

@router.post("/api/v1/products")
async def create_product(product: ProductCreate, user = Depends(get_current_user),
                          product_service: ProductService = Depends(get_product_service),
                          conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    创建新商品
    
    Args:
        product: 商品创建请求体
        user: 当前认证用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 创建失败时返回400错误
    """
    try:
        owner_id = user.get('user_id') or user.get('UserID')
        if not owner_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get user ID")

        await product_service.create_product(conn, owner_id, product.category_name, product.product_name, product.description, product.quantity, product.price, product.image_urls)
        return {"message": "Product created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/v1/products/{product_id}")
async def update_product(
    product_id: int,
    product_update_data: ProductUpdate,
    current_user = Depends(get_current_user),
    product_service: ProductService = Depends(get_product_service),
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    更新商品信息
    
    Args:
        product_id: 商品ID
        product_update_data: 商品更新请求体 (ProductUpdate Schema)
        current_user: 当前认证用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 更新失败时返回相应的HTTP错误
    """
    try:
        owner_id = current_user.get('user_id') or current_user.get('UserID')
        if not owner_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get user ID")

        await product_service.update_product(conn, product_id, owner_id, product_update_data)
        return {"message": "Product updated successfully"}

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DALError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Server error: {e}")

@router.delete("/api/v1/products/{product_id}")
async def delete_product(product_id: int, user = Depends(get_current_user),
                          product_service: ProductService = Depends(get_product_service),
                          conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    删除商品
    
    Args:
        product_id: 商品ID
        user: 当前认证用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 删除失败时返回400错误
    """
    try:
        owner_id = user.get('user_id') or user.get('UserID')
        if not owner_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get user ID")

        await product_service.delete_product(conn, product_id, owner_id)
        return {"message": "Product deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/v1/products")
async def get_product_list(category_id: int = None, status: str = None, keyword: str = None, min_price: float = None, max_price: float = None, order_by: str = 'PostTime', page_number: int = 1, page_size: int = 10,
                            product_service: ProductService = Depends(get_product_service),
                            conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    获取商品列表，支持多种筛选条件和分页
    
    Args:
        category_id: 商品分类ID
        status: 商品状态
        keyword: 搜索关键词
        min_price: 最低价格
        max_price: 最高价格
        order_by: 排序字段
        page_number: 页码
        page_size: 每页数量
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        商品列表
    """
    products = await product_service.get_product_list(conn, category_id, status, keyword, min_price, max_price, order_by, page_number, page_size)
    return products

@router.get("/api/v1/products/{product_id}")
async def get_product_detail(product_id: int,
                              product_service: ProductService = Depends(get_product_service),
                              conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    获取商品详情
    
    Args:
        product_id: 商品ID
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        商品详情
    
    Raises:
        HTTPException: 商品不存在时返回404错误
    """
    product = await product_service.get_product_detail(conn, product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product

@router.put("/api/v1/products/{product_id}/status/activate")
async def activate_product(product_id: int, admin = Depends(get_current_active_admin_user),
                            product_service: ProductService = Depends(get_product_service),
                            conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    管理员审核通过商品
    
    Args:
        product_id: 商品ID
        admin: 当前认证的管理员用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    try:
        admin_id = admin.get('user_id') or admin.get('UserID')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get admin ID")

        await product_service.activate_product(conn, product_id, admin_id)
        return {"message": "Product activated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/v1/products/{product_id}/status/reject")
async def reject_product(product_id: int, admin = Depends(get_current_active_admin_user),
                            product_service: ProductService = Depends(get_product_service),
                            conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    管理员拒绝商品
    
    Args:
        product_id: 商品ID
        admin: 当前认证的管理员用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    try:
        admin_id = admin.get('user_id') or admin.get('UserID')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get admin ID")

        await product_service.reject_product(conn, product_id, admin_id)
        return {"message": "Product rejected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/v1/products/{product_id}/status/withdraw")
async def withdraw_product(product_id: int, user = Depends(get_current_user),
                            product_service: ProductService = Depends(get_product_service),
                            conn: pyodbc.Connection = Depends(get_db_connection)):
    """
    商品所有者下架商品
    
    Args:
        product_id: 商品ID
        user: 当前认证用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    try:
        owner_id = user.get('user_id') or user.get('UserID')
        if not owner_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get user ID")

        await product_service.withdraw_product(conn, product_id, owner_id)
        return {"message": "Product withdrawn successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/api/v1/products/batch/activate")
async def batch_activate_products(
    product_ids: List[int], 
    admin = Depends(get_current_active_admin_user), 
    product_service: ProductService = Depends(get_product_service),
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    管理员批量审核通过商品
    
    Args:
        product_ids: 商品ID列表
        admin: 当前认证的管理员用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    try:
        admin_id = admin.get('user_id') or admin.get('UserID')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get admin ID")

        success_count = await product_service.batch_activate_products(conn, product_ids, admin_id)
        return {"message": f"{success_count} products activated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/v1/products/batch/reject")
async def batch_reject_products(
    product_ids: List[int], 
    admin = Depends(get_current_active_admin_user), 
    product_service: ProductService = Depends(get_product_service),
    conn: pyodbc.Connection = Depends(get_db_connection)
):
    """
    管理员批量拒绝商品
    
    Args:
        product_ids: 商品ID列表
        admin: 当前认证的管理员用户
        product_service: 商品服务依赖
        conn: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    try:
        admin_id = admin.get('user_id') or admin.get('UserID')
        if not admin_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get admin ID")

        success_count = await product_service.batch_reject_products(conn, product_ids, admin_id)
        return {"message": f"{success_count} products rejected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))