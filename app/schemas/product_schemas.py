from uuid import UUID
from pydantic import BaseModel, Field

class ProductResponseSchema(BaseModel):
    """
    Schema for returning product details.
    Based on Product table fields.
    """
    product_id: UUID = Field(..., description="Unique ID of the product")
    name: str = Field(..., max_length=255, description="Name of the product")
    description: str = Field(None, description="Description of the product")
    price: float = Field(..., gt=0, description="Price of the product")
    # 添加其他您需要的字段，例如 seller_id, create_time 等

    class Config:
        orm_mode = True