from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ProductImage(BaseModel):
    image_url: str
    upload_time: datetime = Field(default_factory=datetime.now)
    sort_order: int = 0

class ProductBase(BaseModel):
    category_name: Optional[str]
    product_name: str
    description: Optional[str]
    quantity: int
    price: float
    status: str = "PendingReview"

class ProductCreate(ProductBase):
    owner_id: str
    images: List[ProductImage]

class Product(ProductBase):
    product_id: str
    owner_id: str
    post_time: datetime = Field(default_factory=datetime.now)
    images: List[ProductImage]

    class Config:
        orm_mode = True