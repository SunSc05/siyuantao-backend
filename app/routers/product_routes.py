from fastapi import APIRouter, Depends, HTTPException
from ..services.product_service import ProductService
from ..dal.product_dal import ProductDAL
from ..dal.product_image_dal import ProductImageDAL
from ..dal.user_favorite_dal import UserFavoriteDAL
from ..schemas.product import ProductCreate, ProductUpdate
from ..dependencies import get_db, get_current_user, get_current_active_admin_user

router = APIRouter()

@router.post("/api/v1/products")
async def create_product(product: ProductCreate, user = Depends(get_current_user), db: databases.Database = Depends(get_db)):
    """
    创建新商品
    
    Args:
        product: 商品创建请求体
        user: 当前认证用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 创建失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.create_product(user.id, product.category_name, product.product_name, product.description, product.quantity, product.price, product.image_urls)
        return {"message": "Product created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/v1/products/{product_id}")
async def update_product(product_id: int, product: ProductUpdate, user = Depends(get_current_user), db: databases.Database = Depends(get_db)):
    """
    更新商品信息
    
    Args:
        product_id: 商品ID
        product: 商品更新请求体
        user: 当前认证用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 更新失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.update_product(product_id, user.id, product.category_name, product.product_name, product.description, product.quantity, product.price, product.image_urls)
        return {"message": "Product updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/v1/products/{product_id}")
async def delete_product(product_id: int, user = Depends(get_current_user), db: databases.Database = Depends(get_db)):
    """
    删除商品
    
    Args:
        product_id: 商品ID
        user: 当前认证用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 删除失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.delete_product(product_id, user.id)
        return {"message": "Product deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/v1/products")
async def get_product_list(category_id: int = None, status: str = None, keyword: str = None, min_price: float = None, max_price: float = None, order_by: str = 'PostTime', page_number: int = 1, page_size: int = 10, db: databases.Database = Depends(get_db)):
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
        db: 数据库连接
    
    Returns:
        商品列表
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    products = await product_service.get_product_list(category_id, status, keyword, min_price, max_price, order_by, page_number, page_size)
    return products

@router.get("/api/v1/products/{product_id}")
async def get_product_detail(product_id: int, db: databases.Database = Depends(get_db)):
    """
    获取商品详情
    
    Args:
        product_id: 商品ID
        db: 数据库连接
    
    Returns:
        商品详情
    
    Raises:
        HTTPException: 商品不存在时返回404错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    product = await product_service.get_product_detail(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.put("/api/v1/products/{product_id}/status/activate")
async def activate_product(product_id: int, admin = Depends(get_current_active_admin_user), db: databases.Database = Depends(get_db)):
    """
    管理员审核通过商品
    
    Args:
        product_id: 商品ID
        admin: 当前认证的管理员用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.activate_product(product_id, admin.id)
        return {"message": "Product activated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/v1/products/{product_id}/status/reject")
async def reject_product(product_id: int, admin = Depends(get_current_active_admin_user), db: databases.Database = Depends(get_db)):
    """
    管理员拒绝商品
    
    Args:
        product_id: 商品ID
        admin: 当前认证的管理员用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.reject_product(product_id, admin.id)
        return {"message": "Product rejected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/api/v1/products/{product_id}/status/withdraw")
async def withdraw_product(product_id: int, user = Depends(get_current_user), db: databases.Database = Depends(get_db)):
    """
    商品所有者下架商品
    
    Args:
        product_id: 商品ID
        user: 当前认证用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.withdraw_product(product_id, user.id)
        return {"message": "Product withdrawn successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/api/v1/products/batch/activate")
async def batch_activate_products(
    product_ids: List[int], 
    admin = Depends(get_current_active_admin_user), 
    db: databases.Database = Depends(get_db)
):
    """
    管理员批量审核通过商品
    
    Args:
        product_ids: 商品ID列表
        admin: 当前认证的管理员用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.batch_activate_products(product_ids, admin.id)
        return {"message": f"{len(product_ids)} products activated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/v1/products/batch/reject")
async def batch_reject_products(
    product_ids: List[int], 
    admin = Depends(get_current_active_admin_user), 
    db: databases.Database = Depends(get_db)
):
    """
    管理员批量拒绝商品
    
    Args:
        product_ids: 商品ID列表
        admin: 当前认证的管理员用户
        db: 数据库连接
    
    Returns:
        操作结果消息
    
    Raises:
        HTTPException: 操作失败时返回400错误
    """
    product_dal = ProductDAL(db)
    product_image_dal = ProductImageDAL(db)
    user_favorite_dal = UserFavoriteDAL(db)
    product_service = ProductService(product_dal, product_image_dal, user_favorite_dal)
    try:
        await product_service.batch_reject_products(product_ids, admin.id)
        return {"message": f"{len(product_ids)} products rejected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))