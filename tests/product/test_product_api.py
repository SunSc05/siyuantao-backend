import pytest
from fastapi import status, HTTPException
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from uuid import uuid4, uuid5
from app.main import app
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductUpdate
from unittest.mock import AsyncMock, MagicMock, ANY
from fastapi import Depends
from app.dal.connection import get_db_connection
from app.dependencies import (
    get_product_service as get_product_service_dependency,
    get_current_user as get_current_user_dependency,
    get_current_active_admin_user as get_current_active_admin_user_dependency,
    get_current_authenticated_user as get_current_authenticated_user_dependency
)
from app.schemas.user_schemas import UserResponseSchema
import uuid
from app.exceptions import NotFoundError, IntegrityError, DALError, PermissionError # Import specific exceptions

# Define comprehensive mock product data for various filter, pagination, and sorting scenarios (Moved to top level)
mock_products_all = [
    {
        "商品ID": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11", "商品名称": "Sony WH-1000XM4", "商品描述": "Noise-cancelling headphones", "库存": 15, "价格": 1999.00, "发布时间": "2023-01-05T10:00:00.000000", "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/sony.jpg", "images": []
    },
    {
        "商品ID": "b1fcc1a8-2b8e-4a7b-9c7a-5b1b1a1a1a1b", "商品名称": "Samsung Galaxy S21", "商品描述": "Android smartphone", "库存": 20, "价格": 5999.00, "发布时间": "2023-01-01T10:00:00.000000", "商品状态": "Active", "发布者用户名": "seller2", "商品类别": "Electronics", "主图URL": "/uploads/galaxy.jpg", "images": []
    },
    {
        "商品ID": "c2ddee3a-3c9f-5b8c-ad8b-6c2c2b2b2b2c", "商品名称": "Logitech MX Master 3", "商品描述": "Advanced wireless mouse", "库存": 25, "价格": 599.00, "发布时间": "2023-01-07T10:00:00.000000", "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/logitech.jpg", "images": []
    },
    {
        "商品ID": "d3feef4b-4da0-6c9d-be9c-7d3d3c3c3c3d", "商品名称": "The Great Gatsby", "商品描述": "Classic novel by F. Scott Fitzgerald", "库存": 30, "价格": 68.00, "发布时间": "2023-01-09T10:00:00.000000", "商品状态": "Active", "发布者用户名": "seller3", "商品类别": "Books", "主图URL": "/uploads/gatsby.jpg", "images": []
    },
    {
        "商品ID": "e4gff5c5-5eb1-7dae-cfaf-8e4e4d4d4d4e", "商品名称": "Sold Product 1", "商品描述": "", "库存": 0, "价格": 120.00, "发布时间": "2023-01-03T10:00:00.000000", "商品状态": "Sold", "发布者用户名": "seller4", "商品类别": "Home", "主图URL": "", "images": []
    },
    {
        "商品ID": "f5hgg6d6-6fc2-8feb-e0b0-9f5f5e5e5e5f", "商品名称": "Pending Product 1", "商品描述": "", "库存": 5, "价格": 88.00, "发布时间": "2023-01-06T10:00:00.000000", "商品状态": "PendingReview", "发布者用户名": "seller5", "商品类别": "Sports", "主图URL": "", "images": []
    }
]

# --- Mock Dependencies ---
@pytest.fixture(scope="function")
def mock_product_service(mocker):
    """Mock the ProductService dependency."""
    mock_service = AsyncMock(spec=ProductService)
    # No need to patch dependency here, will do in client fixture
    return mock_service

@pytest.fixture(scope="function")
def mock_db_connection(mocker):
    """Mock the database connection dependency."""
    mock_conn = MagicMock()
    return mock_conn

# --- Mock Authentication Dependencies ---
async def mock_get_current_user_override():
    # Return a dict that matches the expected payload structure for a regular user
    # Use a consistent, predictable integer ID for testing
    return {"user_id": 101, "UserID": 101, "username": "testuser", "is_staff": False, "is_verified": True}

async def mock_get_current_active_admin_user_override():
    # Return a dict that matches the expected payload structure for an admin user
    # Use a consistent, predictable integer ID for testing
    return {"user_id": 201, "UserID": 201, "username": "adminuser", "is_staff": True, "is_verified": True}

async def mock_get_current_authenticated_user_override():
    # Return a UserResponseSchema-like dict for an authenticated user
    # Use a consistent, predictable integer ID for testing
    return {"user_id": 301, "UserID": 301, "username": "authuser", "email": "auth@example.com", "status": "Active", "credit": 100, "is_staff": False, "is_super_admin": False, "is_verified": True, "major": "", "avatar_url": None, "bio": None, "phone_number": "1234567890", "join_time": datetime.now().isoformat()}


@pytest.fixture(scope="function")
def client(
    mock_product_service: AsyncMock,
    mock_db_connection: MagicMock
):
    """Configured TestClient with mocked dependencies."""
    
    async def override_get_db_connection_async():
        yield mock_db_connection

    app.dependency_overrides[get_product_service_dependency] = lambda: mock_product_service
    app.dependency_overrides[get_db_connection] = override_get_db_connection_async
    app.dependency_overrides[get_current_user_dependency] = mock_get_current_user_override
    app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_override
    app.dependency_overrides[get_current_authenticated_user_dependency] = mock_get_current_authenticated_user_override

    with TestClient(app) as tc:
        # Add mocked user IDs to the test client for easy access in tests
        tc.test_user_id = 101 # Fixed integer ID
        tc.test_admin_user_id = 201 # Fixed integer ID
        tc.test_auth_user_id = 301 # Fixed integer ID
        yield tc

    app.dependency_overrides.clear()

