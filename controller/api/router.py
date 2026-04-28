"""
ASDP - API 路由汇总
"""
from fastapi import APIRouter

from controller.api import agents, tasks, results, graph, export

# 创建主路由器
api_router = APIRouter(prefix="/api/v1")

# 注册子路由器
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(results.router, prefix="/results", tags=["results"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(export.router, prefix="/export", tags=["export"])

__all__ = ["api_router"]