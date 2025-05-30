import pytest
import pytest_mock
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.product_service import ProductService
from app.dal.product_dal import ProductDAL
from app.dal.product_image_dal import ProductImageDAL
from app.dal.user_favorite_dal import UserFavoriteDAL
from app.exceptions import NotFoundError, DALError
from datetime import datetime

# 模拟DAL依赖
@pytest.fixture
def mock_product_dal(mocker: pytest_mock.MockerFixture):
    mock_dal = AsyncMock(spec=ProductDAL)
    mock_dal.create_product = AsyncMock()
    mock_dal.get_product_detail = AsyncMock()
    return mock_dal

@pytest.fixture
def mock_image_dal(mocker: pytest_mock.MockerFixture):
    return AsyncMock(spec=ProductImageDAL)

@pytest.fixture
def mock_favorite_dal(mocker: pytest_mock.MockerFixture):
    return AsyncMock(spec=UserFavoriteDAL)

@pytest.fixture
def product_service(mock_product_dal, mock_image_dal, mock_favorite_dal):
    return ProductService(
        product_dal=mock_product_dal,
        product_image_dal=mock_image_dal,
        user_favorite_dal=mock_favorite_dal
    )

# --- ProductService 测试 ---
@pytest.mark.asyncio
async def test_create_product_success(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_data = ProductCreate(
        category_name="测试分类",
        product_name="测试商品",
        quantity=10,
        price=99.9,
        image_urls=["https://example.com/image.jpg"]
    )
    
    # 模拟DAL返回
    mock_product_dal.create_product.return_value = {"product_id": uuid4()}
    
    # 调用服务
    result = await product_service.create_product(
        owner_id=owner_id,
        **product_data.dict()
    )
    
    # 断言
    assert result == {"product_id": mock_product_dal.create_product.return_value["product_id"]}
    mock_product_dal.create_product.assert_called_once_with(
        owner_id=owner_id,
        category_name=product_data.category_name,
        product_name=product_data.product_name,
        description=product_data.description,
        quantity=product_data.quantity,
        price=product_data.price,
        image_urls=product_data.image_urls
    )

@pytest.mark.asyncio
async def test_get_product_detail_not_found(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟DAL返回None
    mock_product_dal.get_product_detail.return_value = None
    
    # 调用服务并断言异常
    with pytest.raises(NotFoundError):
        await product_service.get_product_detail(product_id=uuid4())

# --- 批量审核测试 ---
@pytest.mark.asyncio
async def test_batch_review_products(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟参数
    product_ids = [uuid4(), uuid4()]
    admin_id = uuid4()
    new_status = "Rejected"
    reason = "测试拒绝原因"
    
    # 模拟DAL返回成功数量
    mock_product_dal.batch_review_products.return_value = 2
    
    # 调用服务
    result = await product_service.batch_review_products(
        product_ids=product_ids,
        admin_id=admin_id,
        new_status=new_status,
        reason=reason
    )
    
    # 断言
    assert result == 2
    mock_product_dal.batch_review_products.assert_called_once_with(
        product_ids=product_ids,
        admin_id=admin_id,
        new_status=new_status,
        reason=reason
    )

@pytest.mark.asyncio
async def test_update_product_success(product_service: ProductService, mock_product_dal: AsyncMock, mock_image_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_id = uuid4()
    update_data = ProductUpdate(
        category_name="Updated Category",
        product_name="Updated Product",
        description="Updated Description",
        quantity=5,
        price=123.45,
        image_urls=["http://updated.com/image1.jpg"]
    )

    # 模拟 DAL 返回，表示商品存在且属于该用户
    mock_product_dal.get_product_by_id.return_value = {"ProductID": product_id, "OwnerID": owner_id}
    mock_product_dal.update_product.return_value = None # Assuming update_product in DAL doesn't return data
    mock_image_dal.delete_product_images_by_product_id.return_value = None
    mock_image_dal.add_product_image.return_value = None

    # 调用服务
    await product_service.update_product(
        conn=MagicMock(), # Pass a mock connection
        product_id=product_id,
        owner_id=owner_id,
        category_name=update_data.category_name,
        product_name=update_data.product_name,
        description=update_data.description,
        quantity=update_data.quantity,
        price=update_data.price,
        image_urls=update_data.image_urls
    )

    # 断言 DAL 方法是否被正确调用
    mock_product_dal.get_product_by_id.assert_called_once_with(MagicMock(), product_id)
    mock_product_dal.update_product.assert_called_once_with(
        MagicMock(), product_id, owner_id, update_data.category_name, 
        update_data.product_name, update_data.description, update_data.quantity, update_data.price
    )
    mock_image_dal.delete_product_images_by_product_id.assert_called_once_with(MagicMock(), product_id)
    mock_image_dal.add_product_image.assert_called_once_with(MagicMock(), product_id, update_data.image_urls[0])

@pytest.mark.asyncio
async def test_update_product_permission_denied(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    other_user_id = uuid4()
    product_id = uuid4()
    update_data = ProductUpdate(
        category_name="Updated Category",
        product_name="Updated Product",
        description="Updated Description",
        quantity=5,
        price=123.45,
        image_urls=["http://updated.com/image1.jpg"]
    )

    # 模拟 DAL 返回，表示商品存在但不属于当前用户
    mock_product_dal.get_product_by_id.return_value = {"ProductID": product_id, "OwnerID": owner_id}

    # 调用服务并断言权限错误异常
    with pytest.raises(PermissionError) as excinfo:
        await product_service.update_product(
            conn=MagicMock(),
            product_id=product_id,
            owner_id=other_user_id, # Use different owner ID
            category_name=update_data.category_name,
            product_name=update_data.product_name,
            description=update_data.description,
            quantity=update_data.quantity,
            price=update_data.price,
            image_urls=update_data.image_urls
        )

    # 断言异常信息
    assert "You are not the owner of this product." in str(excinfo.value)

    # 断言 DAL 的 update 方法没有被调用
    mock_product_dal.update_product.assert_not_called()
    mock_product_dal.delete_product_images_by_product_id.assert_not_called()
    mock_image_dal.add_product_image.assert_not_called()

@pytest.mark.asyncio
async def test_update_product_not_found(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_id = uuid4()
    update_data = ProductUpdate(
        category_name="Updated Category",
        product_name="Updated Product",
        description="Updated Description",
        quantity=5,
        price=123.45,
        image_urls=["http://updated.com/image1.jpg"]
    )

    # 模拟 DAL 返回 None，表示商品不存在
    mock_product_dal.get_product_by_id.return_value = None

    # 调用服务并断言商品未找到异常
    with pytest.raises(ValueError) as excinfo:
        await product_service.update_product(
            conn=MagicMock(),
            product_id=product_id,
            owner_id=owner_id,
            category_name=update_data.category_name,
            product_name=update_data.product_name,
            description=update_data.description,
            quantity=update_data.quantity,
            price=update_data.price,
            image_urls=update_data.image_urls
        )

    # 断言异常信息
    assert "Product not found" in str(excinfo.value)

    # 断言 DAL 的 update 方法没有被调用
    mock_product_dal.update_product.assert_not_called()
    mock_product_dal.delete_product_images_by_product_id.assert_not_called()
    mock_image_dal.add_product_image.assert_not_called()

@pytest.mark.asyncio
async def test_delete_product_success(product_service: ProductService, mock_product_dal: AsyncMock, mock_image_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 返回，表示商品存在且属于该用户
    mock_product_dal.get_product_by_id.return_value = {"ProductID": product_id, "OwnerID": owner_id}
    mock_product_dal.delete_product.return_value = None # Assuming delete_product in DAL doesn't return data
    mock_image_dal.delete_product_images_by_product_id.return_value = None

    # 调用服务
    await product_service.delete_product(
        conn=MagicMock(), # Pass a mock connection
        product_id=product_id,
        owner_id=owner_id
    )

    # 断言 DAL 方法是否被正确调用
    mock_product_dal.get_product_by_id.assert_called_once_with(MagicMock(), product_id)
    mock_image_dal.delete_product_images_by_product_id.assert_called_once_with(MagicMock(), product_id)
    mock_product_dal.delete_product.assert_called_once_with(MagicMock(), product_id, owner_id)

@pytest.mark.asyncio
async def test_delete_product_permission_denied(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    other_user_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 返回，表示商品存在但不属于当前用户
    mock_product_dal.get_product_by_id.return_value = {"ProductID": product_id, "OwnerID": owner_id}

    # 调用服务并断言权限错误异常
    with pytest.raises(PermissionError) as excinfo:
        await product_service.delete_product(
            conn=MagicMock(),
            product_id=product_id,
            owner_id=other_user_id # Use different owner ID
        )

    # 断言异常信息
    assert "You are not the owner of this product." in str(excinfo.value)

    # 断言 DAL 的 delete 方法没有被调用
    mock_product_dal.delete_product.assert_not_called()

@pytest.mark.asyncio
async def test_delete_product_not_found(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 返回 None，表示商品不存在
    mock_product_dal.get_product_by_id.return_value = None

    # 调用服务并断言商品未找到异常
    with pytest.raises(ValueError) as excinfo:
        await product_service.delete_product(
            conn=MagicMock(),
            product_id=product_id,
            owner_id=owner_id
        )

    # 断言异常信息
    assert "Product not found" in str(excinfo.value)

    # 断言 DAL 的 delete 方法没有被调用
    mock_product_dal.delete_product.assert_not_called()

@pytest.mark.asyncio
async def test_withdraw_product_success(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 返回，表示商品存在且属于该用户
    mock_product_dal.get_product_by_id.return_value = {"ProductID": product_id, "OwnerID": owner_id}
    mock_product_dal.withdraw_product.return_value = None # Assuming withdraw_product in DAL doesn't return data

    # 调用服务
    await product_service.withdraw_product(
        conn=MagicMock(), # Pass a mock connection
        product_id=product_id,
        owner_id=owner_id
    )

    # 断言 DAL 方法是否被正确调用
    mock_product_dal.get_product_by_id.assert_called_once_with(MagicMock(), product_id)
    mock_product_dal.withdraw_product.assert_called_once_with(MagicMock(), product_id, owner_id)

@pytest.mark.asyncio
async def test_withdraw_product_permission_denied(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    other_user_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 返回，表示商品存在但不属于当前用户
    mock_product_dal.get_product_by_id.return_value = {"ProductID": product_id, "OwnerID": owner_id}

    # 调用服务并断言权限错误异常
    with pytest.raises(PermissionError) as excinfo:
        await product_service.withdraw_product(
            conn=MagicMock(),
            product_id=product_id,
            owner_id=other_user_id # Use different owner ID
        )

    # 断言异常信息
    assert "You are not the owner of this product." in str(excinfo.value)

    # 断言 DAL 的 withdraw 方法没有被调用
    mock_product_dal.withdraw_product.assert_not_called()

@pytest.mark.asyncio
async def test_withdraw_product_not_found(product_service: ProductService, mock_product_dal: AsyncMock):
    # 模拟数据
    owner_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 返回 None，表示商品不存在
    mock_product_dal.get_product_by_id.return_value = None

    # 调用服务并断言商品未找到异常
    with pytest.raises(ValueError) as excinfo:
        await product_service.withdraw_product(
            conn=MagicMock(),
            product_id=product_id,
            owner_id=owner_id
        )

    # 断言异常信息
    assert "Product not found" in str(excinfo.value)

    # 断言 DAL 的 withdraw 方法没有被调用
    mock_product_dal.withdraw_product.assert_not_called()

@pytest.mark.asyncio
async def test_add_favorite_success(product_service: ProductService, mock_favorite_dal: AsyncMock):
    # 模拟数据
    user_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 成功返回
    mock_favorite_dal.add_user_favorite.return_value = None # Assuming DAL doesn't return data on success

    # 调用服务
    await product_service.add_favorite(
        conn=MagicMock(),
        user_id=user_id,
        product_id=product_id
    )

    # 断言 DAL 方法是否被正确调用
    mock_favorite_dal.add_user_favorite.assert_called_once_with(MagicMock(), user_id, product_id)

@pytest.mark.asyncio
async def test_add_favorite_already_favorited(product_service: ProductService, mock_favorite_dal: AsyncMock):
    # 模拟数据
    user_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 抛出 IntegrityError (表示已存在)
    mock_favorite_dal.add_user_favorite.side_effect = IntegrityError("该商品已被您收藏") # Use the actual expected message

    # 调用服务并断言 ValueError (Service 层将 IntegrityError 转换为 ValueError)
    with pytest.raises(ValueError) as excinfo:
        await product_service.add_favorite(
            conn=MagicMock(),
            user_id=user_id,
            product_id=product_id
        )

    # 断言异常信息
    assert "You have already favorited this product." in str(excinfo.value)

    # 断言 DAL 方法被调用
    mock_favorite_dal.add_user_favorite.assert_called_once_with(MagicMock(), user_id, product_id)

@pytest.mark.asyncio
async def test_remove_favorite_success(product_service: ProductService, mock_favorite_dal: AsyncMock):
    # 模拟数据
    user_id = uuid4()
    product_id = uuid4()

    # 模拟 DAL 成功返回
    mock_favorite_dal.remove_user_favorite.return_value = None # Assuming DAL doesn't return data on success

    # 调用服务
    await product_service.remove_favorite(
        conn=MagicMock(),
        user_id=user_id,
        product_id=product_id
    )

    # 断言 DAL 方法是否被正确调用
    mock_favorite_dal.remove_user_favorite.assert_called_once_with(MagicMock(), user_id, product_id)

@pytest.mark.asyncio
async def test_get_user_favorites_success(product_service: ProductService, mock_favorite_dal: AsyncMock, mock_product_dal: AsyncMock):
    # 模拟数据
    user_id = uuid4()
    # 模拟 DAL 返回收藏的商品列表 (只包含基本信息，Service 层需要获取详情)
    dal_favorites = [
        {"商品ID": uuid4(), "ProductID": uuid4(), "FavoriteTime": datetime.now()},
        {"商品ID": uuid4(), "ProductID": uuid4(), "FavoriteTime": datetime.now()},
    ]
    mock_favorite_dal.get_user_favorite_products.return_value = dal_favorites

    # 模拟 Product DAL 返回商品详情
    mock_product_dal.get_product_detail.side_effect = lambda conn, product_id: {"商品ID": product_id, "商品名称": f"商品_{product_id}", "images": []} # Simplified detail

    # 调用服务
    favorites_with_details = await product_service.get_user_favorites(MagicMock(), user_id)

    # 断言 DAL 方法是否被正确调用
    mock_favorite_dal.get_user_favorite_products.assert_called_once_with(MagicMock(), user_id)
    # 断言 get_product_detail 是否为每个收藏商品调用
    assert mock_product_dal.get_product_detail.call_count == len(dal_favorites)

    # 断言返回结果结构和内容
    assert isinstance(favorites_with_details, list)
    assert len(favorites_with_details) == len(dal_favorites)
    assert "商品名称" in favorites_with_details[0]
    assert "images" in favorites_with_details[0]