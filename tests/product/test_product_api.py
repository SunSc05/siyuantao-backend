import pytest
from fastapi import status
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from uuid import uuid4
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
    test_user_id = uuid4() # Use a unique ID for each test run
    return {"user_id": test_user_id, "UserID": str(test_user_id), "username": "testuser", "is_staff": False, "is_verified": True}

async def mock_get_current_active_admin_user_override():
    # Return a dict that matches the expected payload structure for an admin user
    test_admin_user_id = uuid4() # Use a unique ID for each test run
    return {"user_id": test_admin_user_id, "UserID": str(test_admin_user_id), "username": "adminuser", "is_staff": True, "is_verified": True}

async def mock_get_current_authenticated_user_override():
    # Return a UserResponseSchema-like dict for an authenticated user
    test_auth_user_id = uuid4()
    return {"user_id": test_auth_user_id, "UserID": str(test_auth_user_id), "username": "authuser", "email": "auth@example.com", "status": "Active", "credit": 100, "is_staff": False, "is_super_admin": False, "is_verified": True, "major": "", "avatar_url": None, "bio": None, "phone_number": "1234567890", "join_time": datetime.now().isoformat()}


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
        tc.test_user_id = uuid4()
        tc.test_admin_user_id = uuid4()
        tc.test_auth_user_id = uuid4()
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
        "/api/v1/products",
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
    assert response.json()["message"] == "Product created successfully"

    # Assert that the service method was called with the correct arguments
    # The service's create_product expects conn, owner_id (UUID), category_name, product_name, description, quantity, price, image_urls
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
    # arg[1] should be the owner_id (UUID)
    # arg[2] should be category_name
    # arg[3] should be product_name
    # arg[4] should be description
    # arg[5] should be quantity
    # arg[6] should be price
    # arg[7] should be image_urls (list of strings)

    assert args[1] == test_owner_id # Check owner_id
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
    product_ids = [str(uuid4()) for _ in range(3)]
    
    # Mock the service layer call for batch activation
    # The service's batch_activate_products method is expected to return the count of successfully activated products.
    mock_product_service.batch_activate_products.return_value = 3 # Simulate successful activation of 3 products
    
    # Act
    # Send request using the client with mocked dependencies
    response = client.post(
        "/api/v1/products/batch-review",
        json={
            "productIds": product_ids,
            "newStatus": "Active",
            "reason": ""  # Activation doesn't require a reason
        },
        headers={
            "Authorization": "Bearer fake-admin-token" # Placeholder token for clarity
        }
    )
    
    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["successCount"] == 3

    # Assert that the service method was called with the correct arguments
    # The service's batch_activate_products expects conn, product_ids (List[int] - although schema says List[str]), admin_id (int - although schema says UUID)
    # Note: There seems to be a type mismatch between the OpenAPI schema (List[int], int) and the service method signature (List[int], int). The router is sending List[str] and UUID.
    # We should assert based on what the router *actually* sends, which is List[str] and UUID.

    mock_product_service.batch_activate_products.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.batch_activate_products.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_ids (List[str])
    # arg[2] should be admin_id (UUID)

    assert args[1] == product_ids # Check product_ids (list of strings)
    assert args[2] == test_admin_id # Check admin_id (UUID)

