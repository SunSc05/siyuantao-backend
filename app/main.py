# app/main.py
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.exceptions import (
    NotFoundError, IntegrityError, DALError,
    not_found_exception_handler, integrity_exception_handler, dal_exception_handler
)
# 导入所有模块路由
from app.routers import users, products, orders # 这些文件后面会创建

app = FastAPI(
    title="校园二手交易平台 API",
    description="基于 FastAPI 和原生 SQL 构建的后端 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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
        content={"message": exc.detail},
        headers=exc.headers
    )


# 注册路由模块
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Products"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"])
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