# --- 商品接口测试 ---
@pytest.mark.asyncio
async def test_create_product(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users directly, authentication is mocked.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    test_owner_id = client.test_auth_user_id

    # 构造商品数据
    product_data = ProductCreate(
        category_name="电子产品",
        product_name="测试手机",
        description="测试描述",
        quantity=10,
        price=5999.0,
        image_urls=["https://example.com/image.jpg"]
    )

    # Mock the service layer call
    # The service's create_product method is expected to return None on success based on its signature.
    # The API router is responsible for returning the success message.
    mock_product_service.create_product.return_value = None # Simulate successful creation

    # Act
    # Send request using the client with mocked dependencies
    response = client.post(
        "/api/v1/products", # Modified: Added /api/v1 prefix
        json=product_data.model_dump(), # Use model_dump for Pydantic v2
        # Authentication header is implicitly handled by the mocked get_current_authenticated_user
        # but including it in the test makes it clearer that this endpoint requires auth.
        # However, since the dependency override bypasses the actual token check,
        # we don't strictly need the header here for the test to pass based on mocking.
        # Let's keep it to reflect the actual API usage.
        headers={
            "Authorization": "Bearer fake-token" # Use a placeholder token since it's mocked
        }
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED # Expect 201 Created for resource creation
    assert response.json()["message"] == "商品创建成功"

    # Assert that the service method was called with the correct arguments
    # The service's create_product expects conn, owner_id (int), category_name, product_name, description, quantity, price, image_urls
    # We need to capture the call arguments and check them.

    # The mock_product_service.create_product was called within the API endpoint.
    # We check if it was called once.
    mock_product_service.create_product.assert_called_once()

    # Check the arguments it was called with.
    # The first argument is the database connection (mocked).
    # The subsequent arguments are based on the ProductCreate schema and the owner_id from the mocked dependency.
    # Get the call arguments
    args, kwargs = mock_product_service.create_product.call_args

    # Check the arguments
    # arg[0] is the mocked connection
    # arg[1] should be the owner_id (int)
    # arg[2] should be category_name
    # arg[3] should be product_name
    # arg[4] should be description
    # arg[5] should be quantity
    # arg[6] should be price
    # arg[7] should be image_urls (list of strings)

    assert args[1] == test_owner_id # Check owner_id, now an int
    assert args[2] == product_data.category_name
    assert args[3] == product_data.product_name
    assert args[4] == product_data.description
    assert args[5] == product_data.quantity
    assert args[6] == product_data.price
    assert args[7] == product_data.image_urls

@pytest.mark.asyncio
async def test_batch_activate_products(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, authentication is mocked.
    # The mock_get_current_active_admin_user_override provides the authenticated admin user's info.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    test_admin_id = client.test_admin_user_id

    # Generate some fake product IDs for the batch operation
    product_ids_api = [str(uuid4()) for _ in range(3)] # For API request (list of string UUIDs)
    # The service layer expects integer IDs. The router converts UUID strings to integers.
    product_ids_service = [uuid.UUID(pid).int for pid in product_ids_api] # For service call (list of integers)
    
    # Mock the service layer call for batch activation
    # The service's batch_activate_products method is expected to return the count of successfully activated products.
    mock_product_service.batch_activate_products.return_value = len(product_ids_service) # Simulate successful activation
    
    # Act
    # Send request using the client with mocked dependencies
    response = client.post(
        "/api/v1/products/batch/activate", # Modified: Added /api/v1 prefix
        json={
            "product_ids": product_ids_api, # Use product_ids_api for payload (now string UUIDs)
            "new_status": "Active", # Modified: Changed to new_status
            "reason": None  # Activation doesn't require a reason
        },
        headers={
            "Authorization": "Bearer fake-admin-token" # Placeholder token for clarity
        }
    )
    
    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == f"成功激活 {len(product_ids_service)} 件商品" # Modified: Changed to check 'message'

    # Assert that the service method was called with the correct arguments
    # The service's batch_activate_products expects conn, product_ids (List[int]), admin_id (int)

    mock_product_service.batch_activate_products.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.batch_activate_products.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_ids (List[int])
    # arg[2] should be admin_id (int)

    assert args[1] == product_ids_service # Check product_ids (list of integers)
    assert args[2] == test_admin_id # Modified: admin_id is already an int

@pytest.mark.asyncio
async def test_add_favorite(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, authentication is mocked.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    test_user_id = client.test_auth_user_id

    # Generate a fake product ID
    fake_product_id_api = 123 # For API request (integer)
    fake_product_id_service = 123 # For service call (integer)

    # Mock the service layer call for adding a favorite
    # The service's add_favorite method is expected to return None on success.
    mock_product_service.add_favorite.return_value = None # Simulate successful addition

    # Act
    # Send request using the client with mocked dependencies
    response = client.post(
        f"/api/v1/products/{fake_product_id_api}/favorite", # Modified: Added /api/v1 prefix
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token for clarity
        }
    )

    # Assert
    assert response.status_code == status.HTTP_201_CREATED # Expect 201 Created for resource creation
    assert response.json()["message"] == "商品收藏成功"

    # Assert that the service method was called with the correct arguments
    # The service's add_favorite expects conn, user_id (int), product_id (int)

    mock_product_service.add_favorite.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.add_favorite.call_args

    # arg[0] is the mocked connection
    # arg[1] should be user_id (int)
    # arg[2] should be product_id (int)

    assert args[1] == test_user_id # Modified: user_id is already an int
    assert args[2] == fake_product_id_service

@pytest.mark.asyncio
async def test_get_product_list(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data that the service should return
    # This data should match the structure returned by the sp_GetProductList and sp_GetProductDetail (for images)
    # and should use the Chinese aliases defined in the stored procedures.
    mock_products = [
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "测试商品A",
            "商品描述": "描述A",
            "库存": 10,
            "价格": 100.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "testuser1",
            "商品类别": "Electronics",
            "主图URL": "/uploads/imageA.jpg",
            "images": []
        },
        {
            "商品ID": mock_products_all[1]["商品ID"],
            "商品名称": "测试商品B",
            "商品描述": "描述B",
            "库存": 5,
            "价格": 200.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "PendingReview",
            "发布者用户名": "testuser2",
            "商品类别": "Books",
            "主图URL": "/uploads/imageB.jpg",
            "images": []
        }
    ]
    mock_product_service.get_product_list.return_value = mock_products

    # Act
    response = client.get("/api/v1/products", params={
        "category_id": 1, # Modified: Use integer for category_id
        "status": "Active",
        "keyword": "测试",
        "min_price": 50.0,
        "max_price": 250.0,
        "order_by": "Price",
        "page_number": 1,
        "page_size": 10
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_products

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_list.assert_called_once_with(
        ANY, # conn
        1, # category_id (int)
        "Active", # status
        "测试", # keyword
        50.0, # min_price
        250.0, # max_price
        "Price", # order_by
        1, # page_number
        10 # page_size
    )

@pytest.mark.asyncio
async def test_get_product_detail(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, data is mocked.

    # Generate a fake product ID for the test
    test_product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Use integer product ID for update, matching DAL/Service expectation

    mock_product_data = {
        "商品ID": mock_products_all[0]["商品ID"],
        "商品名称": "测试手机",
        "商品描述": "一个很棒的测试手机",
        "库存": 50,
        "价格": 5999.0,
        "发布时间": datetime.now().isoformat(),
        "商品状态": "Active",
        "发布者用户名": "testuser",
        "商品类别": "Electronics",
        "主图URL": "http://example.com/test_phone.jpg",
        "images": [
            {"image_url": "http://example.com/test_phone_1.jpg", "sort_order": 0, "upload_time": datetime.now().isoformat()},
            {"image_url": "http://example.com/test_phone_2.jpg", "sort_order": 1, "upload_time": datetime.now().isoformat()}
        ]
    }

    # Mock the service layer call
    mock_product_service.get_product_detail.return_value = mock_product_data

    # Act
    response = client.get(f"/api/v1/products/{test_product_id}") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_product_data

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_detail.assert_called_once_with(ANY, test_product_id)

@pytest.mark.asyncio
async def test_get_product_detail_not_found(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # Generate a fake product ID that won't be found
    non_existent_product_id = 9999 # Use integer product ID for update, matching DAL/Service expectation

    # Configure the mock_product_service.get_product_detail to return None, simulating not found
    mock_product_service.get_product_detail.return_value = None

    # Act
    response = client.get(f"/api/v1/products/{non_existent_product_id}") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "商品未找到"

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_detail.assert_called_once_with(ANY, non_existent_product_id)

@pytest.mark.asyncio
async def test_update_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user (owner)
    owner_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Use integer product ID for update, matching DAL/Service expectation

    # Prepare product update data
    product_update_data = ProductUpdate(
        product_name="更新后的测试手机",
        description="更新后的测试描述",
        price=6500.0,
        quantity=15,
        image_urls=["https://example.com/updated_image.jpg"]
    )

    # Configure the mock_product_service.update_product to do nothing on success
    mock_product_service.update_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.put(
        f"/api/v1/products/{product_id}", # Modified: Added /api/v1 prefix
        json=product_update_data.model_dump(exclude_unset=True) # Use model_dump for Pydantic v2
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Product updated successfully"

    # Assert that the service method was called with the correct arguments
    # The service's update_product expects conn, product_id (int), owner_id (int), product_update_data (ProductUpdate)

    mock_product_service.update_product.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.update_product.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (int)
    # arg[2] should be owner_id (int)
    # arg[3] should be product_update_data (ProductUpdate object)

    assert args[1] == product_id
    assert args[2] == owner_id # Modified: owner_id is already an int
    assert args[3] == product_update_data

@pytest.mark.asyncio
async def test_update_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use a different user ID to simulate a non-owner attempting the update
    non_owner_user_id = client.test_auth_user_id # Changed to use fixed int ID
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Prepare product update data
    product_update_data = ProductUpdate(
        product_name="尝试更新的商品",
    )

    # Configure the mock_product_service.update_product to raise a PermissionError
    mock_product_service.update_product.side_effect = PermissionError("您无权更新此商品")

    # Act
    response = client.put(
        f"/api/v1/products/{product_id}", # Modified: Added /api/v1 prefix
        json=product_update_data.model_dump(exclude_unset=True)
    )

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN # Expect 403 Forbidden
    assert response.json()["detail"] == "您无权更新此商品"

    # Assert that the service method was called with the correct arguments
    mock_product_service.update_product.assert_called_once()
    args, kwargs = mock_product_service.update_product.call_args
    assert args[1] == product_id
    assert args[2] == non_owner_user_id # Modified: non_owner_user_id is already an int
    assert args[3] == product_update_data

@pytest.mark.asyncio
async def test_delete_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user (owner)
    owner_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Configure the mock_product_service.delete_product to do nothing on success
    mock_product_service.delete_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.delete(f"/api/v1/products/{product_id}") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful deletion
    assert response.json()["message"] == "商品删除成功"

    # Assert that the service method was called with the correct arguments
    mock_product_service.delete_product.assert_called_once_with(ANY, product_id, owner_id) # Modified: owner_id is already an int

@pytest.mark.asyncio
async def test_withdraw_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user (owner)
    owner_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Configure the mock_product_service.withdraw_product to do nothing on success
    mock_product_service.withdraw_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.put(f"/api/v1/products/{product_id}/status/withdraw") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful withdrawal
    assert response.json()["message"] == "商品已成功下架" # Modified: Changed expected message

    # Assert that the service method was called with the correct arguments
    mock_product_service.withdraw_product.assert_called_once_with(ANY, product_id, owner_id) # Modified: owner_id is already an int

@pytest.mark.asyncio
async def test_withdraw_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use a different user ID to simulate a non-owner attempting the withdrawal
    non_owner_user_id = client.test_auth_user_id # Changed to use fixed int ID
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Configure the mock_product_service.withdraw_product to raise a PermissionError
    mock_product_service.withdraw_product.side_effect = PermissionError("您无权下架此商品")

    # Act
    response = client.put(f"/api/v1/products/{product_id}/status/withdraw") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN # Expect 403 Forbidden
    assert response.json()["detail"] == "您无权下架此商品"

    # Assert that the service method was called with the correct arguments
    mock_product_service.withdraw_product.assert_called_once()
    args, kwargs = mock_product_service.withdraw_product.call_args
    assert args[1] == product_id
    assert args[2] == non_owner_user_id # Modified: non_owner_user_id is already an int

@pytest.mark.asyncio
async def test_get_product_list_filter_by_category(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data filtered by category
    mock_products = [
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "电子产品A",
            "商品描述": "",
            "库存": 10,
            "价格": 100.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "user1",
            "商品类别": "Electronics",
            "主图URL": "",
            "images": []
        }
    ]

    # Configure the mock service to return filtered products
    mock_product_service.get_product_list.return_value = mock_products

    # Act
    response = client.get("/api/v1/products", params={
        "category_id": 1, # Modified: Pass integer category ID
        "status": "Active"
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_products

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_list.assert_called_once_with(
        ANY,
        1, # Modified: Assert with integer category ID
        "Active",
        None, None, None, # keyword, min_price, max_price
        'PostTime', 1, 10 # order_by, page_number, page_size
    )

@pytest.mark.asyncio
async def test_get_product_list_filter_by_price_range(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data filtered by price range (100-200)
    mock_products = [
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "商品X",
            "商品描述": "",
            "库存": 5,
            "价格": 150.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "userA",
            "商品类别": "General",
            "主图URL": "",
            "images": []
        }
    ]

    mock_product_service.get_product_list.return_value = mock_products

    # Act
    response = client.get("/api/v1/products", params={
        "min_price": 100.0,
        "max_price": 200.0
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_products

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_list.assert_called_once_with(
        ANY,
        None, None, # category_id, status
        None, # keyword
        100.0, # min_price
        200.0, # max_price
        'PostTime', 1, 10 # order_by, page_number, page_size
    )

@pytest.mark.asyncio
async def test_get_product_list_search_keyword(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data for keyword search tests
    mock_products = [
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "智能手机",
            "商品描述": "一款高性能手机",
            "库存": 20,
            "价格": 3000.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "sellerX",
            "商品类别": "Electronics",
            "主图URL": "",
            "images": []
        }
    ]

    mock_product_service.get_product_list.return_value = mock_products

    # Act
    response = client.get("/api/v1/products", params={
        "keyword": "手机"
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_products

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_list.assert_called_once_with(
        ANY,
        None, None, # category_id, status
        "手机", # keyword
        None, None, # min_price, max_price
        'PostTime', 1, 10 # order_by, page_number, page_size
    )

@pytest.mark.asyncio
async def test_get_product_list_filter_by_status(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data with various statuses
    mock_products_all_statuses = [
        {
            "商品ID": mock_products_all[0]["商品ID"], "商品名称": "Active Product", "商品描述": "", "库存": 10, "价格": 100.0, "发布时间": datetime.now().isoformat(), "商品状态": "Active", "发布者用户名": "user1", "商品类别": "CategoryA", "主图URL": "", "images": []
        },
        {
            "商品ID": mock_products_all[1]["商品ID"], "商品名称": "Pending Product", "商品描述": "", "库存": 5, "价格": 150.0, "发布时间": datetime.now().isoformat(), "商品状态": "PendingReview", "发布者用户名": "user2", "商品类别": "CategoryB", "主图URL": "", "images": []
        },
        {
            "商品ID": mock_products_all[4]["商品ID"], "商品名称": "Sold Product", "商品描述": "", "库存": 0, "价格": 200.0, "发布时间": datetime.now().isoformat(), "商品状态": "Sold", "发布者用户名": "user3", "商品类别": "CategoryC", "主图URL": "", "images": []
        }
    ]

    async def mock_get_product_list_side_effect_status(conn, category_id=None, status=None, keyword=None, min_price=None, max_price=None, order_by='PostTime', page_number=1, page_size=10, **kwargs):
        if status == "Active":
            return [p for p in mock_products_all_statuses if p["商品状态"] == "Active"]
        elif status == "PendingReview":
            return [p for p in mock_products_all_statuses if p["商品状态"] == "PendingReview"]
        elif status == "Sold":
            return [p for p in mock_products_all_statuses if p["商品状态"] == "Sold"]
        return mock_products_all_statuses # Return all if no status filter

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect_status

    # Test with Active status
    response_active = client.get("/api/v1/products", params={
        "status": "Active"
    })
    assert response_active.status_code == status.HTTP_200_OK
    assert len(response_active.json()) == 1
    assert response_active.json()[0]["商品状态"] == "Active"
    mock_product_service.get_product_list.assert_any_call(
        ANY, None, "Active", None, None, None, 'PostTime', 1, 10
    )

    # Test with PendingReview status
    response_pending = client.get("/api/v1/products", params={
        "status": "PendingReview"
    })
    assert response_pending.status_code == status.HTTP_200_OK
    assert len(response_pending.json()) == 1
    assert response_pending.json()[0]["商品状态"] == "PendingReview"
    mock_product_service.get_product_list.assert_any_call(
        ANY, None, "PendingReview", None, None, None, 'PostTime', 1, 10
    )

    # Test with Sold status
    response_sold = client.get("/api/v1/products", params={
        "status": "Sold"
    })
    assert response_sold.status_code == status.HTTP_200_OK
    assert len(response_sold.json()) == 1
    assert response_sold.json()[0]["商品状态"] == "Sold"
    mock_product_service.get_product_list.assert_any_call(
        ANY, None, "Sold", None, None, None, 'PostTime', 1, 10
    )

@pytest.mark.asyncio
async def test_get_product_list_pagination_and_sorting(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data that the service should return for pagination and sorting
    # This data should match the structure returned by the sp_GetProductList and sp_GetProductDetail (for images)
    # and should use the Chinese aliases defined in the stored procedures.
    # Using global mock_products_all for consistency.
    global mock_products_all # Ensure we are using the global mock data

    async def mock_get_product_list_side_effect_pagination_sorting(conn, category_id=None, status=None, keyword=None, min_price=None, max_price=None, order_by='PostTime', page_number=1, page_size=10, **kwargs):
        # Filter by status if provided
        filtered_products = [p for p in mock_products_all if p["商品状态"] == "Active"]

        def get_sort_key(product):
            if order_by == "Price":
                return product["价格"]
            elif order_by == "ProductName":
                return product["商品名称"]
            elif order_by == "PostTime":
                return datetime.fromisoformat(product["发布时间"])
            return datetime.fromisoformat(product["发布时间"]) # Default sort key

        # Determine reverse_sort based on order_by, as API doesn't take sortOrder directly
        # Assume PostTime is DESC by default, others ASC by default if not specified
        reverse_sort = True if order_by == "PostTime" else False
        sorted_products = sorted(filtered_products, key=get_sort_key, reverse=reverse_sort)

        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        return sorted_products[start_index:end_index]

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect_pagination_sorting

    # Test case 1: Page 1, size 2, sorted by Price ASC
    response1 = client.get("/api/v1/products", params={
        "page_number": 1,
        "page_size": 2,
        "order_by": "Price",
        # "sortOrder": "ASC" # Removed, as API doesn't support this directly
    })
    assert response1.status_code == status.HTTP_200_OK
    assert len(response1.json()) == 2
    # Expected order: The Great Gatsby (68.0), Logitech MX Master 3 (599.0)
    assert response1.json()[0]["商品名称"] == "The Great Gatsby"
    assert response1.json()[1]["商品名称"] == "Logitech MX Master 3"
    mock_product_service.get_product_list.assert_any_call(ANY, None, None, None, None, None, "Price", 1, 2)

    # Test case 2: Page 2, size 2, sorted by Price ASC
    response2 = client.get("/api/v1/products", params={
        "page_number": 2,
        "page_size": 2,
        "order_by": "Price",
        # "sortOrder": "ASC" # Removed, as API doesn't support this directly
    })
    assert response2.status_code == status.HTTP_200_OK
    assert len(response2.json()) == 2
    # Expected order: Sony WH-1000XM4 (1999.0), Samsung Galaxy S21 (5999.0)
    assert response2.json()[0]["商品名称"] == "Sony WH-1000XM4"
    assert response2.json()[1]["商品名称"] == "Samsung Galaxy S21"
    mock_product_service.get_product_list.assert_any_call(ANY, None, None, None, None, None, "Price", 2, 2)

    # Test case 3: Sorted by PostTime DESC
    response3 = client.get("/api/v1/products", params={
        "order_by": "PostTime",
        # "sortOrder": "DESC" # Removed, as API doesn't support this directly
    })
    assert response3.status_code == status.HTTP_200_OK
    assert len(response3.json()) == 4 # Only 4 active products in mock_products_all
    # Expected order (most recent first): The Great Gatsby, Logitech MX Master 3, Sony WH-1000XM4, Samsung Galaxy S21
    assert response3.json()[0]["商品名称"] == "The Great Gatsby"
    assert response3.json()[1]["商品名称"] == "Logitech MX Master 3"
    assert response3.json()[2]["商品名称"] == "Sony WH-1000XM4"
    assert response3.json()[3]["商品名称"] == "Samsung Galaxy S21"
    mock_product_service.get_product_list.assert_any_call(ANY, None, None, None, None, None, "PostTime", 1, 10)

@pytest.mark.asyncio
async def test_get_product_list_filter_combinations(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define comprehensive mock product data for various filter conditions
    # mock_products_all is already defined at the top of the file
    global mock_products_all # Use the global mock_products_all

    # Configure the mock_product_service.get_product_list side effect
    async def mock_get_product_list_side_effect(conn, category_id=None, status=None, keyword=None, min_price=None, max_price=None, order_by='PostTime', page_number=1, page_size=10, **kwargs):
        # Map integer category_id to string category name for filtering mock data
        category_id_to_name = {
            1: "Electronics",
            2: "Books",
            3: "Other", # Added mapping for category 3
            4: "Home", # Added mapping for category 4
            5: "Sports", # Added mapping for category 5
            # Add other mappings as needed
        }
        category_name_filter = category_id_to_name.get(category_id) if isinstance(category_id, int) else category_id

        status_filter = status # Corrected: Use status directly
        search_query = keyword # Corrected: Use keyword directly
        min_price_filter = min_price # Corrected: Use min_price directly
        max_price_filter = max_price # Corrected: Use max_price directly
        page_number_filter = page_number # Corrected: Use page_number directly
        page_size_filter = page_size # Corrected: Use page_size directly
        order_by_field = order_by # Corrected: Use order_by directly
        sort_order = kwargs.get("sortOrder", "DESC")

        # Apply filters
        filtered_products = []
        for p in mock_products_all:
            is_match = True

            if status_filter and p["商品状态"] != status_filter:
                is_match = False

            if is_match and category_name_filter and p.get("商品类别") != category_name_filter:
                is_match = False

            if is_match and search_query:
                if not (search_query.lower() in p["商品名称"].lower() or (p.get("商品描述") and search_query.lower() in p["商品描述"].lower())):
                    is_match = False

            if is_match and min_price_filter is not None and p["价格"] < min_price_filter:
                is_match = False
            if is_match and max_price_filter is not None and p["价格"] > max_price_filter:
                is_match = False

            if is_match:
                filtered_products.append(p)

        # Apply sorting
        def get_sort_key(product):
            if order_by_field == "Price":
                return product["价格"]
            elif order_by_field == "ProductName":
                return product["商品名称"]
            elif order_by_field == "PostTime":
                # Convert ISO format string to datetime for proper comparison
                return datetime.fromisoformat(product["发布时间"])
            return datetime.fromisoformat(product["发布时间"]) # Default sort key

        # Determine reverse_sort based on order_by, as API doesn't take sortOrder directly
        # Assume PostTime is DESC by default, others ASC by default if not specified
        reverse_sort = True if order_by_field == "PostTime" else False
        sorted_products = sorted(filtered_products, key=get_sort_key, reverse=reverse_sort)

        # Apply pagination
        start_index = (page_number_filter - 1) * page_size_filter
        end_index = start_index + page_size_filter
        paginated_products = sorted_products[start_index:end_index]

        # Update total count in the paginated results
        total_count = len(filtered_products)
        for p in paginated_products:
             p["总商品数"] = total_count

        return paginated_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Filter by Category and Price Range, Paginate and Sort by Price ASC
    response1 = client.get("/api/v1/products", params={
        "category_id": 1, # Changed to category_id (int)
        "min_price": 1000.00,
        "max_price": 7000.00,
        "page_number": 1,
        "page_size": 2,
        "order_by": "Price",
        # "sortOrder": "ASC" # Removed, as API doesn't support this directly
    })

    assert response1.status_code == status.HTTP_200_OK
    # Expected products: Sony WH-1000XM4 (1999.00), Samsung Galaxy S21 (5999.00) or other if data changed
    # Assuming the sorted products based on mock_products_all and filters
    # Let's define the expected result based on the current mock_products_all and filter criteria
    expected_products_1 = [
        # After filtering for Electronics, min_price=1000, max_price=7000, and sorting by Price ASC:
        # Original: Sony(1999), Samsung(5999), Logitech(599)
        # Filtered & Sorted: Sony(1999), Samsung(5999)
        # After pagination (page 1, size 2):
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "Sony WH-1000XM4",
            "商品描述": "Noise-cancelling headphones",
            "库存": 15,
            "价格": 1999.00,
            "发布时间": "2023-01-05T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "Electronics",
            "主图URL": "/uploads/sony.jpg",
            "images": [],
            "总商品数": 2 # Use fixed value
        },
        {
            "商品ID": mock_products_all[1]["商品ID"],
            "商品名称": "Samsung Galaxy S21",
            "商品描述": "Android smartphone",
            "库存": 20,
            "价格": 5999.00,
            "发布时间": "2023-01-01T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller2",
            "商品类别": "Electronics",
            "主图URL": "/uploads/galaxy.jpg",
            "images": [],
            "总商品数": 2 # Use fixed value
        }
    ]
    assert response1.json() == expected_products_1
    mock_product_service.get_product_list.assert_any_call(
        ANY,
        1, # category_id (int)
        None, # status
        None, # keyword
        1000.00, # min_price
        7000.00, # max_price
        "Price", # order_by
        1, # page_number
        2, # page_size
    )

    # Test case 2: Filter by Status and Keyword, Paginate and Sort by PostTime DESC
    response2 = client.get("/api/v1/products", params={
        "status": "Active",
        "keyword": "mouse",
        "page_number": 1,
        "page_size": 1,
        "order_by": "PostTime",
        # "sortOrder": "DESC" # Removed, as API doesn't support this directly
    })
    assert response2.status_code == status.HTTP_200_OK
    expected_products_2 = [
        # After filtering for Active, keyword='mouse', and sorting by PostTime DESC:
        # Original: Logitech MX Master 3 (Active, 'mouse' in name)
        # Filtered & Sorted:
        {
            "商品ID": mock_products_all[2]["商品ID"],
            "商品名称": "Logitech MX Master 3",
            "商品描述": "Advanced wireless mouse",
            "库存": 25,
            "价格": 599.00,
            "发布时间": "2023-01-07T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "Electronics",
            "主图URL": "/uploads/logitech.jpg",
            "images": [],
            "总商品数": 1 # Use fixed value
        }
    ]
    assert response2.json() == expected_products_2
    mock_product_service.get_product_list.assert_any_call(
        ANY,
        None, # category_id
        "Active", # status
        "mouse", # keyword
        None, None, # min_price, max_price
        "PostTime", # order_by
        1, # page_number
        1, # page_size
    )

    # Test case 3: Filter by Category and Status, and Keyword
    response3 = client.get("/api/v1/products", params={
        "category_id": 2, # Changed to category_id (int)
        "status": "Active",
        "keyword": "gatsby"
    })
    assert response3.status_code == status.HTTP_200_OK
    expected_products_3 = [
        # After filtering for Books, Active, keyword='gatsby':
        # Original: The Great Gatsby (Books, Active, 'gatsby' in name)
        {
            "商品ID": mock_products_all[3]["商品ID"],
            "商品名称": "The Great Gatsby",
            "商品描述": "Classic novel by F. Scott Fitzgerald",
            "库存": 30,
            "价格": 68.00,
            "发布时间": "2023-01-09T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller3",
            "商品类别": "Books",
            "主图URL": "/uploads/gatsby.jpg",
            "images": [],
            "总商品数": 1 # Use fixed value
        }
    ]
    assert response3.json() == expected_products_3
    mock_product_service.get_product_list.assert_any_call(
        ANY,
        2, # category_id (int)
        "Active", # status
        "gatsby", # keyword
        None, None, # min_price, max_price
        'PostTime', 1, 10
    )

@pytest.mark.asyncio
async def test_remove_favorite_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, mocking handles data.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    user_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Configure the mock_product_service.remove_favorite to do nothing on success
    mock_product_service.remove_favorite.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.delete(f"/api/v1/products/{product_id}/favorite") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful removal
    assert response.json()["message"] == "商品已成功从收藏列表中移除"

    mock_product_service.remove_favorite.assert_called_once_with(ANY, user_id, product_id) # Modified: user_id is already an int

@pytest.mark.asyncio
async def test_remove_favorite_not_favorited(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, mocking handles data.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    user_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Configure the mock_product_service.remove_favorite to raise a ValueError to simulate not favorited
    mock_product_service.remove_favorite.side_effect = ValueError("该商品不在您的收藏列表中。") # Simulate service raising ValueError

    # Act
    response = client.delete(f"/api/v1/products/{product_id}/favorite") # Modified: Added /api/v1 prefix

    # Assert
    # The router should catch the ValueError from the service and return a 400 HTTP exception
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "该商品不在您的收藏列表中。"

    mock_product_service.remove_favorite.assert_called_once_with(ANY, user_id, product_id) # Modified: user_id is already an int

@pytest.mark.asyncio
async def test_get_user_favorites(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, mocking handles data.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    user_id = client.test_auth_user_id

    # Define mock data that the service should return (list of favorite products)
    mock_favorite_products = [
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "收藏商品1",
            "商品描述": "Description 1",
            "库存": 10,
            "价格": 100.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller_user_1",
            "商品类别": "CategoryA",
            "收藏时间": datetime.now().isoformat(),
            "主图URL": "/uploads/fav1.jpg",
            "images": []
        },
        {
            "商品ID": mock_products_all[1]["商品ID"],
            "商品名称": "收藏商品2",
            "商品描述": "Description 2",
            "库存": 5,
            "价格": 200.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller_user_2",
            "商品类别": "CategoryB",
            "收藏时间": datetime.now().isoformat(),
            "主图URL": "/uploads/fav2.jpg",
            "images": []
        }
    ]

    # Mock the service's get_user_favorites method to return the mock data
    mock_product_service.get_user_favorites.return_value = mock_favorite_products

    # Act
    response = client.get("/api/v1/products/favorites") # Modified: Added /api/v1 prefix, matched to router

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_favorite_products

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_user_favorites.assert_called_once_with(ANY, user_id) # Modified: user_id is already an int

@pytest.mark.asyncio
async def test_admin_activate_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    admin_id = client.test_admin_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Use integer product ID for update, matching DAL/Service expectation

    # Configure the mock_product_service.activate_product to do nothing on success
    mock_product_service.activate_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.put(f"/api/v1/products/{product_id}/status/activate") # Modified: Added /api/v1 prefix

    # Assert
    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful activation
    assert response.json()["message"] == "商品已成功激活"

    # Assert that the service method was called with the correct arguments
    mock_product_service.activate_product.assert_called_once_with(ANY, product_id, admin_id) # Modified: admin_id is already an int

@pytest.mark.asyncio
async def test_admin_activate_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int

    # Temporarily override the get_current_active_admin_user dependency
    async def mock_get_current_active_admin_user_forbidden_override():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您无权审核商品")

    original_dependency = app.dependency_overrides.get(get_current_active_admin_user_dependency) # Store original
    app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_forbidden_override

    try:
        # Act
        response = client.put(f"/api/v1/products/{product_id}/status/activate") # Modified: Added /api/v1 prefix

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "您无权审核商品"

        # Assert that the service method was NOT called
        mock_product_service.activate_product.assert_not_called()
    finally:
        # Clean up the override
        if original_dependency is None:
            app.dependency_overrides.pop(get_current_active_admin_user_dependency, None)
        else:
            app.dependency_overrides[get_current_active_admin_user_dependency] = original_dependency

@pytest.mark.asyncio
async def test_admin_reject_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    admin_id = client.test_admin_user_id
    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Use integer product ID for update, matching DAL/Service expectation
    # Define a reason for rejection
    reason = "Rejected for testing purposes."

    # Configure the mock_product_service.reject_product to do nothing on success
    mock_product_service.reject_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.put(f"/api/v1/products/{product_id}/status/reject", json={"reason": reason}) # Modified: Added /api/v1 prefix, simplified JSON

    # Assert
    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful rejection
    assert response.json()["message"] == "商品已成功拒绝"

    # Assert that the service method was called with the correct arguments
    mock_product_service.reject_product.assert_called_once_with(ANY, product_id, admin_id, reason) # Modified: admin_id is already an int

@pytest.mark.asyncio
async def test_admin_reject_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Define a fake product ID for the test
    product_id = int(uuid.UUID(mock_products_all[0]["商品ID"])) # Modified: Changed to int
    # Define a reason for rejection
    reason = "Attempted rejection without admin permission."

    # Temporarily override the get_current_active_admin_user dependency
    async def mock_get_current_active_admin_user_forbidden_override():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您无权审核商品")

    original_dependency = app.dependency_overrides.get(get_current_active_admin_user_dependency) # Store original
    app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_forbidden_override

    try:
        # Act
        response = client.put(f"/api/v1/products/{product_id}/status/reject", json={"reason": reason}) # Modified: Added /api/v1 prefix, simplified JSON

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "您无权审核商品"

        # Assert that the service method was NOT called
        mock_product_service.reject_product.assert_not_called()
    finally:
        # Clean up the override
        if original_dependency is None:
            app.dependency_overrides.pop(get_current_active_admin_user_dependency, None)
        else:
            app.dependency_overrides[get_current_active_admin_user_dependency] = original_dependency

@pytest.mark.asyncio
async def test_admin_batch_activate_products(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    admin_id = client.test_admin_user_id
    # Define fake product IDs for the test
    product_ids_int = [int(uuid.UUID(mock_products_all[0]["商品ID"])), int(uuid.UUID(mock_products_all[1]["商品ID"])), int(uuid.UUID(mock_products_all[2]["商品ID"]))] # Use integer IDs, matching DAL/Service expectation
    product_ids_str = [mock_products_all[0]["商品ID"], mock_products_all[1]["商品ID"], mock_products_all[2]["商品ID"]] # Keep for JSON payload

    # Configure the mock_product_service.batch_activate_products to return a success count
    success_count = len(product_ids_int)
    mock_product_service.batch_activate_products.return_value = success_count

    # Act
    # Send request using the client with mocked dependencies
    response = client.post(
        "/api/v1/products/batch/activate", # Modified: Added /api/v1 prefix
        json={
            "product_ids": product_ids_str,
        },
        headers={
            "Authorization": "Bearer fake-admin-token" # Placeholder token for clarity
        }
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == f"成功激活 {success_count} 件商品"

    # Assert that the service method was called with the correct arguments
    # The service's batch_activate_products expects conn, product_ids (List[int]), admin_id (int)

    mock_product_service.batch_activate_products.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.batch_activate_products.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_ids (List[int])
    # arg[2] should be admin_id (int)

    assert args[1] == product_ids_int # Check product_ids (convert to int)
    assert args[2] == admin_id # Modified: admin_id is already an int

@pytest.mark.asyncio
async def test_admin_batch_review_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Define fake product IDs for the test
    product_ids_str = [str(uuid4()) for _ in range(3)] # Use string UUIDs for API request
    new_status = "Active" # Or "Rejected"
    reason = "Batch review attempt without admin permission." # Define reason

    # Temporarily override the get_current_active_admin_user dependency
    async def mock_get_current_active_admin_user_forbidden_override():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您无权审核商品")

    original_dependency = app.dependency_overrides.get(get_current_active_admin_user_dependency) # Store original
    app.dependency_overrides[get_current_active_admin_user_dependency] = mock_get_current_active_admin_user_forbidden_override

    try:
        # Determine the endpoint based on new_status
        if new_status == "Active":
            endpoint = "/api/v1/products/batch/activate"
        elif new_status == "Rejected":
            endpoint = "/api/v1/products/batch/reject"
        else:
            endpoint = "" # Should not happen in this test

        # Act
        # Simulate the API request for batch review
        response = client.post(
            endpoint, # Modified: Use specific endpoint
            json={
                "product_ids": product_ids_str, # Use string UUIDs for payload
                "reason": reason if new_status == "Rejected" else None # Reason only for rejection
            },
            headers={
                "Authorization": "Bearer fake-token" # Use a placeholder token for clarity
            }
        )

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "您无权审核商品"

        # Assert that the service methods were NOT called
        mock_product_service.batch_activate_products.assert_not_called()
        mock_product_service.batch_reject_products.assert_not_called()
    finally:
        # Clean up the override
        if original_dependency is None:
            app.dependency_overrides.pop(get_current_active_admin_user_dependency, None)
        else:
            app.dependency_overrides[get_current_active_admin_user_dependency] = original_dependency

@pytest.mark.asyncio
async def test_get_product_list_filter_pagination_sorting_combinations(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define comprehensive mock product data for various filter, pagination, and sorting scenarios
    # mock_products_all is already defined at the top of the file
    global mock_products_all # Use the global mock_products_all

    # Configure the mock_product_service.get_product_list side effect
    async def mock_get_product_list_side_effect(conn, category_id=None, status=None, keyword=None, min_price=None, max_price=None, order_by='PostTime', page_number=1, page_size=10, **kwargs):
        # Map integer category_id to string category name for filtering mock data
        category_id_to_name = {
            1: "Electronics",
            2: "Books",
            3: "Other", # Added mapping for category 3
            4: "Home", # Added mapping for category 4
            5: "Sports", # Added mapping for category 5
            # Add other mappings as needed
        }
        category_name_filter = category_id_to_name.get(category_id) if isinstance(category_id, int) else category_id

        status_filter = status # Corrected: Use status directly
        search_query = keyword # Corrected: Use keyword directly
        min_price_filter = min_price # Corrected: Use min_price directly
        max_price_filter = max_price # Corrected: Use max_price directly
        page_number_filter = page_number # Corrected: Use page_number directly
        page_size_filter = page_size # Corrected: Use page_size directly
        order_by_field = order_by # Corrected: Use order_by directly
        sort_order = kwargs.get("sortOrder", "DESC")

        # Apply filters
        filtered_products = []
        for p in mock_products_all:
            is_match = True

            if status_filter and p["商品状态"] != status_filter:
                is_match = False

            if is_match and category_name_filter and p.get("商品类别") != category_name_filter:
                is_match = False

            if is_match and search_query:
                if not (search_query.lower() in p["商品名称"].lower() or (p.get("商品描述") and search_query.lower() in p["商品描述"].lower())):
                    is_match = False

            if is_match and min_price_filter is not None and p["价格"] < min_price_filter:
                is_match = False
            if is_match and max_price_filter is not None and p["价格"] > max_price_filter:
                is_match = False

            if is_match:
                filtered_products.append(p)

        # Apply sorting
        def get_sort_key(product):
            if order_by_field == "Price":
                return product["价格"]
            elif order_by_field == "ProductName":
                return product["商品名称"]
            elif order_by_field == "PostTime":
                # Convert ISO format string to datetime for proper comparison
                return datetime.fromisoformat(product["发布时间"])
            return datetime.fromisoformat(product["发布时间"]) # Default sort key

        # Determine reverse_sort based on order_by, as API doesn't take sortOrder directly
        # Assume PostTime is DESC by default, others ASC by default if not specified
        reverse_sort = True if order_by_field == "PostTime" else False
        sorted_products = sorted(filtered_products, key=get_sort_key, reverse=reverse_sort)

        # Apply pagination
        start_index = (page_number_filter - 1) * page_size_filter
        end_index = start_index + page_size_filter
        paginated_products = sorted_products[start_index:end_index]

        # Update total count in the paginated results
        total_count = len(filtered_products)
        for p in paginated_products:
             p["总商品数"] = total_count

        return paginated_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Filter by Category and Price Range, Paginate and Sort by Price ASC
    response1 = client.get("/api/v1/products", params={
        "category_id": 1, # Changed to category_id (int)
        "min_price": 1000.00,
        "max_price": 7000.00,
        "page_number": 1,
        "page_size": 2,
        "order_by": "Price",
        # "sortOrder": "ASC" # Removed, as API doesn't support this directly
    })

    assert response1.status_code == status.HTTP_200_OK
    # Expected products: Sony WH-1000XM4 (1999.00), Samsung Galaxy S21 (5999.00) or other if data changed
    # Assuming the sorted products based on mock_products_all and filters
    # Let's define the expected result based on the current mock_products_all and filter criteria
    expected_products_1 = [
        # After filtering for Electronics, min_price=1000, max_price=7000, and sorting by Price ASC:
        # Original: Sony(1999), Samsung(5999), Logitech(599)
        # Filtered & Sorted: Sony(1999), Samsung(5999)
        # After pagination (page 1, size 2):
        {
            "商品ID": mock_products_all[0]["商品ID"],
            "商品名称": "Sony WH-1000XM4",
            "商品描述": "Noise-cancelling headphones",
            "库存": 15,
            "价格": 1999.00,
            "发布时间": "2023-01-05T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "Electronics",
            "主图URL": "/uploads/sony.jpg",
            "images": [],
            "总商品数": 2 # Use fixed value
        },
        {
            "商品ID": mock_products_all[1]["商品ID"],
            "商品名称": "Samsung Galaxy S21",
            "商品描述": "Android smartphone",
            "库存": 20,
            "价格": 5999.00,
            "发布时间": "2023-01-01T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller2",
            "商品类别": "Electronics",
            "主图URL": "/uploads/galaxy.jpg",
            "images": [],
            "总商品数": 2 # Use fixed value
        }
    ]
    assert response1.json() == expected_products_1
    mock_product_service.get_product_list.assert_any_call(
        ANY,
        1, # category_id (int)
        None, # status
        None, # keyword
        1000.00, # min_price
        7000.00, # max_price
        "Price", # order_by
        1, # page_number
        2, # page_size
    )

    # Test case 2: Filter by Status and Keyword, Paginate and Sort by PostTime DESC
    response2 = client.get("/api/v1/products", params={
        "status": "Active",
        "keyword": "mouse",
        "page_number": 1,
        "page_size": 1,
        "order_by": "PostTime",
        # "sortOrder": "DESC" # Removed, as API doesn't support this directly
    })
    assert response2.status_code == status.HTTP_200_OK
    expected_products_2 = [
        # After filtering for Active, keyword='mouse', and sorting by PostTime DESC:
        # Original: Logitech MX Master 3 (Active, 'mouse' in name)
        # Filtered & Sorted:
        {
            "商品ID": mock_products_all[2]["商品ID"],
            "商品名称": "Logitech MX Master 3",
            "商品描述": "Advanced wireless mouse",
            "库存": 25,
            "价格": 599.00,
            "发布时间": "2023-01-07T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "Electronics",
            "主图URL": "/uploads/logitech.jpg",
            "images": [],
            "总商品数": 1 # Use fixed value
        }
    ]
    assert response2.json() == expected_products_2
    mock_product_service.get_product_list.assert_any_call(
        ANY,
        None, # category_id
        "Active", # status
        "mouse", # keyword
        None, None, # min_price, max_price
        "PostTime", # order_by
        1, # page_number
        1, # page_size
    )

    # Test case 3: Filter by Category and Status, and Keyword
    response3 = client.get("/api/v1/products", params={
        "category_id": 2, # Changed to category_id (int)
        "status": "Active",
        "keyword": "gatsby"
    })
    assert response3.status_code == status.HTTP_200_OK
    expected_products_3 = [
        # After filtering for Books, Active, keyword='gatsby':
        # Original: The Great Gatsby (Books, Active, 'gatsby' in name)
        {
            "商品ID": mock_products_all[3]["商品ID"],
            "商品名称": "The Great Gatsby",
            "商品描述": "Classic novel by F. Scott Fitzgerald",
            "库存": 30,
            "价格": 68.00,
            "发布时间": "2023-01-09T10:00:00.000000", # Use fixed value
            "商品状态": "Active",
            "发布者用户名": "seller3",
            "商品类别": "Books",
            "主图URL": "/uploads/gatsby.jpg",
            "images": [],
            "总商品数": 1 # Use fixed value
        }
    ]
    assert response3.json() == expected_products_3
    mock_product_service.get_product_list.assert_any_call(
        ANY,
        2, # category_id (int)
        "Active", # status
        "gatsby", # keyword
        None, None, # min_price, max_price
        'PostTime', 1, 10
    )