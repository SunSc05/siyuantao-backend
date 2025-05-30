import databases
from typing import List, Dict, Optional

class ProductDAL:
    """
    商品数据访问层，负责与数据库进行交互，执行商品相关的CRUD操作
    """
    def __init__(self, database: databases.Database):
        """
        初始化ProductDAL实例
        
        Args:
            database: 数据库连接对象
        """
        self.database = database

    async def create_product(self, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float) -> None:
        """
        创建新商品
        
        Args:
            owner_id: 商品所有者ID
            category_name: 商品分类名称
            product_name: 商品名称
            description: 商品描述
            quantity: 商品数量
            price: 商品价格
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_CreateProduct @ownerId = :owner_id, @categoryName = :category_name, @productName = :product_name, @description = :description, @quantity = :quantity, @price = :price"
        values = {
            "owner_id": owner_id,
            "category_name": category_name,
            "product_name": product_name,
            "description": description,
            "quantity": quantity,
            "price": price
        }
        await self.database.execute(query=query, values=values)

    async def update_product(self, product_id: int, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float) -> None:
        """
        更新商品信息
        
        Args:
            product_id: 商品ID
            owner_id: 商品所有者ID
            category_name: 商品分类名称
            product_name: 商品名称
            description: 商品描述
            quantity: 商品数量
            price: 商品价格
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            PermissionError: 非商品所有者尝试更新时抛出
        """
        query = "EXEC sp_UpdateProduct @productId = :product_id, @ownerId = :owner_id, @categoryName = :category_name, @productName = :product_name, @description = :description, @quantity = :quantity, @price = :price"
        values = {
            "product_id": product_id,
            "owner_id": owner_id,
            "category_name": category_name,
            "product_name": product_name,
            "description": description,
            "quantity": quantity,
            "price": price
        }
        await self.database.execute(query=query, values=values)

    async def delete_product(self, product_id: int, owner_id: int) -> None:
        """
        删除商品
        
        Args:
            product_id: 商品ID
            owner_id: 商品所有者ID或管理员ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            PermissionError: 非商品所有者或管理员尝试删除时抛出
        """
        query = "EXEC sp_DeleteProduct @productId = :product_id, @ownerId = :owner_id"
        values = {
            "product_id": product_id,
            "owner_id": owner_id
        }
        await self.database.execute(query=query, values=values)

    async def activate_product(self, product_id: int, admin_id: int) -> None:
        """
        管理员审核通过商品，将商品状态设为Active
        
        Args:
            product_id: 商品ID
            admin_id: 管理员ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            PermissionError: 非管理员尝试操作时抛出
        """
        query = "EXEC sp_ActivateProduct @productId = :product_id, @adminId = :admin_id"
        values = {
            "product_id": product_id,
            "admin_id": admin_id
        }
        await self.database.execute(query=query, values=values)

    async def reject_product(self, product_id: int, admin_id: int) -> None:
        """
        管理员拒绝商品，将商品状态设为Rejected
        
        Args:
            product_id: 商品ID
            admin_id: 管理员ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            PermissionError: 非管理员尝试操作时抛出
        """
        query = "EXEC sp_RejectProduct @productId = :product_id, @adminId = :admin_id"
        values = {
            "product_id": product_id,
            "admin_id": admin_id
        }
        await self.database.execute(query=query, values=values)

    async def withdraw_product(self, product_id: int, owner_id: int) -> None:
        """
        商品所有者下架商品，将商品状态设为Withdrawn
        
        Args:
            product_id: 商品ID
            owner_id: 商品所有者ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            PermissionError: 非商品所有者尝试操作时抛出
        """
        query = "EXEC sp_WithdrawProduct @productId = :product_id, @ownerId = :owner_id"
        values = {
            "product_id": product_id,
            "owner_id": owner_id
        }
        await self.database.execute(query=query, values=values)

    async def get_product_list(self, category_id: Optional[int] = None, status: Optional[str] = None, 
                              keyword: Optional[str] = None, min_price: Optional[float] = None, 
                              max_price: Optional[float] = None, order_by: str = 'PostTime', 
                              page_number: int = 1, page_size: int = 10) -> List[Dict]:
        """
        获取商品列表，支持多种筛选条件和分页
        
        Args:
            category_id: 商品分类ID，可选
            status: 商品状态，可选
            keyword: 搜索关键词，可选
            min_price: 最低价格，可选
            max_price: 最高价格，可选
            order_by: 排序字段，默认按发布时间
            page_number: 页码，默认第1页
            page_size: 每页数量，默认10条
        
        Returns:
            商品列表，每个商品包含基本信息
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_GetProductList @categoryId = :category_id, @status = :status, @keyword = :keyword, @minPrice = :min_price, @maxPrice = :max_price, @orderBy = :order_by, @pageNumber = :page_number, @pageSize = :page_size"
        values = {
            "category_id": category_id,
            "status": status,
            "keyword": keyword,
            "min_price": min_price,
            "max_price": max_price,
            "order_by": order_by,
            "page_number": page_number,
            "page_size": page_size
        }
        return await self.database.fetch_all(query=query, values=values)

    async def get_product_by_id(self, product_id: int) -> Optional[Dict]:
        """
        根据商品ID获取商品详情
        
        Args:
            product_id: 商品ID
        
        Returns:
            商品详情字典，如果不存在则返回None
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_GetProductById @productId = :product_id"
        values = {"product_id": product_id}
        return await self.database.fetch_one(query=query, values=values)

    async def decrease_product_quantity(self, product_id: int, quantity_to_decrease: int) -> None:
        """
        减少商品库存，用于订单创建等场景
        
        Args:
            product_id: 商品ID
            quantity_to_decrease: 要减少的数量
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            ValueError: 库存不足时抛出
        """
        query = "EXEC sp_DecreaseProductQuantity @productId = :product_id, @quantityToDecrease = :quantity_to_decrease"
        values = {
            "product_id": product_id,
            "quantity_to_decrease": quantity_to_decrease
        }
        await self.database.execute(query=query, values=values)

    async def increase_product_quantity(self, product_id: int, quantity_to_increase: int) -> None:
        """
        增加商品库存，用于订单取消等场景
        
        Args:
            product_id: 商品ID
            quantity_to_increase: 要增加的数量
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_IncreaseProductQuantity @productId = :product_id, @quantityToIncrease = :quantity_to_increase"
        values = {
            "product_id": product_id,
            "quantity_to_increase": quantity_to_increase
        }
        await self.database.execute(query=query, values=values)


