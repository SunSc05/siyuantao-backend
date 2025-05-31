from typing import List, Dict, Optional
from ..schemas.product import ProductUpdate
from ..dal.product_dal import ProductDAL, ProductImageDAL, UserFavoriteDAL
import pyodbc

class ProductService:
    """
    商品服务层，处理商品相关的业务逻辑，协调DAL层完成复杂操作
    """
    def __init__(self, product_dal: ProductDAL, product_image_dal: ProductImageDAL, user_favorite_dal: UserFavoriteDAL):
        """
        初始化ProductService实例
        
        Args:
            product_dal: ProductDAL 实例
            product_image_dal: ProductImageDAL 实例
            user_favorite_dal: UserFavoriteDAL 实例
        """
        self.product_dal = product_dal
        self.product_image_dal = product_image_dal
        self.user_favorite_dal = user_favorite_dal

    async def create_product(self, conn: pyodbc.Connection, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float, image_urls: List[str]) -> None:
        """
        创建商品及其图片
        
        Args:
            conn: 数据库连接对象
            owner_id: 商品所有者ID
            category_name: 商品分类名称
            product_name: 商品名称
            description: 商品描述
            quantity: 商品数量
            price: 商品价格
            image_urls: 商品图片URL列表 (List[str])
        
        Raises:
            ValueError: 输入数据验证失败时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 数据验证
        if quantity < 0 or price < 0:
            raise ValueError("Quantity and price must be non-negative.")
        
        # 创建商品
        new_product_id = await self.product_dal.create_product(conn, owner_id, category_name, product_name, description, quantity, price)
        
        # Add product images using the new product ID
        # Check if image_urls is not empty before adding
        if image_urls:
            sort_order = 0 # Use 0 for the first image, then increment
            for image_url in image_urls:
                # Call the DAL method, passing the new product ID, image URL, and sort_order
                await self.product_image_dal.add_product_image(conn, new_product_id, image_url, sort_order)
                sort_order += 1

    async def update_product(self, conn: pyodbc.Connection, product_id: int, owner_id: int, product_update_data: ProductUpdate) -> None:
        """
        更新商品及其图片
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            owner_id: 商品所有者ID
            product_update_data: 商品更新数据 Pydantic Schema
        
        Raises:
            ValueError: 输入数据验证失败时抛出
            PermissionError: 非商品所有者尝试更新时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品信息进行权限检查
        product = await self.product_dal.get_product_by_id(conn, product_id)
        if not product:
            raise ValueError("Product not found")
        
        # 权限检查
        if str(product.get("OwnerID")) != str(owner_id):
            raise PermissionError("You are not the owner of this product.")
        
        # Extract data from the schema, excluding None values
        update_data = product_update_data.model_dump(exclude_none=True)
        
        # Separate image_urls from other update data
        image_urls = update_data.pop('image_urls', None)
        
        # Call DAL to update product basic info (if there is data other than images)
        if update_data:
             await self.product_dal.update_product(conn, product_id, owner_id, **update_data)
        
        # Handle image updates if image_urls were provided
        if image_urls is not None:
             # First, delete existing images for this product
             await self.product_image_dal.delete_product_images_by_product_id(conn, product_id)
             
             # Then add the new images with sort order
             if image_urls:
                  sort_order = 0
                  for image_url in image_urls:
                      await self.product_image_dal.add_product_image(conn, product_id, image_url, sort_order)
                      sort_order += 1

    async def delete_product(self, conn: pyodbc.Connection, product_id: int, owner_id: int) -> None:
        """
        删除商品及其关联数据
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            owner_id: 商品所有者ID
        
        Raises:
            PermissionError: 非商品所有者尝试删除时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品信息进行权限检查
        product = await self.product_dal.get_product_by_id(conn, product_id)
        if not product:
            raise ValueError("Product not found")
        
        # 权限检查
        if str(product.get("OwnerID")) != str(owner_id):
            raise PermissionError("You are not the owner of this product.")
        
        # 先删除商品图片
        await self.product_image_dal.delete_product_images_by_product_id(conn, product_id)
        
        # 再删除商品
        await self.product_dal.delete_product(conn, product_id, owner_id)

    async def activate_product(self, conn: pyodbc.Connection, product_id: int, admin_id: int) -> None:
        """
        管理员审核通过商品
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            admin_id: 管理员ID
        
        Raises:
            PermissionError: 非管理员尝试操作时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 管理员权限检查
        if not await self.check_admin_permission(conn, admin_id):
            raise PermissionError("You are not an admin.")
        
        # 激活商品
        await self.product_dal.activate_product(conn, product_id, admin_id)

    async def reject_product(self, conn: pyodbc.Connection, product_id: int, admin_id: int, reason: Optional[str] = None) -> None:
        """
        管理员拒绝商品
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            admin_id: 管理员ID
            reason: 拒绝原因
        
        Raises:
            PermissionError: 非管理员尝试操作时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 管理员权限检查
        # In the DAL, we should trust that the admin_id passed from service is valid
        # as the router already performed the check. However, for robustness, we can keep this check.
        if not await self.check_admin_permission(conn, admin_id):
            raise PermissionError("You are not an admin.")
        
        # 拒绝商品
        await self.product_dal.reject_product(conn, product_id, admin_id, reason) # Pass reason to DAL

    async def withdraw_product(self, conn: pyodbc.Connection, product_id: int, owner_id: int) -> None:
        """
        商品所有者下架商品
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
            owner_id: 商品所有者ID
        
        Raises:
            PermissionError: 非商品所有者尝试操作时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品信息进行权限检查
        product = await self.product_dal.get_product_by_id(conn, product_id)
        if not product:
            raise ValueError("Product not found")
        
        # 权限检查
        if str(product.get("OwnerID")) != str(owner_id):
            raise PermissionError("You are not the owner of this product.")
        
        # 下架商品
        await self.product_dal.withdraw_product(conn, product_id, owner_id)

    async def get_product_list(self, conn: pyodbc.Connection, category_id: Optional[int] = None, status: Optional[str] = None, 
                              keyword: Optional[str] = None, min_price: Optional[float] = None, 
                              max_price: Optional[float] = None, order_by: str = 'PostTime', 
                              page_number: int = 1, page_size: int = 10) -> List[Dict]:
        """
        获取商品列表，包含商品图片信息
        
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
            商品列表，每个商品包含基本信息和图片列表
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品列表
        products = await self.product_dal.get_product_list(conn,
            category_id, status, keyword, min_price, max_price, order_by, page_number, page_size
        )
        
        # 为每个商品添加图片信息
        for product in products:
            product["images"] = await self.product_image_dal.get_images_by_product_id(conn, product.get("商品ID"))
        
        return products

    async def get_product_detail(self, conn: pyodbc.Connection, product_id: int) -> Optional[Dict]:
        """
        获取商品详情，包含商品图片信息
        
        Args:
            conn: 数据库连接对象
            product_id: 商品ID
        
        Returns:
            商品详情字典，包含基本信息和图片列表，如果不存在则返回None
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品基本信息
        product = await self.product_dal.get_product_by_id(conn, product_id)
        
        if product:
            # 添加图片信息
            product["images"] = await self.product_image_dal.get_images_by_product_id(conn, product_id)
        
        return product

    async def add_favorite(self, conn: pyodbc.Connection, user_id: int, product_id: int) -> None:
        """
        用户收藏商品
        
        Args:
            conn: 数据库连接对象
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            ValueError: 已收藏该商品时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        try:
            await self.user_favorite_dal.add_user_favorite(conn, user_id, product_id)
        except Exception as e:
            # 处理重复收藏异常
            if isinstance(e, IntegrityError) or ("该商品已被您收藏" in str(e)):
                raise ValueError("You have already favorited this product.")
            else:
                raise e

    async def remove_favorite(self, conn: pyodbc.Connection, user_id: int, product_id: int) -> None:
        """
        用户取消收藏商品
        
        Args:
            conn: 数据库连接对象
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        await self.user_favorite_dal.remove_user_favorite(conn, user_id, product_id)

    async def get_user_favorites(self, conn: pyodbc.Connection, user_id: int) -> List[Dict]:
        """
        获取用户收藏的商品列表，包含商品详情和图片信息
        
        Args:
            conn: 数据库连接对象
            user_id: 用户ID
        
        Returns:
            商品列表，每个商品包含基本信息和图片列表
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取用户收藏的商品ID列表
        favorite_products = await self.user_favorite_dal.get_user_favorite_products(conn, user_id)
        
        # 获取每个商品的详细信息
        product_details = []
        for product in favorite_products:
            product_detail = await self.get_product_detail(conn, product.get("商品ID"))
            if product_detail:
                product_details.append(product_detail)
        
        return product_details

    async def check_admin_permission(self, conn: pyodbc.Connection, admin_id: int) -> bool:
        """
        检查用户是否具有管理员权限
        
        Args:
            conn: 数据库连接对象
            admin_id: 用户ID
        
        Returns:
            True表示具有管理员权限，False表示没有
        
        Note:
            实际实现中需要根据业务逻辑验证用户权限
        """
        # 这里需要实现具体的管理员权限检查逻辑
        # 示例中假设用户ID为1的是管理员
        # In a real application, you would query the database to check if the user has admin role/permissions.
        # For this mock/test environment, we'll assume a specific admin ID or role status.
        # Assuming admin_id is a UUID or something that can be directly used
        # For now, let's keep it simple. If admin_id needs to be a UUID in DAL, it should be converted.
        # Based on previous discussions and tests, `admin_id` here is an int from the `get_current_active_admin_user` dependency.
        # The `User` table has `UserID` as `int` and `IsStaff` as `bit`.
        # We should query the `User` table to check `IsStaff` status.
        query = "SELECT IsStaff FROM [User] WHERE UserID = ?"
        # Convert admin_id to str for UUID comparison if UserID is UUID, otherwise use as is for int.
        # From product_routes.py, owner_id is converted to int. So admin_id should be int here too.
        values = (admin_id,)
        result = await self._execute_query(conn, query, values, fetchone=True) # Assuming _execute_query is available here
        is_staff = result.get('IsStaff') if result and isinstance(result, dict) else False
        return bool(is_staff)

    async def batch_activate_products(self, conn: pyodbc.Connection, product_ids: List[int], admin_id: int) -> int:
        """
        批量激活商品
        
        Args:
            conn: 数据库连接对象
            product_ids: 商品ID列表
            admin_id: 管理员ID
        Returns:
            成功激活的商品数量
        """
        if not await self.check_admin_permission(conn, admin_id):
            raise PermissionError("You are not an admin.")
        
        success_count = await self.product_dal.batch_activate_products(conn, product_ids, admin_id)
        return success_count

    async def batch_reject_products(self, conn: pyodbc.Connection, product_ids: List[int], admin_id: int, reason: Optional[str] = None) -> int:
        """
        批量拒绝商品
        
        Args:
            conn: 数据库连接对象
            product_ids: 商品ID列表
            admin_id: 管理员ID
            reason: 拒绝原因
        Returns:
            成功拒绝的商品数量
        """
        if not await self.check_admin_permission(conn, admin_id):
            raise PermissionError("You are not an admin.")
        
        success_count = await self.product_dal.batch_reject_products(conn, product_ids, admin_id, reason) # Pass reason to DAL
        return success_count