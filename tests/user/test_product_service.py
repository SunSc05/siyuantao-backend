import pytest
import pytest_mock
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.product_service import ProductService
from app.dal.product_dal import ProductDAL
from app.dal.product_image_dal import ProductImageDAL
from app.dal.user_favorite_dal import UserFavoriteDAL
from app.exceptions import NotFoundError, DALError

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