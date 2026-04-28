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
async def get_agent(agent_id: UUID):
    """获取Agent详情"""
    agent = await AgentStorage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(**agent)


@router.post("/{agent_id}/disable")
async def disable_agent(agent_id: UUID):
    """禁用Agent"""
    agent = await AgentStorage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await AgentStorage.update_status(agent_id, "disabled")
    return {"message": "Agent disabled", "agent_id": str(agent_id)}


@router.post("/{agent_id}/enable")
async def enable_agent(agent_id: UUID):
    """启用Agent"""
    agent = await AgentStorage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await AgentStorage.update_status(agent_id, "offline")  # 先设为offline，等心跳后变online
    return {"message": "Agent enabled", "agent_id": str(agent_id)}


# ============================================================
# Agent 心跳
# ============================================================

@router.post("/{agent_id}/heartbeat")
async def heartbeat(
    agent_id: UUID,
    request: AgentHeartbeatRequest,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    """
    Agent心跳上报
    
    必须通过 X-Agent-Token 请求头认证
    """
    # 验证Token
    agent = await AgentStorage.get_agent_by_token(x_agent_token)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    if str(agent["id"]) != str(agent_id):
        raise HTTPException(status_code=403, detail="Token does not match agent")
    
    # 更新心跳（Redis + PostgreSQL）
    await QueueService.update_heartbeat(agent_id, request.source_ip)
    await AgentStorage.update_heartbeat(agent_id, request.source_ip)
    
    return {
        "status": "ok",
        "agent_id": str(agent_id),
    }


# ============================================================
# Agent 队列状态
# ============================================================

@router.get("/{agent_id}/queue")
async def get_agent_queue(agent_id: UUID):
    """获取Agent队列状态"""
    agent = await AgentStorage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    queue_length = await QueueService.get_queue_length(agent_id)
    is_online = await QueueService.is_agent_online(agent_id)
    
    return {
        "agent_id": str(agent_id),
        "agent_name": agent["name"],
        "status": agent["status"],
        "is_online": is_online,
        "queue_length": queue_length,
    }