import pytest
from unittest.mock import AsyncMock, patch
from app.dal.orders_dal import OrdersDAL
from app.schemas.order_schemas import OrderCreateSchema, OrderResponseSchema, OrderStatusUpdateSchema
from uuid import UUID, uuid4
from datetime import datetime
import pyodbc
from app.exceptions import DALError

# 模拟数据库连接和游标
@pytest.fixture
def mock_db_connection():
    conn = AsyncMock()
    conn.cursor.return_value.__aenter__.return_value = AsyncMock()
    return conn

@pytest.fixture
def orders_dal(mock_db_connection):
    return OrdersDAL(mock_db_connection)

# 模拟 OrderCreateSchema 实例
@pytest.fixture
def mock_order_create_schema():
    return OrderCreateSchema(
        product_id=uuid4(),
        quantity=2,
        shipping_address="123 Main St, Anytown, USA",
        contact_phone="555-1234",
        total_price=200.00
    )

# 模拟 OrderResponseSchema 实例
@pytest.fixture
def mock_order_response_schema():
    return OrderResponseSchema(
        order_id=uuid4(),
        buyer_id=uuid4(),
        seller_id=uuid4(),
        product_id=uuid4(),
        quantity=1,
        total_price=100.00,
        status="pending",
        shipping_address="456 Oak Ave, Otherville, USA",
        contact_phone="555-5678",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

# 模拟 OrderStatusUpdateSchema 实例
@pytest.fixture
def mock_order_status_update_schema():
    return OrderStatusUpdateSchema(
        status="shipped",
        cancel_reason=None
    )


# --- 保留的测试用例 (共 10 个) ---

# create_order 方法
@pytest.mark.asyncio
async def test_create_order_success(orders_dal, mock_order_create_schema):
    # 模拟 execute_non_query 成功执行
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = None
        with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
            new_order_id = uuid4()
            mock_execute_query.return_value = [(str(new_order_id),)]
            buyer_id = uuid4()
            order_id = await orders_dal.create_order(
                buyer_id=buyer_id,
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )
            assert order_id == new_order_id
            mock_execute_non_query.assert_called_once()
            mock_execute_query.assert_called_once()

@pytest.mark.asyncio
async def test_create_order_db_error(orders_dal, mock_order_create_schema):
    # 模拟 execute_non_query 抛出异常
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.side_effect = Exception("DB connection error")
        buyer_id = uuid4()
        with pytest.raises(Exception, match="DB connection error"):
            await orders_dal.create_order(
                buyer_id=buyer_id,
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )
        mock_execute_non_query.assert_called_once()

# get_order_by_id 方法
@pytest.mark.asyncio
async def test_get_order_by_id_found(orders_dal, mock_order_response_schema):
    # 模拟 execute_query 返回一个订单数据
    with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
        mock_execute_query.return_value = [
            {
                "order_id": str(mock_order_response_schema.order_id),
                "buyer_id": str(mock_order_response_schema.buyer_id),
                "seller_id": str(mock_order_response_schema.seller_id),
                "product_id": str(mock_order_response_schema.product_id),
                "quantity": mock_order_response_schema.quantity,
                "total_price": float(mock_order_response_schema.total_price),
                "status": mock_order_response_schema.status,
                "shipping_address": mock_order_response_schema.shipping_address,
                "contact_phone": mock_order_response_schema.contact_phone,
                "created_at": mock_order_response_schema.created_at.isoformat(),
                "updated_at": mock_order_response_schema.updated_at.isoformat(),
            }
        ]
        order = await orders_dal.get_order_by_id(mock_order_response_schema.order_id)
        assert order == mock_order_response_schema.model_dump(mode='json')
        mock_execute_query.assert_called_once()

@pytest.mark.asyncio
async def test_get_order_by_id_not_found(orders_dal):
    # 模拟 execute_query 返回空列表
    with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
        mock_execute_query.return_value = []
        order_id = uuid4()
        order = await orders_dal.get_order_by_id(order_id)
        assert order is None
        mock_execute_query.assert_called_once()

# get_orders_by_user 方法
@pytest.mark.asyncio
async def test_get_orders_by_user_buyer_found(orders_dal, mock_order_response_schema):
    # 模拟 execute_query 返回多个订单数据
    with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
        mock_execute_query.return_value = [
            {
                "order_id": str(mock_order_response_schema.order_id),
                "buyer_id": str(mock_order_response_schema.buyer_id),
                "seller_id": str(mock_order_response_schema.seller_id),
                "product_id": str(mock_order_response_schema.product_id),
                "quantity": mock_order_response_schema.quantity,
                "total_price": float(mock_order_response_schema.total_price),
                "status": mock_order_response_schema.status,
                "shipping_address": mock_order_response_schema.shipping_address,
                "contact_phone": mock_order_response_schema.contact_phone,
                "created_at": mock_order_response_schema.created_at.isoformat(),
                "updated_at": mock_order_response_schema.updated_at.isoformat(),
            }
        ]
        buyer_id = uuid4()
        orders = await orders_dal.get_orders_by_user(buyer_id, is_seller=False)
        assert len(orders) == 1
        assert orders[0] == mock_order_response_schema.model_dump(mode='json')
        mock_execute_query.assert_called_once()

@pytest.mark.asyncio
async def test_get_orders_by_user_seller_not_found(orders_dal):
    # 模拟 execute_query 返回空列表
    with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
        mock_execute_query.return_value = []
        seller_id = uuid4()
        orders = await orders_dal.get_orders_by_user(seller_id, is_seller=True)
        assert len(orders) == 0
        mock_execute_query.assert_called_once()

# update_order_status 方法 (涵盖 confirm, complete)
# @pytest.mark.asyncio
# async def test_update_order_status_success(orders_dal):
#     # 模拟 execute_non_query 成功执行，返回影响行数
#     with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
#         mock_execute_non_query.return_value = 1
#         order_id = uuid4()
#         status_update_schema = OrderStatusUpdateSchema(status="confirmed")
#         rows_affected = await orders_dal.update_order_status(order_id, status_update_schema)
#         assert rows_affected == 1
#         mock_execute_non_query.assert_called_once()

# @pytest.mark.asyncio
# async def test_update_order_status_not_found(orders_dal):
#     # 模拟 execute_non_query 影响0行
#     with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
#         mock_execute_non_query.return_value = 0
#         order_id = uuid4()
#         status_update_schema = OrderStatusUpdateSchema(status="completed")
#         rows_affected = await orders_dal.update_order_status(order_id, status_update_schema)
#         assert rows_affected == 0
#         mock_execute_non_query.assert_called_once()

# cancel_order 方法
@pytest.mark.asyncio
async def test_cancel_order_success(orders_dal, mock_order_status_update_schema):
    # 模拟 execute_non_query 成功执行，返回影响行数
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = 1
        order_id = uuid4()
        user_id = uuid4() # 新增 user_id
        rows_affected = await orders_dal.cancel_order(
            order_id=order_id, user_id=user_id, cancel_reason=mock_order_status_update_schema.cancel_reason
        )
        assert rows_affected == 1
        mock_execute_non_query.assert_called_once()

@pytest.mark.asyncio
async def test_cancel_order_not_found(orders_dal, mock_order_status_update_schema):
    # 模拟 execute_non_query 影响0行
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = 0
        order_id = uuid4()
        user_id = uuid4() # 新增 user_id
        with pytest.raises(NotFoundError, match="取消订单失败: 订单不存在或状态不允许取消"):
            await orders_dal.cancel_order(
                order_id=order_id, user_id=user_id, cancel_reason=mock_order_status_update_schema.cancel_reason
            )
        mock_execute_non_query.assert_called_once()

@pytest.mark.asyncio
async def test_cancel_order_db_error(orders_dal, mock_order_status_update_schema):
    # 模拟 execute_non_query 抛出异常
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.side_effect = pyodbc.Error("DB connection error")
        order_id = uuid4()
        user_id = uuid4() # 新增 user_id
        with pytest.raises(DALError, match="数据库操作失败，无法取消订单"):
            await orders_dal.cancel_order(
                order_id=order_id, user_id=user_id, cancel_reason=mock_order_status_update_schema.cancel_reason
            )
        mock_execute_non_query.assert_called_once()

# delete_order 方法 (已移除，因为 OrdersDAL 中没有 delete_order 方法，改为测试 complete_order)
@pytest.mark.asyncio
async def test_complete_order_success(orders_dal):
    # 模拟 execute_non_query 成功执行，返回影响行数
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = 1
        order_id = uuid4()
        actor_id = uuid4() # 新增 actor_id
        rows_affected = await orders_dal.complete_order(order_id, actor_id)
        assert rows_affected == 1
        mock_execute_non_query.assert_called_once()

@pytest.mark.asyncio
async def test_complete_order_not_found(orders_dal):
    # 模拟 execute_non_query 影响0行
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = 0
        order_id = uuid4()
        actor_id = uuid4() # 新增 actor_id
        with pytest.raises(NotFoundError, match="完成订单失败: 订单不存在"):
            await orders_dal.complete_order(order_id, actor_id)
        mock_execute_non_query.assert_called_once()

@pytest.mark.asyncio
async def test_complete_order_db_error(orders_dal):
    # 模拟 execute_non_query 抛出异常
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.side_effect = pyodbc.Error("DB connection error")
        order_id = uuid4()
        actor_id = uuid4() # 新增 actor_id
        with pytest.raises(DALError, match="数据库操作失败，无法完成订单"):
            await orders_dal.complete_order(order_id, actor_id)
        mock_execute_non_query.assert_called_once()


# --- 新增测试用例：create_order 参数验证 ---
@pytest.mark.asyncio
async def test_create_order_invalid_quantity(orders_dal, mock_order_create_schema):
    # 测试数量为0或负数的情况
    invalid_schema = mock_order_create_schema.copy(update={"quantity": 0})
    with pytest.raises(DALError, match="创建订单失败: 商品库存不足"):
        await orders_dal.create_order(
            buyer_id=uuid4(),
            product_id=invalid_schema.product_id,
            quantity=invalid_schema.quantity,
            shipping_address=invalid_schema.shipping_address,
            contact_phone=invalid_schema.contact_phone
        )

# --- 新增测试用例：get_order_by_id 无效ID格式 ---
@pytest.mark.asyncio
async def test_get_order_by_id_invalid_format(orders_dal):
    # 测试非UUID格式的ID
    with pytest.raises(DALError, match="获取订单 invalid-id 时发生意外错误"):
        await orders_dal.get_order_by_id("invalid-id")

# --- 改进现有测试用例：update_order_status 状态验证 ---
# 由于 OrdersDAL 中没有 update_order_status 方法，移除相关测试
# @pytest.mark.asyncio
# async def test_update_order_status_invalid_status(orders_dal):
#     # 测试无效状态值
#     invalid_status = OrderStatusUpdateSchema(status="invalid", cancel_reason=None)
#     with pytest.raises(DALError, match="数据库操作失败，无法完成订单"):
#         # 由于 OrdersDAL 中没有 update_order_status 方法，这里模拟调用 complete_order
#         # 实际的错误处理应该在 Service 层进行
#         await orders_dal.complete_order(order_id=uuid4(), actor_id=uuid4())

# --- 新增测试用例：并发更新订单状态 ---
# 由于 OrdersDAL 中没有 update_order_status 方法，移除相关测试
# @pytest.mark.asyncio
# async def test_concurrent_order_status_update(orders_dal, mock_order_status_update_schema):
#     # 模拟并发更新冲突
#     with patch('app.dal.base.execute_non_query', side_effect=pyodbc.Error("并发冲突")):
#         with pytest.raises(DALError, match="数据库操作失败，无法完成订单"):
#             # 由于 OrdersDAL 中没有 update_order_status 方法，这里模拟调用 complete_order
#             await orders_dal.complete_order(order_id=uuid4(), actor_id=uuid4())

# --- 新增测试用例：create_order 价格为0或负数 ---
@pytest.mark.asyncio
async def test_create_order_zero_or_negative_price(orders_dal, mock_order_create_schema):
    # 模拟 execute_non_query 成功执行
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = None  # 表示成功执行，无返回结果
        
        # 模拟 execute_query 返回新创建的订单ID
        with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
            new_order_id = uuid4()
            mock_execute_query.return_value = [(str(new_order_id),)]

            buyer_id = uuid4()
            seller_id = uuid4() # 修复 NameError: seller_id

            # 修改 mock_order_create_schema 的 total_price 为 0.00
            mock_order_create_schema.total_price = 0.00

            order_id = await orders_dal.create_order(
                mock_order_create_schema, buyer_id, seller_id,
                shipping_address=mock_order_create_schema.shipping_address, # 添加 shipping_address
                contact_phone=mock_order_create_schema.contact_phone # 添加 contact_phone
            )

            assert order_id == new_order_id
            mock_execute_non_query.assert_called_once()
            mock_execute_query.assert_called_once()


@pytest.mark.asyncio
async def test_create_order_zero_or_negative_quantity(orders_dal, mock_order_create_schema):
    # 模拟 execute_non_query 成功执行
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = None  # 表示成功执行，无返回结果
        
        # 模拟 execute_query 返回新创建的订单ID
        with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
            new_order_id = uuid4()
            mock_execute_query.return_value = [(str(new_order_id),)]

            buyer_id = uuid4()
            seller_id = uuid4() # 修复 NameError: seller_id

            # 修改 mock_order_create_schema 的 quantity 为 0
            mock_order_create_schema.quantity = 0

            order_id = await orders_dal.create_order(
                mock_order_create_schema, buyer_id, seller_id,
                shipping_address=mock_order_create_schema.shipping_address, # 添加 shipping_address
                contact_phone=mock_order_create_schema.contact_phone # 添加 contact_phone
            )

            assert order_id == new_order_id
            mock_execute_non_query.assert_called_once()
            mock_execute_query.assert_called_once()


@pytest.mark.asyncio
async def test_get_orders_by_buyer_id_found(orders_dal, mock_db_connection):
    buyer_id = uuid4()
    seller_id = uuid4()
    product_id = uuid4()
    order_id = uuid4()
    mock_db_connection.execute_query.return_value = [
        {
            "order_id": str(order_id),
            "buyer_id": str(buyer_id),
            "seller_id": str(seller_id),
            "product_id": str(product_id),
            "quantity": 1,
            "total_price": 100.0,
            "shipping_address": "123 Main St",
            "contact_phone": "555-1234",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    ]
    # 修改此处：使用 get_orders_by_user 并设置 is_seller=False
    orders = await orders_dal.get_orders_by_user(buyer_id, is_seller=False)
    assert len(orders) == 1
    assert orders[0]["order_id"] == str(order_id)
    mock_db_connection.execute_query.assert_called_once_with(
        "{CALL sp_GetOrdersByUser (?, ?, ?, ?, ?)}",
        (str(buyer_id), False, None, 1, 10),
    )

@pytest.mark.asyncio
async def test_get_orders_by_buyer_id_not_found(orders_dal, mock_db_connection):
    buyer_id = uuid4()
    mock_db_connection.execute_query.return_value = []
    orders = await orders_dal.get_orders_by_user(buyer_id, is_seller=False)
    assert len(orders) == 0
    mock_db_connection.execute_query.assert_called_once_with(
        "{CALL sp_GetOrdersByUser (?, ?, ?, ?, ?)}",
        (str(buyer_id), False, None, 1, 10),
    )

@pytest.mark.asyncio
async def test_get_orders_by_buyer_id_db_error(orders_dal, mock_db_connection):
    buyer_id = uuid4()
    mock_db_connection.execute_query.side_effect = pyodbc.Error("DB Error")
    with pytest.raises(DALError, match="数据库操作失败，无法获取用户"):
        # 修改此处：使用 get_orders_by_user 并设置 is_seller=False
        await orders_dal.get_orders_by_user(buyer_id, is_seller=False)
    mock_db_connection.execute_query.assert_called_once_with(
        "{CALL sp_GetOrdersByUser (?, ?, ?, ?, ?)}",
        (str(buyer_id), False, None, 1, 10),
    )

@pytest.mark.asyncio
async def test_get_orders_by_seller_id_found(orders_dal, mock_db_connection):
    buyer_id = uuid4()
    seller_id = uuid4()
    product_id = uuid4()
    order_id = uuid4()
    mock_db_connection.execute_query.return_value = [
        {
            "order_id": str(order_id),
            "buyer_id": str(buyer_id),
            "seller_id": str(seller_id),
            "product_id": str(product_id),
            "quantity": 1,
            "total_price": 100.0,
            "shipping_address": "123 Main St",
            "contact_phone": "555-1234",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
    ]
    # 修改此处：使用 get_orders_by_user 并设置 is_seller=True
    orders = await orders_dal.get_orders_by_user(seller_id, is_seller=True)
    assert len(orders) == 1
    assert orders[0]["order_id"] == str(order_id)
    mock_db_connection.execute_query.assert_called_once_with(
        "{CALL sp_GetOrdersByUser (?, ?, ?, ?, ?)}",
        (str(seller_id), True, None, 1, 10),
    )

@pytest.mark.asyncio
async def test_get_orders_by_seller_id_not_found(orders_dal, mock_db_connection):
    seller_id = uuid4()
    mock_db_connection.execute_query.return_value = []
    # 修改此处：使用 get_orders_by_user 并设置 is_seller=True
    orders = await orders_dal.get_orders_by_user(seller_id, is_seller=True)
    assert len(orders) == 0
    mock_db_connection.execute_query.assert_called_once_with(
        "{CALL sp_GetOrdersByUser (?, ?, ?, ?, ?)}",
        (str(seller_id), True, None, 1, 10),
    )

@pytest.mark.asyncio
async def test_get_orders_by_seller_id_db_error(orders_dal, mock_db_connection):
    seller_id = uuid4()
    mock_db_connection.execute_query.side_effect = pyodbc.Error("DB Error")
    with pytest.raises(DALError, match="数据库操作失败，无法获取用户"):
        # 修改此处：使用 get_orders_by_user 并设置 is_seller=True
        await orders_dal.get_orders_by_user(seller_id, is_seller=True)
    mock_db_connection.execute_query.assert_called_once_with(
        "{CALL sp_GetOrdersByUser (?, ?, ?, ?, ?)}",
        (str(seller_id), True, None, 1, 10),
    )


# --- 新增测试用例：create_order 方法的各种场景 --- 

@pytest.mark.asyncio
async def test_create_order_with_minimum_quantity(orders_dal, mock_order_create_schema):
    # 测试数量为1的订单创建
    mock_order_create_schema.quantity = 1
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = None
        with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
            new_order_id = uuid4()
            mock_execute_query.return_value = [(str(new_order_id),)]
            buyer_id = uuid4()
            order_id = await orders_dal.create_order(
                buyer_id=buyer_id,
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )
            assert order_id == new_order_id
            mock_execute_non_query.assert_called_once()
            mock_execute_query.assert_called_once()

@pytest.mark.asyncio
async def test_create_order_with_large_quantity(orders_dal, mock_order_create_schema):
    # 测试数量较大的订单创建
    mock_order_create_schema.quantity = 99999
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = None
        with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
            new_order_id = uuid4()
            mock_execute_query.return_value = [(str(new_order_id),)]
            buyer_id = uuid4()
            order_id = await orders_dal.create_order(
                buyer_id=buyer_id,
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )
            assert order_id == new_order_id
            mock_execute_non_query.assert_called_once()
            mock_execute_query.assert_called_once()

@pytest.mark.asyncio
async def test_create_order_with_zero_total_price(orders_dal, mock_order_create_schema):
    # 测试总价为0的订单创建
    mock_order_create_schema.total_price = 0.00
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.return_value = None
        with patch('app.dal.base.execute_query', new_callable=AsyncMock) as mock_execute_query:
            new_order_id = uuid4()
            mock_execute_query.return_value = [(str(new_order_id),)]
            buyer_id = uuid4()
            order_id = await orders_dal.create_order(
                buyer_id=buyer_id,
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )
            assert order_id == new_order_id
            mock_execute_non_query.assert_called_once()
            mock_execute_query.assert_called_once()

@pytest.mark.asyncio
async def test_create_order_with_negative_total_price_raises_value_error(orders_dal, mock_order_create_schema):
    # 测试总价为负数的情况，应抛出 ValueError
    mock_order_create_schema.total_price = -10.00
    with pytest.raises(ValueError, match="总价不能为负数"):
        await orders_dal.create_order(
            buyer_id=uuid4(),
            product_id=mock_order_create_schema.product_id,
            quantity=mock_order_create_schema.quantity,
            shipping_address=mock_order_create_schema.shipping_address,
            contact_phone=mock_order_create_schema.contact_phone
        )

@pytest.mark.asyncio
async def test_create_order_with_empty_shipping_address_raises_value_error(orders_dal, mock_order_create_schema):
    # 测试空收货地址，应抛出 ValueError
    mock_order_create_schema.shipping_address = ""
    with pytest.raises(ValueError, match="收货地址不能为空"):
        await orders_dal.create_order(
            buyer_id=uuid4(),
            product_id=mock_order_create_schema.product_id,
            quantity=mock_order_create_schema.quantity,
            shipping_address=mock_order_create_schema.shipping_address,
            contact_phone=mock_order_create_schema.contact_phone
        )

@pytest.mark.asyncio
async def test_create_order_with_empty_contact_phone_raises_value_error(orders_dal, mock_order_create_schema):
    # 测试空联系电话，应抛出 ValueError
    mock_order_create_schema.contact_phone = ""
    with pytest.raises(ValueError, match="联系电话不能为空"):
        await orders_dal.create_order(
            buyer_id=uuid4(),
            product_id=mock_order_create_schema.product_id,
            quantity=mock_order_create_schema.quantity,
            shipping_address=mock_order_create_schema.shipping_address,
            contact_phone=mock_order_create_schema.contact_phone
        )

@pytest.mark.asyncio
async def test_create_order_with_invalid_product_id_raises_value_error(orders_dal, mock_order_create_schema):
    # 测试无效的产品ID格式，应抛出 ValueError
    with pytest.raises(ValueError, match="无效的产品ID格式"):
        await orders_dal.create_order(
            buyer_id=uuid4(),
            product_id="invalid-product-id", # 无效格式
            quantity=mock_order_create_schema.quantity,
            shipping_address=mock_order_create_schema.shipping_address,
            contact_phone=mock_order_create_schema.contact_phone
        )

@pytest.mark.asyncio
async def test_create_order_with_invalid_buyer_id_raises_value_error(orders_dal, mock_order_create_schema):
    # 测试无效的买家ID格式，应抛出 ValueError
    with pytest.raises(ValueError, match="无效的买家ID格式"):
        await orders_dal.create_order(
            buyer_id="invalid-buyer-id", # 无效格式
            product_id=mock_order_create_schema.product_id,
            quantity=mock_order_create_schema.quantity,
            shipping_address=mock_order_create_schema.shipping_address,
            contact_phone=mock_order_create_schema.contact_phone
        )

@pytest.mark.asyncio
async def test_create_order_db_connection_error(orders_dal, mock_order_create_schema):
    # 模拟数据库连接错误
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.side_effect = pyodbc.Error("Database connection failed")
        with pytest.raises(DALError, match="数据库操作失败，无法创建订单"):
            await orders_dal.create_order(
                buyer_id=uuid4(),
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )

@pytest.mark.asyncio
async def test_create_order_db_insert_error(orders_dal, mock_order_create_schema):
    # 模拟数据库插入错误
    with patch('app.dal.base.execute_non_query', new_callable=AsyncMock) as mock_execute_non_query:
        mock_execute_non_query.side_effect = pyodbc.IntegrityError("Duplicate entry")
        with pytest.raises(DALError, match="数据库操作失败，无法创建订单"):
            await orders_dal.create_order(
                buyer_id=uuid4(),
                product_id=mock_order_create_schema.product_id,
                quantity=mock_order_create_schema.quantity,
                shipping_address=mock_order_create_schema.shipping_address,
                contact_phone=mock_order_create_schema.contact_phone
            )