@pytest.mark.asyncio
async def test_add_favorite(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, authentication is mocked.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    test_user_id = client.test_auth_user_id

    # Generate a fake product ID
    fake_product_id = uuid4()

    # Mock the service layer call for adding a favorite
    # The service's add_favorite method is expected to return None on success.
    mock_product_service.add_favorite.return_value = None # Simulate successful addition

    # Act
    # Send request using the client with mocked dependencies
    response = client.post(
        f"/api/v1/favorites/{fake_product_id}",
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token for clarity
        }
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Product added to favorites successfully"

    # Assert that the service method was called with the correct arguments
    # The service's add_favorite expects conn, user_id (UUID), product_id (UUID)

    mock_product_service.add_favorite.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.add_favorite.call_args

    # arg[0] is the mocked connection
    # arg[1] should be user_id (UUID)
    # arg[2] should be product_id (UUID)

    assert args[1] == test_user_id # Check user_id
    assert args[2] == fake_product_id # Check product_id

@pytest.mark.asyncio
async def test_get_product_list(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data that the service should return
    # This data should match the structure returned by the sp_GetProductList and sp_GetProductDetail (for images)
    # and should use the Chinese aliases defined in the stored procedures.
    mock_product_list_data = [
        {
            "商品ID": str(uuid4()),
            "商品名称": "测试商品1",
            "商品描述": "描述1",
            "库存": 10,
            "价格": 100.0,
            "发布时间": datetime.now().isoformat(), # Return as ISO 8601 string
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "分类A",
            "主图URL": "http://example.com/img1_main.jpg",
            "总商品数": 3, # Total count for pagination
            "images": [
                {"图片ID": str(uuid4()), "商品ID": "", "图片URL": "http://example.com/img1_main.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 0},
                {"图片ID": str(uuid4()), "商品ID": "", "图片URL": "http://example.com/img1_alt.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 1},
            ] # Include nested images
        },
        {
            "商品ID": str(uuid4()),
            "商品名称": "测试商品2",
            "商品描述": "描述2",
            "库存": 20,
            "价格": 200.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller2",
            "商品类别": "分类B",
            "主图URL": "http://example.com/img2_main.jpg",
            "总商品数": 3,
             "images": [
                {"图片ID": str(uuid4()), "商品ID": "", "图片URL": "http://example.com/img2_main.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 0},
            ]
        },
        {
            "商品ID": str(uuid4()),
            "商品名称": "测试商品3",
            "商品描述": "描述3",
            "库存": 15,
            "价格": 150.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "分类A",
            "主图URL": None, # Simulate no main image
            "总商品数": 3,
            "images": [] # Simulate no images
        }
    ]

    # Mock the service's get_product_list method to return the mock data
    # The service method expects conn and optional filter/pagination/sorting parameters.
    mock_product_service.get_product_list.return_value = mock_product_list_data

    # Act
    # Send GET request to the products endpoint
    response = client.get("/api/v1/products")

    # Assert
    assert response.status_code == status.HTTP_200_OK

    # Assert the response body matches the mock data structure and content
    products = response.json()
    assert isinstance(products, list)
    assert len(products) == len(mock_product_list_data)

    # Assert that the service method was called with the correct (default) arguments
    # The service's get_product_list expects conn, category_id, status, keyword, min_price, max_price, order_by, page_number, page_size

    mock_product_service.get_product_list.assert_called_once()

    # Check the arguments (should be default values except for connection)
    args, kwargs = mock_product_service.get_product_list.call_args

    # arg[0] is the mocked connection
    # Keyword arguments should match the default values in the service method
    assert kwargs.get('category_id') is None
    assert kwargs.get('status') is None # API default is 'Active', but service default might be None or require passing from API
    assert kwargs.get('keyword') is None
    assert kwargs.get('min_price') is None
    assert kwargs.get('max_price') is None
    assert kwargs.get('order_by') == 'PostTime'
    assert kwargs.get('page_number') == 1
    assert kwargs.get('page_size') == 10 # API default is 20, service default is 10. Need to reconcile.
    # Assuming API passes default 20, service should expect 20. Let's update expected call.
    assert kwargs.get('page_size') == 20 # Corrected assertion based on API router default

    # Compare returned data with mock data (basic check)
    # This is a simplified check; a more thorough test would compare specific fields and structures.
    returned_product_names = [p.get("商品名称") for p in products]
    assert "测试商品1" in returned_product_names
    assert "测试商品2" in returned_product_names
    assert "测试商品3" in returned_product_names

    # Check structure of returned products
    if products:
        sample_product = products[0]
        expected_keys = ["商品ID", "商品名称", "商品描述", "库存", "价格", "发布时间", "商品状态", "发布者用户名", "商品类别", "主图URL", "总商品数", "images"]
        for key in expected_keys:
            assert key in sample_product
        assert isinstance(sample_product["images"], list)
        if sample_product["images"]:
             sample_image = sample_product["images"][0]
             expected_image_keys = ["图片ID", "商品ID", "图片URL", "上传时间", "显示顺序"]
             for key in expected_image_keys:
                  assert key in sample_image

@pytest.mark.asyncio
async def test_get_product_detail(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, data is mocked.

    # Generate a fake product ID for the test
    test_product_id = uuid4()

    # Define mock product detail data that the service should return
    # This data should match the structure returned by sp_GetProductDetail
    mock_product_detail_data = {
        "商品ID": str(test_product_id),
        "商品名称": "测试详情商品",
        "商品描述": "详细描述",
        "库存": 5,
        "价格": 300.0,
        "发布时间": datetime.now().isoformat(),
        "商品状态": "Active",
        "发布者用户名": "seller1",
        "发布者头像URL": "http://example.com/avatar.jpg",
        "商品类别": "电子产品",
        "images": [
            {"图片ID": str(uuid4()), "商品ID": str(test_product_id), "图片URL": "http://example.com/detail_img1.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 0},
            {"图片ID": str(uuid4()), "商品ID": str(test_product_id), "图片URL": "http://example.com/detail_img2.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 1},
        ] # Include nested images
    }

    # Mock the service's get_product_detail method to return the mock data
    # The service method expects conn and product_id.
    mock_product_service.get_product_detail.return_value = mock_product_detail_data

    # Act
    # Send GET request to the product detail endpoint
    response = client.get(f"/api/v1/products/{test_product_id}")

    # Assert
    assert response.status_code == status.HTTP_200_OK

    # Assert the response body matches the mock data structure and content
    product = response.json()
    assert isinstance(product, dict)
    assert product.get("商品ID") == str(test_product_id)
    assert product.get("商品名称") == "测试详情商品"
    assert product.get("发布者用户名") == "seller1"
    assert "images" in product
    assert isinstance(product["images"], list)
    assert len(product["images"]) == 2
    # Basic check for image structure
    if product["images"]:
         sample_image = product["images"][0]
         expected_image_keys = ["图片ID", "商品ID", "图片URL", "上传时间", "显示顺序"]
         for key in expected_image_keys:
              assert key in sample_image

    # Assert that the service method was called with the correct arguments
    # The service's get_product_detail expects conn and product_id (UUID)

    mock_product_service.get_product_detail.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.get_product_detail.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (UUID)

    assert args[1] == test_product_id # Check product_id

@pytest.mark.asyncio
async def test_get_product_detail_not_found(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # Generate a fake product ID that won't be found
    fake_product_id = uuid4()

    # Mock the service's get_product_detail method to return None, simulating not found
    mock_product_service.get_product_detail.return_value = None

    # Act
    # Send GET request to the product detail endpoint with the fake ID
    response = client.get(f"/api/v1/products/{fake_product_id}")

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # The API router should raise HTTPException(404) with detail "Product not found"
    assert "Product not found" in response.json()["detail"] or "商品不存在" in response.json()["detail"]

    # Assert that the service method was called with the correct arguments
    mock_product_service.get_product_detail.assert_called_once()
    args, kwargs = mock_product_service.get_product_detail.call_args
    assert args[1] == fake_product_id # Check product_id

@pytest.mark.asyncio
async def test_update_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user (owner)
    test_owner_id = client.test_auth_user_id

    # Generate a fake product ID for the product to be updated
    test_product_id = uuid4()

    # Define the update data
    update_data = {
        "product_name": "更新后的测试商品",
        "price": 123.45,
        "quantity": 5,
        "description": "更新后的描述",
        "category_name": "更新分类",
        "image_urls": ["http://newimage.com/img1.jpg", "http://newimage.com/img2.jpg"]
    }

    # Define the expected return value from the service after update
    # This should be the updated product details, matching the structure of sp_GetProductDetail
    # and including the Chinese aliases.
    updated_product_data = {
        "商品ID": str(test_product_id),
        "商品名称": update_data["product_name"],
        "商品描述": update_data["description"],
        "库存": update_data["quantity"],
        "价格": update_data["price"],
        "发布时间": datetime.now().isoformat(),
        "商品状态": "Active", # Assuming update doesn't change status to PendingReview
        "发布者用户名": "authuser", # Matches the mocked authenticated user
        "发布者头像URL": "http://example.com/avatar.jpg", # Example avatar URL
        "商品类别": update_data["category_name"],
        "images": [
            {"图片ID": str(uuid4()), "商品ID": str(test_product_id), "图片URL": "http://newimage.com/img1.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 0},
            {"图片ID": str(uuid4()), "商品ID": str(test_product_id), "图片URL": "http://newimage.com/img2.jpg", "上传时间": datetime.now().isoformat(), "显示顺序": 1},
        ] # Updated images
    }

    # Mock the service's update_product method to return the updated product data
    # The service method expects conn, product_id, owner_id, and a ProductUpdate schema.
    # It should return the updated product data dictionary.
    mock_product_service.update_product.return_value = updated_product_data

    # Act
    # Send PUT request using the client with mocked dependencies
    response = client.put(
        f"/api/v1/products/{test_product_id}",
        json=update_data,
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token for clarity
        }
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK

    # Assert the response body matches the expected updated product data
    returned_product = response.json()
    assert isinstance(returned_product, dict)
    assert returned_product.get("商品ID") == str(test_product_id)
    assert returned_product.get("商品名称") == update_data["product_name"]
    assert returned_product.get("价格") == update_data["price"]
    assert returned_product.get("库存") == update_data["quantity"]
    assert returned_product.get("商品描述") == update_data["description"]
    assert returned_product.get("商品类别") == update_data["category_name"]
    assert "images" in returned_product
    assert isinstance(returned_product["images"], list)
    assert len(returned_product["images"]) == 2
    # More detailed assertions for image data can be added if needed.

    # Assert that the service method was called with the correct arguments
    # The service's update_product expects conn, product_id (UUID), owner_id (UUID), and product_update_data (ProductUpdate schema)

    mock_product_service.update_product.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.update_product.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (UUID)
    # arg[2] should be owner_id (UUID)
    # arg[3] should be a ProductUpdate schema object

    assert args[1] == test_product_id # Check product_id
    assert args[2] == test_owner_id # Check owner_id
    assert isinstance(args[3], ProductUpdate) # Check if the third argument is a ProductUpdate schema
    assert args[3].model_dump(exclude_none=True) == update_data # Check the content of the schema

@pytest.mark.asyncio
async def test_update_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use a different user ID to simulate a non-owner attempting the update
    non_owner_user_id = uuid4()

    # Generate a fake product ID
    test_product_id = uuid4()

    # Define the update data
    update_data = {
        "product_name": "尝试更新的商品"
    }

    # Mock the service layer call to raise a PermissionError
    # The service method expects conn, product_id, owner_id, and ProductUpdate schema.
    mock_product_service.update_product.side_effect = PermissionError("You are not the owner of this product.")

    # Act
    # Send PUT request using the client with mocked dependencies
    # The mocked get_current_authenticated_user_override will return the non_owner_user_id
    response = client.put(
        f"/api/v1/products/{test_product_id}",
        json=update_data,
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token
        }
    )

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "You are not the owner of this product" in response.json()["detail"] or "无权修改此商品" in response.json()["detail"]

    # Assert that the service method was called with the correct arguments
    mock_product_service.update_product.assert_called_once()
    args, kwargs = mock_product_service.update_product.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (UUID)
    # arg[2] should be the user_id from the mocked authentication (non_owner_user_id)
    # arg[3] should be a ProductUpdate schema object

    assert args[1] == test_product_id # Check product_id
    assert args[2] == client.test_auth_user_id # Check owner_id (should be the authenticated user's ID)
    assert isinstance(args[3], ProductUpdate) # Check schema type
    assert args[3].model_dump(exclude_none=True) == update_data # Check schema content

@pytest.mark.asyncio
async def test_delete_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user (owner)
    test_owner_id = client.test_auth_user_id

    # Generate a fake product ID for the product to be deleted
    test_product_id = uuid4()

    # Mock the service layer call for deleting a product
    # The service's delete_product method is expected to return None on success.
    mock_product_service.delete_product.return_value = None # Simulate successful deletion

    # Act
    # Send DELETE request using the client with mocked dependencies
    response = client.delete(
        f"/api/v1/products/{test_product_id}",
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token for clarity
        }
    )

    # Assert
    assert response.status_code == status.HTTP_204_NO_CONTENT # Expect 204 No Content for successful deletion

    # Assert that the service method was called with the correct arguments
    # The service's delete_product expects conn, product_id (UUID), owner_id (UUID)

    mock_product_service.delete_product.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.delete_product.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (UUID)
    # arg[2] should be owner_id (UUID)

    assert args[1] == test_product_id # Check product_id
    assert args[2] == test_owner_id # Check owner_id

@pytest.mark.asyncio
async def test_withdraw_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use the test_auth_user_id from the client fixture for simulating the current user (owner)
    test_owner_id = client.test_auth_user_id

    # Generate a fake product ID for the product to be withdrawn
    test_product_id = uuid4()

    # Mock the service layer call for withdrawing a product
    # The service's withdraw_product method is expected to return None on success.
    mock_product_service.withdraw_product.return_value = None # Simulate successful withdrawal

    # Act
    # Send PUT request using the client with mocked dependencies
    response = client.put(
        f"/api/v1/products/{test_product_id}/withdraw",
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token for clarity
        }
    )

    # Assert
    assert response.status_code == status.HTTP_200_OK # Expect 200 OK for successful withdrawal

    # Assert that the service method was called with the correct arguments
    # The service's withdraw_product expects conn, product_id (UUID), owner_id (UUID)

    mock_product_service.withdraw_product.assert_called_once()

    # Check the arguments
    args, kwargs = mock_product_service.withdraw_product.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (UUID)
    # arg[2] should be owner_id (UUID)

    assert args[1] == test_product_id # Check product_id
    assert args[2] == test_owner_id # Check owner_id

@pytest.mark.asyncio
async def test_withdraw_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.
    # The mock_get_current_authenticated_user_override provides the authenticated user's info.

    # Use a different user ID to simulate a non-owner attempting the withdrawal
    non_owner_user_id = uuid4()

    # Generate a fake product ID
    test_product_id = uuid4()

    # Mock the service layer call to raise a PermissionError
    # The service method expects conn, product_id, owner_id.
    mock_product_service.withdraw_product.side_effect = PermissionError("You are not the owner of this product.")

    # Act
    # Send PUT request using the client with mocked dependencies
    # The mocked get_current_authenticated_user_override will return the non_owner_user_id
    response = client.put(
        f"/api/v1/products/{test_product_id}/withdraw",
        headers={
            "Authorization": "Bearer fake-token" # Placeholder token
        }
    )

    # Assert
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "You are not the owner of this product" in response.json()["detail"] or "无权下架此商品" in response.json()["detail"]

    # Assert that the service method was called with the correct arguments
    mock_product_service.withdraw_product.assert_called_once()
    args, kwargs = mock_product_service.withdraw_product.call_args

    # arg[0] is the mocked connection
    # arg[1] should be product_id (UUID)
    # arg[2] should be the user_id from the mocked authentication (non_owner_user_id)

    assert args[1] == test_product_id # Check product_id
    assert args[2] == client.test_auth_user_id # Check owner_id (should be the authenticated user's ID)

@pytest.mark.asyncio
async def test_get_product_list_filter_by_category(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data filtered by category
    mock_filtered_product_list_data = [
        {
            "商品ID": str(uuid4()),
            "商品名称": "电子商品 A",
            "商品描述": "描述 A",
            "库存": 10,
            "价格": 100.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "电子产品",
            "主图URL": "http://example.com/elec_a.jpg",
            "总商品数": 2,
            "images": []
        },
        {
            "商品ID": str(uuid4()),
            "商品名称": "电子商品 B",
            "商品描述": "描述 B",
            "库存": 20,
            "价格": 200.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller2",
            "商品类别": "电子产品",
            "主图URL": "http://example.com/elec_b.jpg",
            "总商品数": 2,
            "images": []
        }
    ]

    # Mock the service's get_product_list method to return the filtered mock data
    # It should be called with categoryName='电子产品'
    mock_product_service.get_product_list.return_value = mock_filtered_product_list_data

    # Act
    # Send GET request with category filter
    response = client.get("/api/v1/products", params={
        "categoryName": "电子产品"
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK

    # Assert the response body matches the filtered mock data
    products = response.json()
    assert isinstance(products, list)
    assert len(products) == len(mock_filtered_product_list_data)
    for product in products:
        assert product.get("商品类别") == "电子产品"

    # Assert that the service method was called with the correct category filter
    mock_product_service.get_product_list.assert_called_once()
    args, kwargs = mock_product_service.get_product_list.call_args
    assert kwargs.get('category_id') == "电子产品" # Check categoryName filter (API passes categoryName)
    # Check other default parameters are passed as expected
    assert kwargs.get('status') is None
    assert kwargs.get('keyword') is None
    assert kwargs.get('min_price') is None
    assert kwargs.get('max_price') is None
    assert kwargs.get('order_by') == 'PostTime'
    assert kwargs.get('page_number') == 1
    assert kwargs.get('page_size') == 20

@pytest.mark.asyncio
async def test_get_product_list_filter_by_price_range(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data filtered by price range (100-200)
    mock_filtered_product_list_data = [
        {
            "商品ID": str(uuid4()),
            "商品名称": "中价商品",
            "商品描述": "描述",
            "库存": 15,
            "价格": 150.0,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller1",
            "商品类别": "分类B",
            "主图URL": "http://example.com/mid_price.jpg",
            "总商品数": 1,
            "images": []
        }
    ]

    # Mock the service's get_product_list method to return the filtered mock data
    # It should be called with minPrice=100 and maxPrice=200
    mock_product_service.get_product_list.return_value = mock_filtered_product_list_data

    # Act
    # Send GET request with price range filter
    response = client.get("/api/v1/products", params={
        "minPrice": 100,
        "maxPrice": 200
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK

    # Assert the response body matches the filtered mock data
    products = response.json()
    assert isinstance(products, list)
    assert len(products) == len(mock_filtered_product_list_data)
    for product in products:
        price = product.get("价格")
        assert price is not None
        assert 100.0 <= price <= 200.0

    # Assert that the service method was called with the correct price range filters
    mock_product_service.get_product_list.assert_called_once()
    args, kwargs = mock_product_service.get_product_list.call_args
    assert kwargs.get('min_price') == 100.0 # Check min_price filter (API passes minPrice, service expects min_price float)
    assert kwargs.get('max_price') == 200.0 # Check max_price filter (API passes maxPrice, service expects max_price float)
    # Check other default parameters are passed as expected
    assert kwargs.get('category_id') is None
    assert kwargs.get('status') is None
    assert kwargs.get('keyword') is None
    assert kwargs.get('order_by') == 'PostTime'
    assert kwargs.get('page_number') == 1
    assert kwargs.get('page_size') == 20

@pytest.mark.asyncio
async def test_get_product_list_search_keyword(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data for keyword search tests
    mock_products_all = [
        {
            "商品ID": str(uuid4()), "商品名称": "Laptop Dell", "商品描述": "Powerful laptop", "库存": 10, "价格": 800.00, "发布时间": datetime.now().isoformat(), "商品状态": "Active", "发布者用户名": "seller_user", "商品类别": "Electronics", "主图URL": "/uploads/laptop1.jpg", "总商品数": 0, "images": []
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Wireless Keyboard", "商品描述": "Ergonomic keyboard", "库存": 20, "价格": 75.00, "发布时间": datetime.now().isoformat(), "商品状态": "Active", "发布者用户名": "seller_user", "商品类别": "Electronics", "主图URL": "/uploads/keyboard1.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Ergonomic Mouse", "商品描述": "Wireless mouse", "库存": 15, "价格": 25.00, "发布时间": datetime.now().isoformat(), "商品状态": "Active", "发布者用户名": "seller_user", "商品类别": "Electronics", "主图URL": "/uploads/mouse1.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Book Thriller", "商品描述": "Exciting story about adventure", "库存": 5, "价格": 15.00, "发布时间": datetime.now().isoformat(), "商品状态": "Active", "发布者用户名": "seller_user", "商品类别": "Books", "主图URL": "/uploads/book1.jpg", "images": [], "总商品数": 0
        },
    ]

    # Configure the mock_product_service.get_product_list side effect for keyword search
    async def mock_get_product_list_side_effect(conn, **kwargs):
        keyword = kwargs.get("searchQuery", None)
        status_filter = kwargs.get("status", "Active") # Assuming default status is Active

        filtered_products = []
        for p in mock_products_all:
            is_match = True

            # Apply status filter first
            if status_filter and p["商品状态"] != status_filter:
                is_match = False

            # Apply keyword filter if status matches
            if is_match and keyword:
                if not (keyword.lower() in p["商品名称"].lower() or (p.get("商品描述") and keyword.lower() in p["商品描述"].lower())):
                    is_match = False

            if is_match:
                filtered_products.append(p)
        
        # Update total count for filtered results
        total_count = len(filtered_products)
        for p in filtered_products:
            p["总商品数"] = total_count
             
        # Return filtered products (no pagination/sorting in this specific test mock)
        return filtered_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Search by keyword in name
    response1 = client.get("/api/v1/products", params={
        "keyword": "Laptop",
    })

    assert response1.status_code == status.HTTP_200_OK
    products1 = response1.json()
    assert len(products1) == 1
    assert products1[0]["商品名称"] == "Laptop Dell"
    assert products1[0]["总商品数"] == 1

    # Test case 2: Search by keyword in description (case-insensitive)
    response2 = client.get("/api/v1/products", params={
        "keyword": "powerful",
    })

    assert response2.status_code == status.HTTP_200_OK
    products2 = response2.json()
    assert len(products2) == 1
    assert products2[0]["商品名称"] == "Laptop Dell"
    assert products2[0]["总商品数"] == 1

    # Test case 3: Search by keyword found in multiple products (name or description)
    response3 = client.get("/api/v1/products", params={
        "keyword": "wireless",
    })

    assert response3.status_code == status.HTTP_200_OK
    products3 = response3.json()
    assert len(products3) == 2
    product_names3 = [p["商品名称"] for p in products3]
    assert "Wireless Keyboard" in product_names3
    assert "Ergonomic Mouse" in product_names3
    assert products3[0]["总商品数"] == 2

    # Test case 4: Search by a keyword not found
    response4 = client.get("/api/v1/products", params={
        "keyword": "Tablet",
    })

    assert response4.status_code == status.HTTP_200_OK
    products4 = response4.json()
    assert len(products4) == 0
    assert products4 == []

    # Assert that the mock service's get_product_list method was called with correct parameters for each test case
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        searchQuery='Laptop', categoryName=None, status='Active', minPrice=None, maxPrice=None, order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        searchQuery='powerful', categoryName=None, status='Active', minPrice=None, maxPrice=None, order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        searchQuery='wireless', categoryName=None, status='Active', minPrice=None, maxPrice=None, order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        searchQuery='Tablet', categoryName=None, status='Active', minPrice=None, maxPrice=None, order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC'
    )

@pytest.mark.asyncio
async def test_get_product_list_filter_by_status(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data with various statuses
    mock_products_all = [
        {
            "商品ID": str(uuid4()),
            "商品名称": "待审核商品",
            "商品描述": "This product is pending review.",
            "库存": 5,
            "价格": 10.00,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "PendingReview",
            "发布者用户名": "seller_user",
            "商品类别": "CategoryA",
            "主图URL": "/uploads/pending.jpg",
            "总商品数": 3, # Will be updated based on filter
            "images": []
        },
        {
            "商品ID": str(uuid4()),
            "商品名称": "在售商品",
            "商品描述": "This product is active.",
            "库存": 10,
            "价格": 20.00,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Active",
            "发布者用户名": "seller_user",
            "商品类别": "CategoryA",
            "主图URL": "/uploads/active.jpg",
            "总商品数": 1, # Will be updated based on filter
            "images": []
        },
        {
            "商品ID": str(uuid4()),
            "商品名称": "已售罄商品",
            "商品描述": "This product is sold out.",
            "库存": 0,
            "价格": 30.00,
            "发布时间": datetime.now().isoformat(),
            "商品状态": "Sold",
            "发布者用户名": "seller_user",
            "商品类别": "CategoryB",
            "主图URL": "/uploads/sold.jpg",
            "总商品数": 1, # Will be updated based on filter
            "images": []
        },
    ]

    # Configure the mock_product_service.get_product_list to return filtered results based on status
    async def mock_get_product_list_side_effect(conn, **kwargs):
        status_filter = kwargs.get("status", None)

        if status_filter:
            filtered_products = [p for p in mock_products_all if p["商品状态"] == status_filter]
        else:
            # Default behavior if no status filter is provided (assuming Active status)
            filtered_products = [p for p in mock_products_all if p["商品状态"] == "Active"]

        # Update total count for filtered results
        for p in filtered_products:
            p["总商品数"] = len(filtered_products)

        return filtered_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Filter by PendingReview status
    response_pending = client.get("/api/v1/products", params={
        "status": "PendingReview"
    })

    assert response_pending.status_code == status.HTTP_200_OK
    products_pending = response_pending.json()
    assert len(products_pending) == 1
    assert products_pending[0]["商品名称"] == "待审核商品"

    # Test case 2: Filter by Active status
    response_active = client.get("/api/v1/products", params={
        "status": "Active"
    })

    assert response_active.status_code == status.HTTP_200_OK
    products_active = response_active.json()
    assert len(products_active) == 1
    assert products_active[0]["商品名称"] == "在售商品"

    # Test case 3: Filter by Sold status
    response_sold = client.get("/api/v1/products", params={
        "status": "Sold"
    })

    assert response_sold.status_code == status.HTTP_200_OK
    products_sold = response_sold.json()
    assert len(products_sold) == 1
    assert products_sold[0]["商品名称"] == "已售罄商品"

    # Test case 4: Filter by a non-existent status
    response_nonexistent = client.get("/api/v1/products", params={
        "status": "UnknownStatus"
    })

    assert response_nonexistent.status_code == status.HTTP_200_OK
    products_nonexistent = response_nonexistent.json()
    assert len(products_nonexistent) == 0

    # Test case 5: No status filter (should default to Active)
    response_default = client.get("/api/v1/products")

    assert response_default.status_code == status.HTTP_200_OK
    products_default = response_default.json()
    assert len(products_default) == 1
    assert products_default[0]["商品名称"] == "在售商品"

    # Assert that the mock service's get_product_list method was called with correct parameters for each test case
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, # category_name from params is mapped to category_id in DAL call
        status='Active', # Default status
        keyword=None,
        min_price=None,
        max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName='Electronics' # The raw param name should be passed to the mock
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None,
        status='Active', # Status from params
        keyword='Wireless',
        min_price=None,
        max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None,
        status='Active', # Default status
        keyword='mouse',
        min_price=10.00,
        max_price=30.00,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName='Electronics'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status=None, keyword=None, min_price=None, max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC', # Default parameters
        categoryName=None # Default parameter
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword=None, min_price=100.00, max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName='Books'
    )

@pytest.mark.asyncio
async def test_get_product_list_pagination_and_sorting(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data that the service should return for pagination and sorting
    # This data should match the structure returned by the sp_GetProductList and sp_GetProductDetail (for images)
    # and should use the Chinese aliases defined in the stored procedures.
    mock_products_all = []
    for i in range(15):
        mock_products_all.append({
            "商品ID": str(uuid4()),
            "商品名称": f"商品{i:02d}", # Ensure name sorts numerically
            "商品描述": f"描述{i}",
            "库存": 10 + i,
            "价格": 100.0 + i, # Price increases
            "发布时间": (datetime.now() - timedelta(days=15-i)).isoformat(), # Newer products have higher index
            "商品状态": "Active",
            "发布者用户名": "seller_user",
            "商品类别": "CategoryA",
            "主图URL": f"/uploads/product{i:02d}.jpg",
            "总商品数": 0, # Will be updated based on filter
            "images": []
        })

    # Configure the mock_product_service.get_product_list side effect for pagination and sorting
    async def mock_get_product_list_side_effect(conn, **kwargs):
        page_number = kwargs.get("page_number", 1)
        page_size = kwargs.get("page_size", 10)
        order_by = kwargs.get("orderBy", "PostTime")
        sort_order = kwargs.get("sortOrder", "DESC")
        status_filter = kwargs.get("status", "Active") # Assume default status filter

        # Apply status filter first
        filtered_products = [p for p in mock_products_all if p["商品状态"] == status_filter]
        
        # Apply sorting
        def get_sort_key(product):
            if order_by == "Price":
                return product["价格"]
            elif order_by == "ProductName":
                return product["商品名称"]
            elif order_by == "PostTime":
                 # Convert ISO format string to datetime for proper comparison
                 return datetime.fromisoformat(product["发布时间"])
            return datetime.fromisoformat(product["发布时间"]) # Default sort key

        reverse_sort = sort_order.upper() == "DESC"
        sorted_products = sorted(filtered_products, key=get_sort_key, reverse=reverse_sort)

        # Apply pagination
        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        paginated_products = sorted_products[start_index:end_index]

        # Update total count in the paginated results
        total_count = len(filtered_products)
        for p in paginated_products:
             p["总商品数"] = total_count

        return paginated_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Get first page (default size 10), sorted by PostTime DESC (default)
    response1 = client.get("/api/v1/products", params={})

    assert response1.status_code == status.HTTP_200_OK
    products1 = response1.json()
    assert len(products1) == 10 # Should return 10 products
    # Check sorting by PostTime DESC (newest first)
    # Assuming mock_products_all is created with newer products having higher index
    assert products1[0]["商品名称"] == "商品14"
    assert products1[9]["商品名称"] == "商品05"
    assert products1[0]["总商品数"] == 15 # Total active products

    # Test case 2: Get second page (size 5), sorted by Price ASC
    response2 = client.get("/api/v1/products", params={
        "page_number": 2,
        "page_size": 5,
        "order_by": "Price",
        "sortOrder": "ASC"
    })

    assert response2.status_code == status.HTTP_200_OK
    products2 = response2.json()
    assert len(products2) == 5 # Should return 5 products
    # Check sorting by Price ASC (lowest price first)
    # mock_products_all[0] has price 100, index 0
    # mock_products_all[4] has price 104, index 4
    # mock_products_all[5] has price 105, index 5
    # First page sorted by price ASC would be product 0-4
    # Second page sorted by price ASC would be product 5-9
    assert products2[0]["商品名称"] == "商品05" # Price 105.0
    assert products2[4]["商品名称"] == "商品09" # Price 109.0
    assert products2[0]["总商品数"] == 15 # Total active products

    # Test case 3: Empty page when requesting beyond available data
    response3 = client.get("/api/v1/products", params={
        "page_number": 2,
        "page_size": 10,
    })

    assert response3.status_code == status.HTTP_200_OK
    products3 = response3.json()
    assert len(products3) == 5 # Products 10-14 on second page of 10
    assert products3[0]["商品名称"] == "商品04"
    assert products3[4]["商品名称"] == "商品00"
    assert products3[0]["总商品数"] == 15

    # Test case 4: Page number too large
    response4 = client.get("/api/v1/products", params={
        "page_number": 3,
        "page_size": 10,
    })

    assert response4.status_code == status.HTTP_200_OK
    products4 = response4.json()
    assert len(products4) == 0
    assert products4 == []

    # Assert that the mock service's get_product_list method was called with correct parameters for each test case
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        page_number=1, page_size=10, order_by='PostTime', sortOrder='DESC',
        categoryName=None, status='Active', searchQuery=None, minPrice=None, maxPrice=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        page_number=2, page_size=5, order_by='Price', sortOrder='ASC',
        categoryName=None, status='Active', searchQuery=None, minPrice=None, maxPrice=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        page_number=2, page_size=10, order_by='PostTime', sortOrder='DESC',
        categoryName=None, status='Active', searchQuery=None, minPrice=None, maxPrice=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        page_number=3, page_size=10, order_by='PostTime', sortOrder='DESC',
        categoryName=None, status='Active', searchQuery=None, minPrice=None, maxPrice=None
    )

@pytest.mark.asyncio
async def test_get_product_list_filter_combinations(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define mock product data that covers various filter conditions
    mock_products_all = [
        {
            "商品ID": str(uuid4()), "商品名称": "Laptop Dell", "商品描述": "Powerful laptop", "库存": 10, "价格": 800.00, "发布时间": (datetime.now() - timedelta(days=5)).isoformat(), "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/laptop.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Wireless Keyboard", "商品描述": "Ergonomic keyboard", "库存": 20, "价格": 75.00, "发布时间": (datetime.now() - timedelta(days=2)).isoformat(), "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/keyboard.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Ergonomic Mouse", "商品描述": "Wireless mouse", "库存": 15, "价格": 25.00, "发布时间": (datetime.now() - timedelta(days=1)).isoformat(), "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/mouse.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Adventure Book", "商品描述": "Exciting thriller story", "库存": 5, "价格": 15.00, "发布时间": datetime.now().isoformat(), "商品状态": "PendingReview", "发布者用户名": "seller2", "商品类别": "Books", "主图URL": "/uploads/book.jpg", "images": [], "总商品数": 0
        },
         {
            "商品ID": str(uuid4()), "商品名称": "Fiction Novel", "商品描述": "A long read", "库存": 2, "价格": 20.00, "发布时间": (datetime.now() - timedelta(days=3)).isoformat(), "商品状态": "Active", "发布者用户名": "seller2", "商品类别": "Books", "主图URL": "/uploads/novel.jpg", "images": [], "总商品数": 0
        },
    ]

    # Configure the mock_product_service.get_product_list side effect for filter combinations
    async def mock_get_product_list_side_effect(conn, **kwargs):
        category_name = kwargs.get("categoryName", None)
        status_filter = kwargs.get("status", "Active")
        keyword = kwargs.get("searchQuery", None)
        min_price = kwargs.get("minPrice", None)
        max_price = kwargs.get("maxPrice", None)

        filtered_products = []
        for p in mock_products_all:
            is_match = True

            # Apply filters
            if status_filter and p["商品状态"] != status_filter:
                is_match = False

            if is_match and category_name and p.get("商品类别") != category_name:
                is_match = False

            if is_match and keyword:
                if not (keyword.lower() in p["商品名称"].lower() or (p.get("商品描述") and keyword.lower() in p["商品描述"].lower())):
                    is_match = False
            
            if is_match and min_price is not None and p["价格"] < min_price:
                is_match = False
            if is_match and max_price is not None and p["价格"] > max_price:
                is_match = False

            if is_match:
                filtered_products.append(p)
        
        # Update total count for filtered results
        total_count = len(filtered_products)
        for p in filtered_products:
             p["总商品数"] = total_count
             
        # For this test, we are only testing filter logic, not pagination/sorting
        # So return all filtered products
        return filtered_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Category and Price Range
    response1 = client.get("/api/v1/products", params={
        "category_name": "Electronics",
        "min_price": 50.00,
        "max_price": 100.00,
    })

    assert response1.status_code == status.HTTP_200_OK
    products1 = response1.json()
    assert len(products1) == 1
    assert products1[0]["商品名称"] == "Wireless Keyboard"
    assert products1[0]["总商品数"] == 1

    # Test case 2: Keyword and Status (Active)
    response2 = client.get("/api/v1/products", params={
        "keyword": "Wireless",
        "status": "Active", # Explicitly Active
    })

    assert response2.status_code == status.HTTP_200_OK
    products2 = response2.json()
    assert len(products2) == 2
    product_names2 = [p["商品名称"] for p in products2]
    assert "Wireless Keyboard" in product_names2
    assert "Ergonomic Mouse" in product_names2
    assert products2[0]["总商品数"] == 2 # Check total count

    # Test case 3: Category, Price Range, and Keyword
    response3 = client.get("/api/v1/products", params={
        "category_name": "Electronics",
        "min_price": 10.00,
        "max_price": 30.00,
        "keyword": "mouse",
    })

    assert response3.status_code == status.HTTP_200_OK
    products3 = response3.json()
    assert len(products3) == 1
    assert products3[0]["商品名称"] == "Ergonomic Mouse"
    assert products3[0]["总商品数"] == 1

    # Test case 4: No filters (should return all Active products)
    response4 = client.get("/api/v1/products")

    assert response4.status_code == status.HTTP_200_OK
    products4 = response4.json()
    # Expecting 4 active products
    assert len(products4) == 4
    product_names4 = [p["商品名称"] for p in products4]
    assert "Laptop Dell" in product_names4
    assert "Wireless Keyboard" in product_names4
    assert "Ergonomic Mouse" in product_names4
    assert "Fiction Novel" in product_names4
    assert "Adventure Book" not in product_names4 # Should not be included as status is PendingReview
    assert products4[0]["总商品数"] == 4

    # Test case 5: Combined filters resulting in no products
    response5 = client.get("/api/v1/products", params={
        "category_name": "Books",
        "min_price": 100.00,
    })

    assert response5.status_code == status.HTTP_200_OK
    products5 = response5.json()
    assert len(products5) == 0
    assert products5 == []
    # Note: Total count might be 0 or absent depending on how SP/Service handles empty results
    # Assuming an empty list is returned with maybe total_count = 0 if service includes it even for empty lists.
    # Based on previous tests, total_count seems to be present in items if any.
    # If no items, response should be [] and total_count might not be in the response or be 0.
    # The mock side effect will add total_count as 0 to items if list is empty, so checking the list is enough.

    # Assert that the mock service's get_product_list method was called with correct parameters for each test case
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword=None, min_price=50.00, max_price=100.00,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName='Electronics'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword='Wireless', min_price=None, max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword='mouse', min_price=10.00, max_price=30.00,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName='Electronics'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status=None, keyword=None, min_price=None, max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword=None, min_price=100.00, max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName='Books'
    )

@pytest.mark.asyncio
async def test_remove_favorite_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, mocking handles data.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    user_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = str(uuid4())

    # Configure the mock_product_service.remove_favorite to do nothing on success
    # (It will raise an exception on failure, which is tested in another case)
    mock_product_service.remove_favorite.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    # The add favorite part is not strictly necessary for testing remove, but we can mock it if the router endpoint calls it first
    # Assuming the endpoint directly calls remove_favorite
    response = client.delete(f"/api/v1/products/{product_id}/favorite")

    # Assert
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Assert that the mock service's remove_favorite method was called with correct parameters
    # Note: The user ID is obtained from the authenticated user dependency.
    mock_product_service.remove_favorite.assert_called_once_with(
        ANY, # Mocked connection
        user_id=user_id, # User ID from authentication mock
        product_id=product_id # Product ID from path parameter
    )

@pytest.mark.asyncio
async def test_remove_favorite_not_favorited(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, mocking handles data.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    user_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = str(uuid4())

    # Configure the mock_product_service.remove_favorite to raise a ValueError to simulate not favorited
    mock_product_service.remove_favorite.side_effect = ValueError("该商品不在您的收藏列表中。") # Simulate service raising ValueError

    # Act
    response = client.delete(f"/api/v1/products/{product_id}/favorite")

    # Assert
    # The router should catch the ValueError from the service and return a 400 HTTP exception
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "该商品不在您的收藏列表中。" in response.json()["detail"]

    # Assert that the mock service's remove_favorite method was called with correct parameters
    mock_product_service.remove_favorite.assert_called_once_with(
        ANY, # Mocked connection
        user_id=user_id, # User ID from authentication mock
        product_id=product_id # Product ID from path parameter
    )

@pytest.mark.asyncio
async def test_get_user_favorites(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create a user or product directly, mocking handles data.

    # Use the test_auth_user_id from the client fixture for simulating the current user
    user_id = client.test_auth_user_id

    # Define mock data that the service should return (list of favorite products)
    mock_favorite_products = [
        {
            "商品ID": str(uuid4()),
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
            "images": [{"ImageID": str(uuid4()), "ProductID": str(uuid4()), "ImageURL": "/uploads/fav1.jpg", "UploadTime": datetime.now().isoformat(), "SortOrder": 0}]
        },
        {
            "商品ID": str(uuid4()),
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
            "images": [{"ImageID": str(uuid4()), "ProductID": str(uuid4()), "ImageURL": "/uploads/fav2.jpg", "UploadTime": datetime.now().isoformat(), "SortOrder": 0}]
        }
    ]

    # Mock the service's get_user_favorites method to return the mock data
    mock_product_service.get_user_favorites.return_value = mock_favorite_products

    # Act
    response = client.get("/api/v1/favorites")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    # Compare the returned JSON with the mock data
    assert response.json() == mock_favorite_products

    # Assert that the mock service's get_user_favorites method was called with correct parameters
    # Note: The user ID is obtained from the authenticated user dependency.
    mock_product_service.get_user_favorites.assert_called_once_with(
        ANY, # Mocked connection
        user_id=user_id # User ID from authentication mock
    )

@pytest.mark.asyncio
async def test_admin_activate_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    admin_id = client.test_admin_user_id
    # Define a fake product ID for the test
    product_id = str(uuid4())

    # Configure the mock_product_service.activate_product to do nothing on success
    mock_product_service.activate_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.put(f"/api/v1/products/{product_id}/activate")

    # Assert
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Assert that the mock service's activate_product method was called with correct parameters
    mock_product_service.activate_product.assert_called_once_with(
        ANY, # Mocked connection
        product_id=product_id, # Product ID from path parameter
        admin_id=admin_id # Admin ID from authentication mock
    )

@pytest.mark.asyncio
async def test_admin_activate_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use a different user ID to simulate a non-admin attempting the activation
    non_admin_user_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = str(uuid4())

    # Configure the mock_product_service.activate_product to raise a PermissionError
    mock_product_service.activate_product.side_effect = PermissionError("You are not an admin.")

    # Act
    response = client.put(f"/api/v1/products/{product_id}/activate") # This request will be made by the non_admin_user simulated by the mock

    # Assert
    # The router should catch the PermissionError from the service and return a 403 Forbidden HTTP exception
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "You are not an admin." in response.json()["detail"]

    # Assert that the mock service's activate_product method was called with correct parameters
    # Note: The user ID is obtained from the authenticated user dependency.
    mock_product_service.activate_product.assert_called_once_with(
        ANY, # Mocked connection
        product_id=product_id, # Product ID from path parameter
        admin_id=non_admin_user_id # User ID from authentication mock
    )

@pytest.mark.asyncio
async def test_admin_reject_product_success(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    admin_id = client.test_admin_user_id
    # Define a fake product ID for the test
    product_id = str(uuid4())
    # Define a reason for rejection
    reason = "Rejected for testing purposes."

    # Configure the mock_product_service.reject_product to do nothing on success
    mock_product_service.reject_product.return_value = None # Assuming service returns None or doesn't return explicitly on success

    # Act
    response = client.put(f"/api/v1/products/{product_id}/reject", json={"reason": reason})

    # Assert
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Assert that the mock service's reject_product method was called with correct parameters
    mock_product_service.reject_product.assert_called_once_with(
        ANY, # Mocked connection
        product_id=product_id, # Product ID from path parameter
        admin_id=admin_id, # Admin ID from authentication mock
        reason=reason # Reason from request body
    )

@pytest.mark.asyncio
async def test_admin_reject_product_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use a different user ID to simulate a non-admin attempting the rejection
    non_admin_user_id = client.test_auth_user_id
    # Define a fake product ID for the test
    product_id = str(uuid4())
    # Define a reason for rejection
    reason = "Attempted rejection without admin permission."

    # Configure the mock_product_service.reject_product to raise a PermissionError
    mock_product_service.reject_product.side_effect = PermissionError("You are not an admin.")

    # Act
    response = client.put(f"/api/v1/products/{product_id}/reject", json={"reason": reason}) # This request will be made by the non_admin_user simulated by the mock

    # Assert
    # The router should catch the PermissionError from the service and return a 403 Forbidden HTTP exception
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "You are not an admin." in response.json()["detail"]

    # Assert that the mock service's reject_product method was called with correct parameters
    # Note: The user ID is obtained from the authenticated user dependency.
    mock_product_service.reject_product.assert_called_once_with(
        ANY, # Mocked connection
        product_id=product_id, # Product ID from path parameter
        admin_id=non_admin_user_id, # User ID from authentication mock
        reason=reason # Reason from request body
    )

@pytest.mark.asyncio
async def test_admin_batch_activate_products(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use the test_admin_user_id from the client fixture for simulating the current admin
    admin_id = client.test_admin_user_id
    # Define fake product IDs for the test
    product_ids = [str(uuid4()), str(uuid4()), str(uuid4())]

    # Configure the mock_product_service.batch_activate_products to return a success count
    success_count = len(product_ids)
    mock_product_service.batch_activate_products.return_value = success_count

    # Act
    response = client.post("/api/v1/products/batch-review", json={
        "product_ids": product_ids,
        "new_status": "Active",
        "reason": None # Reason is optional for activation
    })

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["successCount"] == success_count

    # Assert that the mock service's batch_activate_products method was called with correct parameters
    mock_product_service.batch_activate_products.assert_called_once_with(
        ANY, # Mocked connection
        product_ids=product_ids, # Product IDs from request body
        admin_id=admin_id # Admin ID from authentication mock
        # Note: batch_activate_products service method doesn't take reason, so it shouldn't be asserted here
    )

@pytest.mark.asyncio
async def test_admin_batch_review_permission_denied(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, mocking handles data and authentication.

    # Use a different user ID to simulate a non-admin attempting the batch review
    non_admin_user_id = client.test_auth_user_id
    # Define fake product IDs for the test
    product_ids = [str(uuid4()), str(uuid4()), str(uuid4())]
    # Define status and reason for the batch review
    new_status = "Active" # Or "Rejected"
    reason = "Batch review attempt without admin permission."

    # Configure the mock_product_service.batch_activate_products or batch_reject_products to raise a PermissionError
    # Mocking based on the requested new_status
    if new_status == "Active":
        mock_product_service.batch_activate_products.side_effect = PermissionError("You are not an admin.")
    elif new_status == "Rejected":
         mock_product_service.batch_reject_products.side_effect = PermissionError("You are not an admin.")

    # Act
    # Simulate the API request for batch review
    response = client.post("/api/v1/products/batch-review", json={
        "product_ids": product_ids,
        "new_status": new_status,
        "reason": reason
    }) # This request will be made by the non_admin_user simulated by the mock

    # Assert
    # The router should catch the PermissionError from the service and return a 403 Forbidden HTTP exception
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "You are not an admin." in response.json()["detail"]

    # Assert that the appropriate mock service method was called with correct parameters
    # Note: The user ID is obtained from the authenticated user dependency.
    if new_status == "Active":
         mock_product_service.batch_activate_products.assert_called_once_with(
             ANY, # Mocked connection
             product_ids=product_ids,
             admin_id=non_admin_user_id # User ID from authentication mock
         )
    elif new_status == "Rejected":
         mock_product_service.batch_reject_products.assert_called_once_with(
             ANY, # Mocked connection
             product_ids=product_ids,
             admin_id=non_admin_user_id, # User ID from authentication mock
             reason=reason
         )

@pytest.mark.asyncio
async def test_get_product_list_filter_pagination_sorting_combinations(client: TestClient, mock_product_service: AsyncMock):
    # Arrange
    # No need to create users or products directly, data is mocked.

    # Define comprehensive mock product data for various filter, pagination, and sorting scenarios
    mock_products_all = [
        {
            "商品ID": str(uuid4()), "商品名称": "Apple iPhone 13", "商品描述": "Latest iPhone", "库存": 5, "价格": 6999.00, "发布时间": (datetime.now() - timedelta(days=10)).isoformat(), "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/iphone.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Samsung Galaxy S21", "商品描述": "Android flagship", "库存": 8, "价格": 5999.00, "发布时间": (datetime.now() - timedelta(days=8)).isoformat(), "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/galaxy.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Sony WH-1000XM4", "商品描述": "Noise cancelling headphones", "库存": 12, "价格": 1999.00, "发布时间": (datetime.now() - timedelta(days=15)).isoformat(), "商品状态": "Active", "发布者用户名": "seller2", "商品类别": "Electronics", "主图URL": "/uploads/sony.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "MacBook Air M1", "商品描述": "Thin and light laptop", "库存": 3, "价格": 7999.00, "发布时间": (datetime.now() - timedelta(days=20)).isoformat(), "商品状态": "Active", "发布者用户名": "seller2", "商品类别": "Electronics", "主图URL": "/uploads/macbook.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Kindle Paperwhite", "商品描述": "E-reader", "库存": 20, "价格": 999.00, "发布时间": (datetime.now() - timedelta(days=5)).isoformat(), "商品状态": "Active", "发布者用户名": "seller3", "商品类别": "Books", "主图URL": "/uploads/kindle.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "The Great Gatsby", "商品描述": "Classic novel", "库存": 50, "价格": 50.00, "发布时间": (datetime.now() - timedelta(days=2)).isoformat(), "商品状态": "Active", "发布者用户名": "seller3", "商品类别": "Books", "主图URL": "/uploads/gatsby.jpg", "images": [], "总商品数": 0
        },
        {
            "商品ID": str(uuid4()), "商品名称": "Logitech MX Master 3", "商品描述": "Advanced wireless mouse", "库存": 18, "价格": 699.00, "发布时间": (datetime.now() - timedelta(days=7)).isoformat(), "商品状态": "Active", "发布者用户名": "seller1", "商品类别": "Electronics", "主图URL": "/uploads/mxmaster.jpg", "images": [], "总商品数": 0
        },
         {
            "商品ID": str(uuid4()), "商品名称": "Pending Product 1", "商品描述": "This is pending review", "库存": 1, "价格": 100.00, "发布时间": datetime.now().isoformat(), "商品状态": "PendingReview", "发布者用户名": "seller4", "商品类别": "Other", "主图URL": "/uploads/pending.jpg", "images": [], "总商品数": 0
        },
         {
            "商品ID": str(uuid4()), "商品名称": "Sold Product 1", "商品描述": "This is sold", "库存": 0, "价格": 200.00, "发布时间": (datetime.now() - timedelta(days=1)).isoformat(), "商品状态": "Sold", "发布者用户名": "seller4", "商品类别": "Other", "主图URL": "/uploads/sold.jpg", "images": [], "总商品数": 0
        },
    ]

    # Configure the mock_product_service.get_product_list side effect
    async def mock_get_product_list_side_effect(conn, **kwargs):
        category_name = kwargs.get("categoryName", None)
        status_filter = kwargs.get("status", "Active")
        keyword = kwargs.get("searchQuery", None)
        min_price = kwargs.get("minPrice", None)
        max_price = kwargs.get("maxPrice", None)
        page_number = kwargs.get("page_number", 1)
        page_size = kwargs.get("page_size", 10)
        order_by = kwargs.get("orderBy", "PostTime") # Note: Service uses orderBy, SP uses sortBy
        sort_order = kwargs.get("sortOrder", "DESC")

        # Apply filters
        filtered_products = []
        for p in mock_products_all:
            is_match = True

            if status_filter and p["商品状态"] != status_filter:
                is_match = False

            if is_match and category_name and p.get("商品类别") != category_name:
                is_match = False

            if is_match and keyword:
                if not (keyword.lower() in p["商品名称"].lower() or (p.get("商品描述") and keyword.lower() in p["商品描述"].lower())):
                    is_match = False
            
            if is_match and min_price is not None and p["价格"] < min_price:
                is_match = False
            if is_match and max_price is not None and p["价格"] > max_price:
                is_match = False

            if is_match:
                filtered_products.append(p)
        
        # Apply sorting
        def get_sort_key(product):
            if order_by == "Price":
                return product["价格"]
            elif order_by == "ProductName":
                return product["商品名称"]
            elif order_by == "PostTime":
                # Convert ISO format string to datetime for proper comparison
                return datetime.fromisoformat(product["发布时间"])
            return datetime.fromisoformat(product["发布时间"]) # Default sort key

        reverse_sort = sort_order.upper() == "DESC"
        sorted_products = sorted(filtered_products, key=get_sort_key, reverse=reverse_sort)

        # Apply pagination
        start_index = (page_number - 1) * page_size
        end_index = start_index + page_size
        paginated_products = sorted_products[start_index:end_index]

        # Update total count in the paginated results
        total_count = len(filtered_products)
        for p in paginated_products:
             p["总商品数"] = total_count

        return paginated_products

    mock_product_service.get_product_list.side_effect = mock_get_product_list_side_effect

    # Test case 1: Filter by Category and Price Range, Paginate and Sort by Price ASC
    response1 = client.get("/api/v1/products", params={
        "category_name": "Electronics",
        "min_price": 1000.00,
        "max_price": 7000.00,
        "page_number": 1,
        "page_size": 2,
        "order_by": "Price",
        "sortOrder": "ASC"
    })

    assert response1.status_code == status.HTTP_200_OK
    products1 = response1.json()
    assert len(products1) == 2
    assert products1[0]["商品名称"] == "Sony WH-1000XM4" # Price 1999
    assert products1[1]["商品名称"] == "Samsung Galaxy S21" # Price 5999
    assert products1[0]["总商品数"] == 4 # Total active electronics between 1000 and 7000 (Sony, Samsung, iPhone, Logitech)

    # Test case 2: Filter by Keyword and Status (Active), Paginate and Sort by PostTime DESC
    response2 = client.get("/api/v1/products", params={
        "keyword": "wireless",
        "status": "Active",
        "page_number": 1,
        "page_size": 1,
        "order_by": "PostTime",
        "sortOrder": "DESC"
    })

    assert response2.status_code == status.HTTP_200_OK
    products2 = response2.json()
    assert len(products2) == 1
    # The newest 'wireless' product is Logitech MX Master 3
    assert products2[0]["商品名称"] == "Logitech MX Master 3"
    assert products2[0]["总商品数"] == 2 # Total active wireless products (Logitech, Samsung Galaxy S21 description)

    # Test case 3: Filter by Category and Keyword, Paginate and Sort by ProductName ASC
    response3 = client.get("/api/v1/products", params={
        "category_name": "Books",
        "keyword": "novel",
        "page_number": 1,
        "page_size": 10,
        "order_by": "ProductName",
        "sortOrder": "ASC"
    })

    assert response3.status_code == status.HTTP_200_OK
    products3 = response3.json()
    assert len(products3) == 2
    # Sorted by Product Name ASC: The Great Gatsby, Fiction Novel
    assert products3[0]["商品名称"] == "Fiction Novel"
    assert products3[1]["商品名称"] == "The Great Gatsby"
    assert products3[0]["总商品数"] == 2 # Total active book novels

    # Test case 4: Filter by Status (PendingReview), no other filters, Pagination default, Sorting default
    response4 = client.get("/api/v1/products", params={
        "status": "PendingReview",
    })

    assert response4.status_code == status.HTTP_200_OK
    products4 = response4.json()
    assert len(products4) == 1
    assert products4[0]["商品名称"] == "Pending Product 1"
    assert products4[0]["总商品数"] == 1

    # Assert that the mock service's get_product_list method was called with correct parameters for each test case
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword=None, min_price=1000.00, max_price=7000.00,
        order_by='Price', page_number=1, page_size=2, sortOrder='ASC',
        categoryName='Electronics'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword='wireless', min_price=None, max_price=None,
        order_by='PostTime', page_number=1, page_size=1, sortOrder='DESC',
        categoryName=None
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='Active', keyword='novel', min_price=None, max_price=None,
        order_by='ProductName', page_number=1, page_size=10, sortOrder='ASC',
        categoryName='Books'
    )
    mock_product_service.get_product_list.assert_any_call(
        ANY, # Mocked connection
        category_id=None, status='PendingReview', keyword=None, min_price=None, max_price=None,
        order_by='PostTime', page_number=1, page_size=10, sortOrder='DESC',
        categoryName=None
    )