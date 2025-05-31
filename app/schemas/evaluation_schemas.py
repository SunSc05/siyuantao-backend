from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class EvaluationCreateSchema(BaseModel):
    """
    评价创建Schema
    对应存储过程：[dbo].[CreateEvaluation]
    """
    order_id: UUID = Field(..., description="订单ID")
    rating: int = Field(..., ge=1, le=5, description="评分 (1-5)")
    comment: Optional[str] = Field(None, max_length=500, description="评价内容")

    class Config:
        from_attributes = True

class EvaluationResponseSchema(BaseModel):
    """
    评价响应Schema
    用于返回评价的完整信息
    """
    evaluation_id: UUID = Field(..., description="评价ID")
    order_id: UUID = Field(..., description="订单ID")
    product_id: UUID = Field(..., description="商品ID")
    buyer_id: UUID = Field(..., description="评价发起人ID，即买家ID")
    seller_id: UUID = Field(..., description="评价对象ID，即卖家ID")
    rating: int = Field(..., description="评分")
    comment: Optional[str] = Field(None, description="评价内容")
    created_at: datetime = Field(..., description="评价创建时间")

    class Config:
        from_attributes = True