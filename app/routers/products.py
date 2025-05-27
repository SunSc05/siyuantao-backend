from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.product import Product, ProductCreate
from app.services.product_service import (
    create_product_service,
    get_user_products_service,
    get_product_detail_service,
    update_product_service,
    delete_product_service,
    search_products_service
)
from app.dependencies import get_current_user

router = APIRouter()

# 创建商品
@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate, current_user = Depends(get_current_user)):
    """创建新商品（需要认证）"""
    return await create_product_service(current_user.id, product)

# 获取当前用户的商品列表
@router.get("/my", response_model=List[Product])
async def get_my_products(current_user = Depends(get_current_user)):
    """获取当前用户发布的所有商品（需要认证）"""
    return await get_user_products_service(current_user.id)

# 获取商品详情
@router.get("/{product_id}", response_model=Product)
async def get_product_detail(product_id: str):
    """获取单个商品详情"""
    product = await get_product_detail_service(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product

# 更新商品信息
@router.put("/{product_id}", response_model=Product)
async def update_product(
    product_id: str, 
    updated_product: ProductCreate,
    current_user = Depends(get_current_user)
):
    """更新商品信息（需要认证，且必须是商品所有者）"""
    product = await update_product_service(
        product_id, updated_product, current_user.id
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或无权限")
    return product

# 删除商品
@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: str, current_user = Depends(get_current_user)):
    """删除商品（需要认证，且必须是商品所有者）"""
    success = await delete_product_service(product_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="商品不存在或无权限")
    return None

# 搜索商品
@router.get("/", response_model=List[Product])
async def search_products(
    keyword: str = "",
    category: str = None,
    min_price: float = None,
    max_price: float = None,
    sort: str = "newest"  # newest, oldest, price_low, price_high
):
    """搜索商品（支持关键词、分类、价格范围和排序）"""
    return await search_products_service(
        keyword, category, min_price, max_price, sort
    )