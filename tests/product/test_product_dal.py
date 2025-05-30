import pytest
from unittest.mock import AsyncMock, MagicMock
from app.dal.product_dal import ProductDAL
from databases import Database
from uuid import uuid4

@pytest.fixture
def mock_db_connection(mocker: pytest_mock.MockerFixture):
    return MagicMock(spec=Database)

@pytest.mark.asyncio
async def test_sp_batch_review_products(mock_db_connection: MagicMock):
    # 初始化DAL
    dal = ProductDAL(mock_db_connection)
    
    # 模拟参数
    product_ids = ["123e4567-e89b-12d3-a456-426614174000", "456e4567-e89b-12d3-a456-426614174000"]
    admin_id = "789e4567-e89b-12d3-a456-426614174000"
    new_status = "Active"
    reason = ""
    
    # 调用方法
    await dal.batch_review_products(
        product_ids=product_ids,
        admin_id=admin_id,
        new_status=new_status,
        reason=reason
    )
    
    # 断言SQL执行（示例，需根据实际存储过程参数调整）
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_BatchReviewProducts @productIds = '123e4567-e89b-12d3-a456-426614174000,456e4567-e89b-12d3-a456-426614174000', @adminId = '789e4567-e89b-12d3-a456-426614174000', @newStatus = 'Active', @reason = ''"
    )

@pytest.mark.asyncio
async def test_add_user_favorite_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    user_id = uuid4()
    product_id = uuid4()

    await dal.add_user_favorite(mock_db_connection, user_id, product_id)

    # 断言 execute_query 是否被正确调用
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_AddFavoriteProduct @userId = :user_id, @productId = :product_id",
        {"user_id": str(user_id), "product_id": str(product_id)}
    )

@pytest.mark.asyncio
async def test_remove_user_favorite_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    user_id = uuid4()
    product_id = uuid4()

    await dal.remove_user_favorite(mock_db_connection, user_id, product_id)

    # 断言 execute_query 是否被正确调用
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_RemoveFavoriteProduct @userId = :user_id, @productId = :product_id",
        {"user_id": str(user_id), "product_id": str(product_id)}
    )

@pytest.mark.asyncio
async def test_get_user_favorite_products_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    user_id = uuid4()

    # 模拟数据库返回数据
    mock_db_connection.execute.return_value = AsyncMock()
    mock_db_connection.execute.return_value.fetchall.return_value = [
        {"商品ID": uuid4(), "商品名称": "商品A"},
        {"商品ID": uuid4(), "商品名称": "商品B"},
    ]

    favorites = await dal.get_user_favorite_products(mock_db_connection, user_id)

    # 断言 execute_query 是否被正确调用
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_GetUserFavoriteProducts @userId = :user_id",
        {"user_id": str(user_id)}
    )

    # 断言返回结果
    assert isinstance(favorites, list)
    assert len(favorites) == 2
    assert "商品名称" in favorites[0]

@pytest.mark.asyncio
async def test_decrease_product_quantity_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    product_id = uuid4()
    quantity_to_decrease = 5

    await dal.decrease_product_quantity(mock_db_connection, product_id, quantity_to_decrease)

    # 断言 execute_query 是否被正确调用
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_DecreaseProductQuantity @productId = :product_id, @quantityToDecrease = :quantity_to_decrease",
        {"product_id": product_id, "quantity_to_decrease": quantity_to_decrease}
    )

@pytest.mark.asyncio
async def test_increase_product_quantity_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    product_id = uuid4()
    quantity_to_increase = 10

    await dal.increase_product_quantity(mock_db_connection, product_id, quantity_to_increase)

    # 断言 execute_query 是否被正确调用
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_IncreaseProductQuantity @productId = :product_id, @quantityToIncrease = :quantity_to_increase",
        {"product_id": product_id, "quantity_to_increase": quantity_to_increase}
    )

@pytest.mark.asyncio
async def test_create_product_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    owner_id = uuid4()
    category_name = "Electronics"
    product_name = "Laptop"
    description = "A test laptop"
    quantity = 10
    price = 1200.50

    # Call the DAL method
    await dal.create_product(
        mock_db_connection,
        owner_id,
        category_name,
        product_name,
        description,
        quantity,
        price
    )

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_CreateProduct @ownerId = :owner_id, @categoryName = :category_name, @productName = :product_name, @description = :description, @quantity = :quantity, @price = :price",
        {
            "owner_id": owner_id,
            "category_name": category_name,
            "product_name": product_name,
            "description": description,
            "quantity": quantity,
            "price": price
        }
    )

@pytest.mark.asyncio
async def test_update_product_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    product_id = uuid4()
    owner_id = uuid4()
    category_name = "Updated Category"
    product_name = "Updated Product"
    description = "Updated Description"
    quantity = 5
    price = 99.99

    # Call the DAL method
    await dal.update_product(
        mock_db_connection,
        product_id,
        owner_id,
        category_name,
        product_name,
        description,
        quantity,
        price
    )

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_UpdateProduct @productId = :product_id, @ownerId = :owner_id, @categoryName = :category_name, @productName = :product_name, @description = :description, @quantity = :quantity, @price = :price",
        {
            "product_id": product_id,
            "owner_id": owner_id,
            "category_name": category_name,
            "product_name": product_name,
            "description": description,
            "quantity": quantity,
            "price": price
        }
    )

