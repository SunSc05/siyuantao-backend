import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, timezone

from app.schemas.order_schemas import OrderCreateSchema, OrderResponseSchema, OrderStatusUpdateSchema
from app.dependencies import get_current_user
from app.services.order_service import OrderService
from app.exceptions import IntegrityError, ForbiddenError, NotFoundError, DALError
from fastapi import HTTPException, status
import pytest_mock
import pyodbc

# 假设这是你为 order_service 准备的 mock fixture 定义 (通常放在 conftest.py)
# 为了测试方便，这里直接定义，实际项目中应放在 conftest.py
@pytest.fixture
def mock_order_service(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    """Mock the OrderService dependency."""
    mock_service = AsyncMock(spec=OrderService)
    return mock_service

# --- POST /orders/ - 创建订单 ---

def test_create_order_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功创建一个订单。
    'client' fixture 会自动处理认证，模拟一个普通用户已登录。
    'mock_order_service' fixture 提供了 Service 层的 Mock。
    """
    order_data = OrderCreateSchema(product_id=uuid4(), quantity=1, shipping_address="123 Main St", contact_phone="555-1234", total_price=100.0)
    # mock_buyer_id is implicitly handled by the client fixture's get_current_user override

    expected_created_order_schema = OrderResponseSchema(
        order_id=uuid4(),
        buyer_id=client.test_user_id,
        product_id=order_data.product_id,
        quantity=order_data.quantity,
        shipping_address=order_data.shipping_address,
        contact_phone=order_data.contact_phone,
        total_price=order_data.total_price,
        status="Pending",
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
        updated_at=datetime.now(timezone.utc).replace(microsecond=0),
        seller_id=uuid4(),
        trade_id=None,
        complete_time=None,
        cancel_time=None,
        cancel_reason=None
    )
    mock_order_service.create_order.return_value = expected_created_order_schema

    response = client.post("/api/v1/orders/", json=order_data.model_dump(mode='json'))

    assert response.status_code == 201
    response_data = response.json()
    expected_json_data = expected_created_order_schema.model_dump(mode='json', by_alias=True)
    assert response_data == expected_json_data

    mock_order_service.create_order.assert_called_once_with(
        mocker.ANY,
        order_data,
        client.test_user_id
    )

def test_create_order_value_error(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试Service层抛出ValueError时，Router是否正确处理。
    """
    order_data = OrderCreateSchema(product_id=uuid4(), quantity=0, shipping_address="123 Main St", contact_phone="555-1234", total_price=100.0) # 无效数量，但 total_price 有效
    mock_order_service.create_order.side_effect = ValueError("订单数量必须大于0")

    response = client.post("/api/v1/orders/", json=order_data.model_dump(mode='json'))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json().get('detail') == "订单数量必须大于0"
    mock_order_service.create_order.assert_called_once()

# --- GET /orders/{order_id} - 获取单个订单 ---

def test_get_order_by_id_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功获取单个订单。
    """
    order_id = uuid4()
    expected_order = OrderResponseSchema(
        order_id=order_id,
        buyer_id=client.test_user_id,
        product_id=uuid4(),
        quantity=1,
        total_price=100.0,
        status="Pending",
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
        updated_at=datetime.now(timezone.utc).replace(microsecond=0),
        seller_id=uuid4(),
        trade_id=None,
        shipping_address="456 Oak Ave, Otherville, USA",
        contact_phone="555-5678",
        complete_time=None,
        cancel_time=None,
        cancel_reason=None
    )
    mock_order_service.get_order_by_id.return_value = expected_order

    response = client.get(f"/api/v1/orders/{order_id}")

    assert response.status_code == 200
    assert response.json() == expected_order.model_dump(mode='json', by_alias=True)
    mock_order_service.get_order_by_id.assert_called_once_with(mocker.ANY, order_id)

def test_get_order_by_id_not_found(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试获取不存在的订单。
    """
    order_id = uuid4()
    mock_order_service.get_order_by_id.side_effect = NotFoundError("订单未找到")

    response = client.get(f"/api/v1/orders/{order_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json().get('detail') == "订单未找到"
    mock_order_service.get_order_by_id.assert_called_once()

# --- DELETE /orders/{order_id} - 删除订单 ---

def test_delete_order_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功删除订单。
    """

    order_id = uuid4()
    mock_order_service.delete_order.return_value = None # delete_order 不返回任何值

    response = client.delete(f"/api/v1/orders/{order_id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_order_service.delete_order.assert_called_once_with(
        mocker.ANY,
        order_id=order_id,
        user_id=client.test_user_id
    )

def test_delete_order_forbidden(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试用户无权删除的订单。
    """
    order_id = uuid4()
    mock_order_service.delete_order.side_effect = ForbiddenError("您无权删除此订单")

    response = client.delete(f"/api/v1/orders/{order_id}")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json().get('detail') == "您无权删除此订单"
    mock_order_service.delete_order.assert_called_once()

# --- POST /orders/{order_id}/cancel - 取消订单 ---

def test_cancel_order_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功取消订单。
    """
    order_id = uuid4()
    cancel_reason = "买家取消"
    mock_order_service.cancel_order.return_value = None # cancel_order 不返回任何值

    response = client.post(f"/api/v1/orders/{order_id}/cancel", json={"cancel_reason": cancel_reason})

    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_order_service.cancel_order.assert_called_once_with(
        mocker.ANY,
        order_id=order_id,
        user_id=client.test_user_id,
        cancel_reason=cancel_reason
    )

# --- PUT /orders/{order_id}/confirm - 确认订单 ---

def test_confirm_order_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功确认订单。
    """
    order_id = uuid4()
    mock_order_service.confirm_order.return_value = True

    response = client.put(f"/api/v1/orders/{order_id}/confirm")

    assert response.status_code == 200
    assert response.json() == {"message": "订单已成功确认"}
    mock_order_service.confirm_order.assert_called_once_with(mocker.ANY, order_id, client.test_user_id)

# --- PUT /orders/{order_id}/complete - 完成订单 ---

def test_complete_order_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功完成订单。
    """
    order_id = uuid4()
    mock_order_service.complete_order.return_value = True

    response = client.put(f"/api/v1/orders/{order_id}/complete")

    assert response.status_code == 200
    assert response.json() == {"message": "订单已成功完成"}
    mock_order_service.complete_order.assert_called_once_with(mocker.ANY, order_id, client.test_user_id)

# --- PUT /orders/{order_id}/reject - 拒绝订单 ---

def test_reject_order_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功拒绝订单。
    """
    order_id = uuid4()
    mock_order_service.reject_order.return_value = True

    response = client.put(f"/api/v1/orders/{order_id}/reject")

    assert response.status_code == 200
    assert response.json() == {"message": "订单已成功拒绝"}
    mock_order_service.reject_order.assert_called_once_with(mocker.ANY, order_id, client.test_user_id)

# --- PUT /orders/{order_id}/status - 更新订单状态 ---

def test_update_order_status_success(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功更新订单状态。
    """
    order_id = uuid4()
    status_update_data = OrderStatusUpdateSchema(status="Completed")
    mock_user_id = client.test_user_id

    expected_updated_order_schema = OrderResponseSchema(
        order_id=order_id,
        buyer_id=mock_user_id,
        product_id=uuid4(),
        quantity=1,
        shipping_address="123 Main St",
        contact_phone="555-1234",
        total_price=100.0,
        status="Completed",
        created_at=datetime.now(timezone.utc).replace(microsecond=0),
        updated_at=datetime.now(timezone.utc).replace(microsecond=0),
        seller_id=uuid4(),
        trade_id=None,
        complete_time=datetime.now(timezone.utc).replace(microsecond=0),
        cancel_time=None,
        cancel_reason=None
    )
    mock_order_service.update_order_status.return_value = expected_updated_order_schema

    response = client.put(f"/api/v1/orders/{order_id}/status", json=status_update_data.model_dump(mode='json'))

    assert response.status_code == 200
    response_data = response.json()
    expected_json_data = expected_updated_order_schema.model_dump(mode='json', by_alias=True)
    assert response_data == expected_json_data

    mock_order_service.update_order_status.assert_called_once_with(
        mocker.ANY,
        order_id=order_id,
        new_status=status_update_data.status,
        user_id=client.test_user_id
    )

def test_update_order_status_value_error(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试无效的状态转换。
    """
    order_id = uuid4()
    status_update_data = OrderStatusUpdateSchema(status="InvalidStatus")
    mock_order_service.update_order_status.side_effect = ValueError("无效的订单状态转换")

    response = client.put(f"/api/v1/orders/{order_id}/status", json=status_update_data.model_dump(mode='json'))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json().get('detail') == "无效的订单状态转换"
    mock_order_service.update_order_status.assert_called_once()

# --- GET /orders/mine - 获取当前用户订单 ---

def test_get_my_orders_success_with_orders(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功获取当前用户订单列表 (有订单)。
    """
    mock_user_id = client.test_user_id
    orders_list = [
        OrderResponseSchema(
            order_id=uuid4(),
            buyer_id=client.test_user_id,
            product_id=uuid4(),
            quantity=1,
            shipping_address="Addr1",
            contact_phone="Phone1",
            total_price=100.0,
            status="Pending",
            created_at=datetime.now(timezone.utc).replace(microsecond=0),
            updated_at=datetime.now(timezone.utc).replace(microsecond=0),
            seller_id=uuid4(),
            trade_id=None,
            complete_time=None,
            cancel_time=None,
            cancel_reason=None
        ),
        OrderResponseSchema(
            order_id=uuid4(),
            buyer_id=client.test_user_id,
            product_id=uuid4(),
            quantity=2,
            shipping_address="Addr2",
            contact_phone="Phone2",
            total_price=200.0,
            status="Completed",
            created_at=datetime.now(timezone.utc).replace(microsecond=0),
            updated_at=datetime.now(timezone.utc).replace(microsecond=0),
            seller_id=uuid4(),
            trade_id=uuid4(),
            complete_time=datetime.now(timezone.utc).replace(microsecond=0),
            cancel_time=None,
            cancel_reason=None
        ),
    ]
    mock_order_service.get_orders_by_user.return_value = orders_list

    response = client.get("/api/v1/orders/mine")

    assert response.status_code == 200
    response_data = response.json()
    # Convert the list of schemas to a list of dictionaries for comparison
    expected_json_data = [order.model_dump(mode='json', by_alias=True) for order in orders_list]
    assert response_data == expected_json_data

    mock_order_service.get_orders_by_user.assert_called_once_with(
        mocker.ANY,
        client.test_user_id,
        is_seller=False,
        status=None,
        page_number=1,
        page_size=10
    )

def test_get_my_orders_success_no_orders(client: TestClient, mock_order_service: AsyncMock, mocker: pytest_mock.MockerFixture):
    """
    测试成功获取当前用户订单列表 (无订单)。
    """
    mock_order_service.get_orders_by_user.return_value = []

    response = client.get("/api/v1/orders/mine")

    assert response.status_code == 200
    assert response.json() == []
    mock_order_service.get_orders_by_user.assert_called_once_with(
        mocker.ANY,
        client.test_user_id,
        is_seller=False,
        status=None,
        page_number=1,
        page_size=10
    )