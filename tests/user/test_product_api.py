import pytest
from fastapi import status
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from uuid import uuid4
from main import app
from app.dal.product_dal import ProductDAL
from app.dal.user_dal import UserDAL
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductUpdate
from app.dependencies import get_db
from tests.utils import create_test_user, create_test_product, authenticate_user, get_test_db

# 使用测试数据库连接
@pytest.fixture
async def client():
    async with get_test_db() as db:
        yield TestClient(app)
        await clear_test_data(db)  # 清理测试数据的辅助函数

async def clear_test_data(db):
    """清理测试数据（示例，需根据实际表结构调整）"""
    dal = ProductDAL(db)
    await dal.delete_all_products()  # 假设存在批量删除方法
    user_dal = UserDAL(db)
    await user_dal.delete_all_users()

# --- 商品接口测试 ---
@pytest.mark.asyncio
async def test_create_product(client: TestClient):
    # 创建管理员用户
    admin = await create_test_user(client, is_admin=True)
    token = authenticate_user(client, admin)
    
    # 构造商品数据
    product_data = ProductCreate(
        category_name="电子产品",
        product_name="测试手机",
        description="测试描述",
        quantity=10,
        price=5999.0,
        image_urls=["https://example.com/image.jpg"]
    )
    
    # 发送请求
    response = client.post(
        "/api/v1/products",
        json=product_data.dict(),
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 断言
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Product created successfully"

@pytest.mark.asyncio
async def test_batch_activate_products(client: TestClient):
    # 创建管理员用户
    admin = await create_test_user(client, is_admin=True)
    token = authenticate_user(client, admin)
    
    # 创建3个待审核商品
    product_ids = []
    for _ in range(3):
        product = await create_test_product(client, admin["id"], status="PendingReview")
        product_ids.append(str(product["product_id"]))  # 假设返回的ID为字符串
    
    # 批量激活
    response = client.post(
        "/api/v1/products/batch-review",
        json={
            "productIds": product_ids,
            "newStatus": "Active",
            "reason": ""  # 激活无需原因
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 断言
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["successCount"] == 3

# --- 收藏接口测试 ---
@pytest.mark.asyncio
async def test_add_favorite(client: TestClient):
    # 创建普通用户和商品
    user = await create_test_user(client)
    product = await create_test_product(client, user["id"])
    token = authenticate_user(client, user)
    
    # 发送收藏请求
    response = client.post(
        f"/api/v1/favorites/{product['product_id']}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 断言
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Product added to favorites successfully"