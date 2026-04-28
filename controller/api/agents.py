"""
ASDP - Agent 管理 API
"""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import JSONResponse

from controller.models.schemas import (
    AgentCreate, AgentResponse, AgentHeartbeatRequest,
)
from controller.services.storage_service import AgentStorage
from controller.services.queue_service import QueueService

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# 辅助函数
# ============================================================

async def resolve_agent_id(agent_id: str) -> dict:
    """
    解析 agent_id，支持 UUID 和字符串格式。
    先尝试按 UUID 匹配 id 字段，再尝试按名称匹配 name 字段。
    """
    # 尝试按 UUID 查找
    try:
        uuid_id = UUID(agent_id)
        agent = await AgentStorage.get_agent(uuid_id)
        if agent:
            return agent
    except (ValueError, AttributeError):
        pass

    # 尝试按名称查找
    async with pg_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM agents WHERE name = $1",
            agent_id,
        )
        if row:
            return dict(row)

    raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")


# 导入 pg_connection
from controller.database import pg_connection


# ============================================================
# Agent CRUD
# ============================================================

@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(agent: AgentCreate):
    """
    创建新的扫描Agent
    
    - **name**: Agent名称（唯一）
    - **network_zone**: 网络区域标识
    - **max_concurrency**: 最大并发数
    - **rate_limit**: 每秒最大扫描数
    """
    try:
        result = await AgentStorage.create_agent(
            name=agent.name,
            description=agent.description,
            network_zone=agent.network_zone,
            max_concurrency=agent.max_concurrency,
            rate_limit=agent.rate_limit,
        )
        logger.info(f"Agent created: {agent.name} (id={result['id']})")
        return AgentResponse(**result)
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[AgentResponse])
async def list_agents(status: Optional[str] = None):
    """列出所有Agent，可按状态过滤"""
    agents = await AgentStorage.list_agents(status=status)
    return [AgentResponse(**a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """获取Agent详情（支持 UUID 或名称）"""
    agent = await resolve_agent_id(agent_id)
    return AgentResponse(**agent)


@router.post("/{agent_id}/disable")
async def disable_agent(agent_id: str):
    """禁用Agent（支持 UUID 或名称）"""
    agent = await resolve_agent_id(agent_id)
    await AgentStorage.update_status(agent["id"], "disabled")
    return {"message": "Agent disabled", "agent_id": str(agent["id"])}


@router.post("/{agent_id}/enable")
async def enable_agent(agent_id: str):
    """启用Agent（支持 UUID 或名称）"""
    agent = await resolve_agent_id(agent_id)
    await AgentStorage.update_status(agent["id"], "offline")  # 先设为offline，等心跳后变online
    return {"message": "Agent enabled", "agent_id": str(agent["id"])}


# ============================================================
# Agent 心跳
# ============================================================

@router.post("/{agent_id}/heartbeat")
async def heartbeat(
    agent_id: str,
    request: AgentHeartbeatRequest,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    """
    Agent心跳上报（支持 UUID 或名称）
    
    必须通过 X-Agent-Token 请求头认证
    """
    # 验证Token
    agent = await AgentStorage.get_agent_by_token(x_agent_token)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    # 支持 UUID 和名称两种方式匹配
    resolved = await resolve_agent_id(agent_id)
    if str(resolved["id"]) != str(agent["id"]):
        raise HTTPException(status_code=403, detail="Token does not match agent")
    
    # 更新心跳（Redis + PostgreSQL）
    await QueueService.update_heartbeat(agent["id"], request.source_ip)
    await AgentStorage.update_heartbeat(agent["id"], request.source_ip)
    
    return {
        "status": "ok",
        "agent_id": str(agent["id"]),
    }


# ============================================================
# Agent 队列状态
# ============================================================

@router.get("/{agent_id}/queue")
async def get_agent_queue(agent_id: str):
    """获取Agent队列状态（支持 UUID 或名称）"""
    agent = await resolve_agent_id(agent_id)
    
    queue_length = await QueueService.get_queue_length(agent["id"])
    is_online = await QueueService.is_agent_online(agent["id"])
    
    return {
        "agent_id": str(agent["id"]),
        "agent_name": agent["name"],
        "status": agent["status"],
        "is_online": is_online,
        "queue_length": queue_length,
    }
