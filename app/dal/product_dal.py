# import databases # Remove this import
from typing import List, Dict, Optional
import pyodbc # Import pyodbc for type hinting conn
from uuid import UUID
import logging

from app.exceptions import DALError, NotFoundError, IntegrityError, PermissionError, DatabaseError # Import DatabaseError

logger = logging.getLogger(__name__)

class ProductDAL:
    """
    商品数据访问层，负责与数据库进行交互，执行商品相关的CRUD操作
    """
    def __init__(self, execute_query_func):
        """
        初始化ProductDAL实例
        
        Args:
            execute_query_func: 通用的数据库执行函数，接收 conn, sql, params, fetchone/fetchall 等参数
        """
        self._execute_query = execute_query_func

    async def create_product(self, conn: pyodbc.Connection, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float) -> int:
        """
        创建新商品
        
        Args:
            conn: 数据库连接对象
            owner_id: 商品所有者ID
            category_name: 商品分类名称
            product_name: 商品名称
            description: 商品描述
            quantity: 商品数量
            price: 商品价格
        
        Returns:
            新商品ID
        
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
        # Execute the query and fetch the result (should be the new product ID)
        result = await self._execute_query(conn, query, values, fetchone=True)
        
        # Assuming the stored procedure returns the new product ID in a column named '新商品ID' or 'NewProductID'
        # Need to check the actual SP definition for the exact column name.
        # Based on 02_product_procedures.sql, it returns '新商品ID'.
        new_product_id = result.get('新商品ID') if result else None
        
        if not new_product_id:
            # Handle case where SP executed but did not return the expected ID
            raise DatabaseError("Failed to retrieve new product ID after creation.")
            
        return new_product_id # Return the new product ID

    async def update_product(self, conn: pyodbc.Connection, product_id: int, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float) -> None:
        """
        更新商品信息
        
        Args:
            conn: 数据库连接对象
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
        await self._execute_query(conn, query, values)

    async def delete_product(self, conn: pyodbc.Connection, product_id: int, owner_id: int) -> None:
        """
        删除商品
        
        Args:
            conn: 数据库连接对象
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
        await self._execute_query(conn, query, values)

    async def activate_product(self, conn: pyodbc.Connection, product_id: int, admin_id: int) -> None:
        """
        管理员审核通过商品，将商品状态设为Active
        
        Args:
            conn: 数据库连接对象
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
        await self._execute_query(conn, query, values)

    async def reject_product(self, conn: pyodbc.Connection, product_id: int, admin_id: int, reason: Optional[str] = None) -> None:
        """
        管理员拒绝商品，将商品状态设为Rejected
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            admin_id: 管理员ID
            reason: 拒绝原因，可选
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            PermissionError: 非管理员尝试操作时抛出
        """
        # Add logging
        logger.debug(f"DAL: Admin {admin_id} rejecting product {product_id} with reason: {reason}")
        # Modify query to include reason
        query = "EXEC sp_RejectProduct @productId = :product_id, @adminId = :admin_id, @reason = :reason"
        values = {
            "product_id": product_id,
            "admin_id": admin_id,
            "reason": reason
        }
        try:
            await self._execute_query(conn, query, values)
            # Add logging for success
            logger.info(f"DAL: Product {product_id} rejected successfully by admin {admin_id}")
        except pyodbc.Error as e:
            logger.error(f"DAL: Database error rejecting product {product_id}: {e}")
            raise DatabaseError(f"Database error rejecting product {product_id}: {e}") from e
        except Exception as e:
            # Catch other potential exceptions during execution
            logger.error(f"DAL: Unexpected error rejecting product {product_id}: {e}")
            raise DALError(f"Unexpected error rejecting product {product_id}: {e}") from e

    async def withdraw_product(self, conn: pyodbc.Connection, product_id: int, owner_id: int) -> None:
        """
        商品所有者下架商品，将商品状态设为Withdrawn
        
        Args:
            conn: 数据库连接对象
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
        await self._execute_query(conn, query, values)

    async def get_product_list(self, conn: pyodbc.Connection, category_id: Optional[int] = None, status: Optional[str] = None, 
                              keyword: Optional[str] = None, min_price: Optional[float] = None, 
                              max_price: Optional[float] = None, order_by: str = 'PostTime', 
                              page_number: int = 1, page_size: int = 10) -> List[Dict]:
        """
        获取商品列表，支持多种筛选条件和分页
        
        Args:
            conn: 数据库连接对象
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
        query = "EXEC sp_GetProductList @searchQuery = :searchQuery, @categoryName = :categoryName, @minPrice = :minPrice, @maxPrice = :maxPrice, @page = :pageNumber, @pageSize = :pageSize, @sortBy = :orderBy, @sortOrder = :sortOrder, @status = :status"
        values = {
            "searchQuery": keyword,
            "categoryName": category_id,
            "minPrice": min_price,
            "maxPrice": max_price,
            "pageNumber": page_number,
            "pageSize": page_size,
            "orderBy": order_by,
            "sortOrder": "DESC",
            "status": status
        }
        return await self._execute_query(conn, query, values, fetchall=True)

    async def get_product_by_id(self, conn: pyodbc.Connection, product_id: int) -> Optional[Dict]:
        """
        根据商品ID获取商品详情
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
        
        Returns:
            商品详情字典，如果不存在则返回None
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_GetProductDetail @productId = :product_id"
        values = {"product_id": product_id}
        product_detail = await self._execute_query(conn, query, values, fetchone=True)
        return product_detail

    async def decrease_product_quantity(self, conn: pyodbc.Connection, product_id: int, quantity_to_decrease: int) -> None:
        """
        减少商品库存，用于订单创建等场景
        
        Args:
            conn: 数据库连接对象
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
        await self._execute_query(conn, query, values)

    async def increase_product_quantity(self, conn: pyodbc.Connection, product_id: int, quantity_to_increase: int) -> None:
        """
        增加商品库存，用于订单取消等场景
        
        Args:
            conn: 数据库连接对象
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
        await self._execute_query(conn, query, values)

    async def batch_activate_products(self, conn: pyodbc.Connection, product_ids: List[int], admin_id: int) -> None:
        """
        批量激活商品
        
        Args:
            conn: 数据库连接对象
            product_ids: 商品ID列表 (List[int] - but SP expects NVARCHAR(MAX) of comma-separated UUIDs)
            admin_id: 管理员ID (int - but SP expects UNIQUEIDENTIFIER)
        """
        product_ids_str = ",".join(product_ids)
        admin_id_str = str(admin_id)

        query = "EXEC sp_BatchReviewProducts @productIds = :product_ids, @adminId = :admin_id, @newStatus = :newStatus, @reason = :reason"
        values = {
            "product_ids": product_ids_str,
            "admin_id": admin_id_str,
            "newStatus": "Active",
            "reason": None
        }
        result = await self._execute_query(conn, query, values, fetchone=True)
        return result.get('SuccessCount', 0) if result and isinstance(result, dict) else 0

    async def batch_reject_products(self, conn: pyodbc.Connection, product_ids: List[int], admin_id: int, reason: Optional[str] = None) -> None:
        """
        批量拒绝商品
        
        Args:
            conn: 数据库连接对象
            product_ids: 商品ID列表 (List[int] assumed to be List[str] of UUIDs)
            admin_id: 管理员ID (int assumed to be UUID string)
            reason: 拒绝原因
        """
        product_ids_str = ",".join(product_ids)
        admin_id_str = str(admin_id)

        query = "EXEC sp_BatchReviewProducts @productIds = :product_ids, @adminId = :admin_id, @newStatus = :newStatus, @reason = :reason"
        values = {
            "product_ids": product_ids_str,
            "admin_id": admin_id_str,
            "newStatus": "Rejected",
            "reason": reason
        }
        result = await self._execute_query(conn, query, values, fetchone=True)
        return result.get('SuccessCount', 0) if result and isinstance(result, dict) else 0


class ProductImageDAL:
    """
    商品图片数据访问层，负责与数据库进行交互，执行商品图片相关的操作
    """
    def __init__(self, execute_query_func):
        """
        初始化ProductImageDAL实例
        
        Args:
            execute_query_func: 通用的数据库执行函数
        """
        self._execute_query = execute_query_func

    async def add_product_image(self, conn: pyodbc.Connection, product_id: int, image_url: str, sort_order: int) -> None:
        """
        添加商品图片
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            image_url: 图片URL
            sort_order: 图片显示顺序
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "INSERT INTO [ProductImage] ([ProductID], [ImageURL], [SortOrder]) VALUES (?, ?, ?)"
        values = (product_id, image_url, sort_order)
        await self._execute_query(conn, query, values)

    async def get_images_by_product_id(self, conn: pyodbc.Connection, product_id: int) -> List[Dict]:
        """
        获取指定商品的所有图片
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
        
        Returns:
            图片URL列表
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "SELECT ImageID, ProductID, ImageURL, UploadTime, SortOrder FROM [ProductImage] WHERE ProductID = ? ORDER BY SortOrder ASC, UploadTime ASC"
        values = (product_id,)
        return await self._execute_query(conn, query, values, fetchall=True)

    async def delete_product_image(self, conn: pyodbc.Connection, image_id: int) -> None:
        """
        删除指定图片
        
        Args:
            conn: 数据库连接对象
            image_id: 图片ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "DELETE FROM [ProductImage] WHERE [ImageID] = ?"
        values = (image_id,)
        await self._execute_query(conn, query, values)

    async def delete_product_images_by_product_id(self, conn: pyodbc.Connection, product_id: int) -> None:
        """
        删除指定商品的所有图片
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "DELETE FROM [ProductImage] WHERE [ProductID] = ?"
        values = (product_id,)
        await self._execute_query(conn, query, values)


class UserFavoriteDAL:
    """
    用户收藏数据访问层，负责与数据库进行交互，执行用户收藏相关的操作
    """
    def __init__(self, execute_query_func):
        """
        初始化UserFavoriteDAL实例
        
        Args:
            execute_query_func: 通用的数据库执行函数
        """
        self._execute_query = execute_query_func

    async def add_user_favorite(self, conn: pyodbc.Connection, user_id: int, product_id: int) -> None:
        """
        添加用户收藏
        
        Args:
            conn: 数据库连接对象
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
            ValueError: 已收藏该商品时抛出
        """
        query = "EXEC sp_AddFavoriteProduct @userId = :user_id, @productId = :product_id"
        values = {
            "user_id": str(user_id),
            "product_id": str(product_id)
        }
        await self._execute_query(conn, query, values)

    async def remove_user_favorite(self, conn: pyodbc.Connection, user_id: int, product_id: int) -> None:
        """
        移除用户收藏
        
        Args:
            conn: 数据库连接对象
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_RemoveFavoriteProduct @userId = :user_id, @productId = :product_id"
        values = {
            "user_id": str(user_id),
            "product_id": str(product_id)
        }
        await self._execute_query(conn, query, values)

    async def get_user_favorite_products(self, conn: pyodbc.Connection, user_id: int) -> List[Dict]:
        """
        获取用户收藏的商品列表
        
        Args:
            conn: 数据库连接对象
            user_id: 用户ID
        
        Returns:
            商品列表，每个商品包含基本信息
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        query = "EXEC sp_GetUserFavoriteProducts @userId = :user_id"
        values = {"user_id": str(user_id)}
        return await self._execute_query(conn, query, values, fetchall=True)  