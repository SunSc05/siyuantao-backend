# app/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.exceptions import (
    NotFoundError, IntegrityError, DALError,
    not_found_exception_handler, integrity_exception_handler, dal_exception_handler
)
# 导入所有模块路由
from app.routers import users, auth # 暂时只导入已存在的路由
# from app.routers import products, orders # 这些文件后面会创建

app = FastAPI(
    title="校园二手交易平台 API",
    description="基于 FastAPI 和原生 SQL 构建的后端 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

import logging
logger = logging.getLogger(__name__)

logger.info(f"FastAPI app instance created with id: {id(app)}")

# 注册 CORS 中间件 (生产环境中请限制 allow_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生产环境请限制为您的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器
app.add_exception_handler(NotFoundError, not_found_exception_handler)
app.add_exception_handler(IntegrityError, integrity_exception_handler)
app.add_exception_handler(DALError, dal_exception_handler)
# 对于未捕获的 HTTPException (例如 Pydantic 验证失败)
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )


# 注册路由模块
app.include_router(users.router, prefix="/api/v1")
# app.include_router(products.router, prefix="/api/v1/products", tags=["Products"]) # 暂时注释掉未创建的路由
# app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"]) # 暂时注释掉未创建的路由
app.include_router(auth.router, prefix="/api/v1")
# ... 注册其他模块路由

@app.get("/")
async def root():
    return {"message": "Welcome to the Campus Exchange API!"}

# 您可以添加一些启动和关闭事件 (例如，初始化数据库连接池)
@app.on_event("startup")
async def startup_event():
    print("Application startup...")
    # 可以在这里做一些数据库连接池初始化等操作

@app.on_event("shutdown")
async def shutdown_event():
    print("Application shutdown...")
    # 可以在这里关闭数据库连接池等 