class ProductImageDAL:
    """
    商品图片数据访问层，负责与数据库进行交互，执行商品图片相关的操作
    """
    def __init__(self, database: databases.Database):
        """
        初始化ProductImageDAL实例
        
        Args:
            database: 数据库连接对象
        """
        self.database = database

    async def add_product_image(self, product_id: int, image_url: str) -> None:
        """
        添加商品图片
        
        Args:
            product_id: 商品ID
            image_url: 图片URL
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "INSERT INTO [ProductImage] ([ProductID], [ImageURL]) VALUES (:product_id, :image_url)"
        values = {
            "product_id": product_id,
            "image_url": image_url
        }
        await self.database.execute(query=query, values=values)

    async def get_images_by_product_id(self, product_id: int) -> List[Dict]:
        """
        获取指定商品的所有图片
        
        Args:
            product_id: 商品ID
        
        Returns:
            图片URL列表
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_GetImagesByProduct @productId = :product_id"
        values = {"product_id": product_id}
        return await self.database.fetch_all(query=query, values=values)

    async def delete_product_image(self, image_id: int) -> None:
        """
        删除指定图片
        
        Args:
            image_id: 图片ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "DELETE FROM [ProductImage] WHERE [ImageID] = :image_id"
        values = {"image_id": image_id}
        await self.database.execute(query=query, values=values)

    async def delete_product_images_by_product_id(self, product_id: int) -> None:
        """
        删除指定商品的所有图片
        
        Args:
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "DELETE FROM [ProductImage] WHERE [ProductID] = :product_id"
        values = {"product_id": product_id}
        await self.database.execute(query=query, values=values)


class UserFavoriteDAL:
    """
    用户收藏数据访问层，负责与数据库进行交互，执行用户收藏相关的操作
    """
    def __init__(self, database: databases.Database):
        """
        初始化UserFavoriteDAL实例
        
        Args:
            database: 数据库连接对象
        """
        self.database = database

    async def add_user_favorite(self, user_id: int, product_id: int) -> None:
        """
        添加用户收藏
        
        Args:
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            ValueError: 已收藏该商品时抛出
        """
        query = "EXEC sp_AddUserFavorite @userId = :user_id, @productId = :product_id"
        values = {
            "user_id": user_id,
            "product_id": product_id
        }
        await self.database.execute(query=query, values=values)

    async def remove_user_favorite(self, user_id: int, product_id: int) -> None:
        """
        移除用户收藏
        
        Args:
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_RemoveUserFavorite @userId = :user_id, @productId = :product_id"
        values = {
            "user_id": user_id,
            "product_id": product_id
        }
        await self.database.execute(query=query, values=values)

    async def get_user_favorite_products(self, user_id: int) -> List[Dict]:
        """
        获取用户收藏的商品列表
        
        Args:
            user_id: 用户ID
        
        Returns:
            商品列表，每个商品包含基本信息
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_GetUserFavoriteProducts @userId = :user_id"
        values = {"user_id": user_id}
        return await self.database.fetch_all(query=query, values=values)
    
async def batch_activate_products(self, product_ids: List[int], admin_id: int) -> None:
    """
    批量激活商品
    
    Args:
        product_ids: 商品ID列表
        admin_id: 管理员ID
    """
    query = "EXEC sp_BatchActivateProducts @productIds = :product_ids, @adminId = :admin_id"
    values = {
        "product_ids": ",".join(map(str, product_ids)),
        "admin_id": admin_id
    }
    await self.database.execute(query=query, values=values)

async def batch_reject_products(self, product_ids: List[int], admin_id: int) -> None:
    """
    批量拒绝商品
    
    Args:
        product_ids: 商品ID列表
        admin_id: 管理员ID
    """
    query = "EXEC sp_BatchRejectProducts @productIds = :product_ids, @adminId = :admin_id"
    values = {
        "product_ids": ",".join(map(str, product_ids)),
        "admin_id": admin_id
    }
    await self.database.execute(query=query, values=values)  