@pytest.mark.asyncio
async def test_delete_product_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    product_id = uuid4()
    owner_id = uuid4()

    # Call the DAL method
    await dal.delete_product(mock_db_connection, product_id, owner_id)

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_DeleteProduct @productId = :product_id, @ownerId = :owner_id",
        {
            "product_id": product_id,
            "owner_id": owner_id
        }
    )

@pytest.mark.asyncio
async def test_activate_product_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    product_id = uuid4()
    admin_id = uuid4()

    # Call the DAL method
    await dal.activate_product(mock_db_connection, product_id, admin_id)

    # Assert that the mock execute_query was called with the correct SP and parameters
    # Note: activate_product in DAL calls sp_ActivateProduct, not sp_ReviewProduct
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_ActivateProduct @productId = :product_id, @adminId = :admin_id",
        {
            "product_id": product_id,
            "admin_id": admin_id
        }
    )

@pytest.mark.asyncio
async def test_reject_product_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    product_id = uuid4()
    admin_id = uuid4()

    # Call the DAL method
    await dal.reject_product(mock_db_connection, product_id, admin_id)

    # Assert that the mock execute_query was called with the correct SP and parameters
    # Note: reject_product in DAL calls sp_RejectProduct, not sp_ReviewProduct
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_RejectProduct @productId = :product_id, @adminId = :admin_id",
        {
            "product_id": product_id,
            "admin_id": admin_id
        }
    )

@pytest.mark.asyncio
async def test_withdraw_product_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    product_id = uuid4()
    owner_id = uuid4()

    # Call the DAL method
    await dal.withdraw_product(mock_db_connection, product_id, owner_id)

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_WithdrawProduct @productId = :product_id, @ownerId = :owner_id",
        {
            "product_id": product_id,
            "owner_id": owner_id
        }
    )

@pytest.mark.asyncio
async def test_get_product_list_dal(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameters
    category_id = "Electronics"
    status = "Active"
    keyword = "Laptop"
    min_price = 1000.0
    max_price = 1500.0
    order_by = "Price"
    page_number = 2
    page_size = 5

    # Mock database return data
    mock_db_connection.execute.return_value = AsyncMock()
    mock_db_connection.execute.return_value.fetchall.return_value = [
        {"商品ID": uuid4(), "商品名称": "Laptop A"},
        {"商品ID": uuid4(), "商品名称": "Laptop B"},
    ]

    # Call the DAL method
    products = await dal.get_product_list(
        mock_db_connection,
        category_id=category_id,
        status=status,
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        order_by=order_by,
        page_number=page_number,
        page_size=page_size
    )

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_GetProductList @searchQuery = :searchQuery, @categoryName = :categoryName, @minPrice = :minPrice, @maxPrice = :maxPrice, @page = :pageNumber, @pageSize = :pageSize, @sortBy = :orderBy, @sortOrder = :sortOrder, @status = :status",
        {
            "searchQuery": keyword,
            "categoryName": category_id,
            "minPrice": min_price,
            "maxPrice": max_price,
            "pageNumber": page_number,
            "pageSize": page_size,
            "orderBy": order_by,
            "sortOrder": "DESC", # Default sortOrder in DAL method
            "status": status
        }
    )

    # Assert the returned data format
    assert isinstance(products, list)
    assert len(products) == 2
    assert "商品ID" in products[0]
    assert "商品名称" in products[0]

@pytest.mark.asyncio
async def test_get_product_by_id_dal_found(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameter
    product_id = uuid4()

    # Mock database return data (product found)
    mock_db_connection.execute.return_value = AsyncMock()
    mock_db_connection.execute.return_value.fetchone.return_value = {
        "商品ID": product_id,
        "商品名称": "Test Product Detail",
        "价格": 100.0
    }

    # Call the DAL method
    product = await dal.get_product_by_id(mock_db_connection, product_id)

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_GetProductDetail @productId = :product_id",
        {"product_id": product_id}
    )

    # Assert the returned data
    assert isinstance(product, dict)
    assert product["商品ID"] == product_id
    assert product["商品名称"] == "Test Product Detail"

@pytest.mark.asyncio
async def test_get_product_by_id_dal_not_found(mock_db_connection: MagicMock):
    dal = ProductDAL(mock_db_connection)
    # Mock input parameter
    product_id = uuid4()

    # Mock database return data (product not found - SP might return None or a specific message)
    # Assuming execute_query will handle SP message and return None for not found.
    mock_db_connection.execute.return_value = AsyncMock()
    mock_db_connection.execute.return_value.fetchone.return_value = None

    # Call the DAL method
    product = await dal.get_product_by_id(mock_db_connection, product_id)

    # Assert that the mock execute_query was called with the correct SP and parameters
    mock_db_connection.execute.assert_called_once_with(
        "EXEC sp_GetProductDetail @productId = :product_id",
        {"product_id": product_id}
    )

    # Assert the returned data is None
    assert product is None