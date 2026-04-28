"""
ASDP Controller - 主应用入口
分布式暴露面检测平台中心控制端
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from controller.config import (
    APP_NAME, APP_VERSION, HOST, PORT,
    CORS_ORIGINS, LOG_LEVEL, LOG_FORMAT, DEBUG,
)
from controller.database import init_databases, close_databases
from controller.api.router import api_router

# 配置日志
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"{APP_NAME} v{APP_VERSION} starting...")
    await init_databases()
    logger.info("Database connections initialized")
    yield
    logger.info("Shutting down...")
    await close_databases()
    logger.info("Database connections closed")


# 创建 FastAPI 应用
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="分布式暴露面检测平台 - 中心控制端",
    lifespan=lifespan,
    debug=DEBUG,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(api_router)

# 静态文件（前端构建产物）
import os
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """根路径 - 健康检查"""
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "name": APP_NAME,
        "version": APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "controller.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level=LOG_LEVEL.lower(),
    )