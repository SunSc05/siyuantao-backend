from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

# 根据 SQL Server 的 UNIQUEIDENTIFIER 类型，使用 UUID
# 根据 SQL Server 的 NVARCHAR 类型，使用 str
# 根据 SQL Server 的 INT 类型，使用 int
# 根据 SQL Server 的 DECIMAL(10, 2) 类型，使用 float 或 Decimal (这里使用 float 简化)
# 根据 SQL Server 的 DATETIME 类型，使用 datetime

class OrderCreateSchema(BaseModel):
    """
    Schema for creating a new order.
    Based on sp_CreateOrder procedure parameters and Order table fields.
    """
    product_id: UUID = Field(..., description="ID of the product being ordered")
    quantity: int = Field(..., gt=0, description="Quantity of the product")
    shipping_address: str = Field(..., max_length=255, description="Shipping address for the order")
    contact_phone: str = Field(..., max_length=20, description="Contact phone number for the order")
    total_price: float = Field(..., gt=0, description="Total price of the order") # 添加 total_price 字段

    class Config:
        orm_mode = True # 允许从 ORM 模型创建 Schema 实例

class OrderResponseSchema(BaseModel):
    """
    Schema for returning order details.
    Based on Order table fields.
    """
    order_id: UUID = Field(..., description="Unique ID of the order")
    seller_id: UUID = Field(..., description="ID of the seller")
    buyer_id: UUID = Field(..., description="ID of the buyer")
    product_id: UUID = Field(..., description="ID of the product ordered")
    quantity: int = Field(..., description="Quantity of the product")
    shipping_address: str = Field(..., max_length=255, description="Shipping address for the order")
    contact_phone: str = Field(..., max_length=20, description="Contact phone number for the order")
    total_price: float = Field(..., description="Total price of the order") # 使用 float 对应 DECIMAL(10, 2)
    status: str = Field(..., description="Current status of the order")
    created_at: datetime = Field(..., description="Timestamp when the order was created")
    updated_at: datetime = Field(..., description="Timestamp when the order was last updated")
    complete_time: Optional[datetime] = Field(None, description="Timestamp when the order was completed")
    cancel_time: Optional[datetime] = Field(None, description="Timestamp when the order was cancelled")
    cancel_reason: Optional[str] = Field(None, description="Reason for order cancellation")

    class Config:
        orm_mode = True

class OrderStatusUpdateSchema(BaseModel):
    """
    Schema for updating the status of an order.
    Based on potential status update operations (e.g., confirm, complete, cancel).
    """
    status: str = Field(..., description="New status for the order")
    # 可以根据需要添加其他字段，例如 cancel_reason
    cancel_reason: Optional[str] = Field(None, description="Reason for cancellation, required if status is 'Cancelled'")

    class Config:
        orm_mode = True