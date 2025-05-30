from typing import List, Dict, Optional
from ..dal.product_dal import ProductDAL
from .dal.product_image_dal import ProductImageDAL
from ..dal.user_favorite_dal import UserFavoriteDAL

class ProductService:
    """
    商品服务层，处理商品相关的业务逻辑，协调DAL层完成复杂操作
    """
    def __init__(self, product_dal: ProductDAL, product_image_dal: ProductImageDAL, user_favorite_dal: UserFavoriteDAL):
        """
        初始化ProductService实例
        
        Args:
            product_dal: 商品数据访问层实例
            product_image_dal: 商品图片数据访问层实例
            user_favorite_dal: 用户收藏数据访问层实例
        """
        self.product_dal = product_dal
        self.product_image_dal = product_image_dal
        self.user_favorite_dal = user_favorite_dal

    async def create_product(self, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float, image_urls: List[str]) -> None:
        """
        创建商品及其图片
        
        Args:
            owner_id: 商品所有者ID
            category_name: 商品分类名称
            product_name: 商品名称
            description: 商品描述
            quantity: 商品数量
            price: 商品价格
            image_urls: 商品图片URL列表
        
        Raises:
            ValueError: 输入数据验证失败时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 数据验证
        if quantity < 0 or price < 0:
            raise ValueError("Quantity and price must be non-negative.")
        
        # 创建商品
        await self.product_dal.create_product(owner_id, category_name, product_name, description, quantity, price)
        
        # 获取新创建的商品ID
        product = await self.product_dal.get_product_by_id(await self.product_dal.get_last_inserted_id())
        
        # 添加商品图片
        for image_url in image_urls:
            await self.product_image_dal.add_product_image(product["ProductID"], image_url)

    async def update_product(self, product_id: int, owner_id: int, category_name: str, product_name: str, 
                            description: str, quantity: int, price: float, image_urls: List[str]) -> None:
        """
        更新商品及其图片
        
        Args:
            product_id: 商品ID
            owner_id: 商品所有者ID
            category_name: 商品分类名称
            product_name: 商品名称
            description: 商品描述
            quantity: 商品数量
            price: 商品价格
            image_urls: 商品图片URL列表
        
        Raises:
            ValueError: 输入数据验证失败时抛出
            PermissionError: 非商品所有者尝试更新时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品信息进行权限检查
        product = await self.product_dal.get_product_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        
        # 权限检查
        if product["OwnerID"] != owner_id:
            raise PermissionError("You are not the owner of this product.")
        
        # 数据验证
        if quantity < 0 or price < 0:
            raise ValueError("Quantity and price must be non-negative.")
        
        # 更新商品信息
        await self.product_dal.update_product(product_id, owner_id, category_name, product_name, description, quantity, price)
        
        # 先删除原有图片
        await self.product_image_dal.delete_product_images_by_product_id(product_id)
        
        # 添加新图片
        for image_url in image_urls:
            await self.product_image_dal.add_product_image(product_id, image_url)

    async def delete_product(self, product_id: int, owner_id: int) -> None:
        """
        删除商品及其关联数据
        
        Args:
            product_id: 商品ID
            owner_id: 商品所有者ID
        
        Raises:
            PermissionError: 非商品所有者尝试删除时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品信息进行权限检查
        product = await self.product_dal.get_product_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        
        # 权限检查
        if product["OwnerID"] != owner_id:
            raise PermissionError("You are not the owner of this product.")
        
        # 先删除商品图片
        await self.product_image_dal.delete_product_images_by_product_id(product_id)
        
        # 再删除商品
        await self.product_dal.delete_product(product_id, owner_id)

    async def activate_product(self, product_id: int, admin_id: int) -> None:
        """
        管理员审核通过商品
        
        Args:
            product_id: 商品ID
            admin_id: 管理员ID
        
        Raises:
            PermissionError: 非管理员尝试操作时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 管理员权限检查
        if not await self.check_admin_permission(admin_id):
            raise PermissionError("You are not an admin.")
        
        # 激活商品
        await self.product_dal.activate_product(product_id, admin_id)

    async def reject_product(self, product_id: int, admin_id: int) -> None:
        """
        管理员拒绝商品
        
        Args:
            product_id: 商品ID
            admin_id: 管理员ID
        
        Raises:
            PermissionError: 非管理员尝试操作时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 管理员权限检查
        if not await self.check_admin_permission(admin_id):
            raise PermissionError("You are not an admin.")
        
        # 拒绝商品
        await self.product_dal.reject_product(product_id, admin_id)

    async def withdraw_product(self, product_id: int, owner_id: int) -> None:
        """
        商品所有者下架商品
        
        Args:
            product_id: 商品ID
            owner_id: 商品所有者ID
        
        Raises:
            PermissionError: 非商品所有者尝试操作时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品信息进行权限检查
        product = await self.product_dal.get_product_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        
        # 权限检查
        if product["OwnerID"] != owner_id:
            raise PermissionError("You are not the owner of this product.")
        
        # 下架商品
        await self.product_dal.withdraw_product(product_id, owner_id)

    async def get_product_list(self, category_id: Optional[int] = None, status: Optional[str] = None, 
                              keyword: Optional[str] = None, min_price: Optional[float] = None, 
                              max_price: Optional[float] = None, order_by: str = 'PostTime', 
                              page_number: int = 1, page_size: int = 10) -> List[Dict]:
        """
        获取商品列表，包含商品图片信息
        
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
            商品列表，每个商品包含基本信息和图片列表
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品列表
        products = await self.product_dal.get_product_list(
            category_id, status, keyword, min_price, max_price, order_by, page_number, page_size
        )
        
        # 为每个商品添加图片信息
        for product in products:
            product["images"] = await self.product_image_dal.get_images_by_product_id(product["ProductID"])
        
        return products

    async def get_product_detail(self, product_id: int) -> Optional[Dict]:
        """
        获取商品详情，包含商品图片信息
        
        Args:
            product_id: 商品ID
        
        Returns:
            商品详情字典，包含基本信息和图片列表，如果不存在则返回None
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取商品基本信息
        product = await self.product_dal.get_product_by_id(product_id)
        
        if product:
            # 添加图片信息
            product["images"] = await self.product_image_dal.get_images_by_product_id(product_id)
        
        return product

    async def add_favorite(self, user_id: int, product_id: int) -> None:
        """
        用户收藏商品
        
        Args:
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            ValueError: 已收藏该商品时抛出
            DatabaseError: 数据库操作失败时抛出
        """
        try:
            await self.user_favorite_dal.add_user_favorite(user_id, product_id)
        except Exception as e:
            # 处理重复收藏异常
            if "Violation of UNIQUE KEY constraint" in str(e):
                raise ValueError("You have already favorited this product.")
            else:
                raise e

    async def remove_favorite(self, user_id: int, product_id: int) -> None:
        """
        用户取消收藏商品
        
        Args:
            user_id: 用户ID
            product_id: 商品ID
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        await self.user_favorite_dal.remove_user_favorite(user_id, product_id)

    async def get_user_favorites(self, user_id: int) -> List[Dict]:
        """
        获取用户收藏的商品列表，包含商品详情和图片信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            商品列表，每个商品包含基本信息和图片列表
        
        Raises:
            DatabaseError: 数据库操作失败时抛出
        """
        # 获取用户收藏的商品ID列表
        favorite_products = await self.user_favorite_dal.get_user_favorite_products(user_id)
        
        # 获取每个商品的详细信息
        product_details = []
        for product in favorite_products:
            product_detail = await self.get_product_detail(product["ProductID"])
            if product_detail:
                product_details.append(product_detail)
        
        return product_details

    async def check_admin_permission(self, admin_id: int) -> bool:
        """
        检查用户是否具有管理员权限
        
        Args:
            admin_id: 用户ID
        
        Returns:
            True表示具有管理员权限，False表示没有
        
        Note:
            实际实现中需要根据业务逻辑验证用户权限
        """
        # 这里需要实现具体的管理员权限检查逻辑
        # 示例中假设用户ID为1的是管理员
        return admin_id == 1
    
async def batch_activate_products(self, product_ids: List[int], admin_id: int) -> None:
    """
    批量激活商品
    
    Args:
        product_ids: 商品ID列表
        admin_id: 管理员ID
    """
    await self.product_dal.batch_activate_products(product_ids, admin_id)

async def batch_reject_products(self, product_ids: List[int], admin_id: int) -> None:
    """
    批量拒绝商品
    
    Args:
        product_ids: 商品ID列表
        admin_id: 管理员ID
    """
    await self.product_dal.batch_reject_products(product_ids, admin_id)