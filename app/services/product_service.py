from typing import List
from app.schemas.product import ProductCreate, Product
from app.dal.product_dal import create_product, get_user_products, update_product_status
from app.dal.connection import get_db_connection

def create_product_service(product: ProductCreate):
    with get_db_connection() as db:
        return create_product(db, product)

def get_user_products_service(owner_id: str):
    with get_db_connection() as db:
        return get_user_products(db, owner_id)

def withdraw_product_service(product_id: str):
    with get_db_connection() as db:
        return update_product_status(db, product_id, "Withdrawn")