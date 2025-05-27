import uuid
from typing import List
from sqlalchemy.orm import Session
from app.dal.connection import get_db_connection  # 假设 connection.py 中有获取数据库连接的函数
from app.schemas.product import Product, ProductImage

def create_product(db: Session, product: Product):
    product.product_id = str(uuid.uuid4())
    db.add(product)
    for img in product.images:
        img.image_id = str(uuid.uuid4())
        img.product_id = product.product_id
        db.add(img)
    db.commit()
    db.refresh(product)
    return product

def get_user_products(db: Session, owner_id: str):
    return db.query(Product).filter(Product.owner_id == owner_id).all()

def update_product_status(db: Session, product_id: str, status: str):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if product:
        product.status = status
        db.commit()
        db.refresh(product)
    return product