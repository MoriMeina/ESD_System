"""
ASDP - 扫描任务管理 API
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from controller.models.schemas import (
    ScanTaskCreate, ScanTaskResponse, ScanResultBatch, ScanResultItem,
    parse_port_range,
)
from controller.services.storage_service import (
    TaskStorage, AgentStorage, ScanResultStorage, IPAssetStorage,
)
from controller.services.queue_service import QueueService

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# 任务创建
# ============================================================

@router.post("/", response_model=ScanTaskResponse, status_code=201)
async def create_task(task: ScanTaskCreate, background_tasks: BackgroundTasks):
    """
    创建扫描任务
    
    - **target_ips**: 目标IP列表
    - **port_range**: 端口范围 (如 "1-1000" 或 "22,80,443")
    - **protocol**: tcp/udp/both
    - **agent_ids**: 指定Agent，为空则自动分配在线Agent
    """
    # 创建任务记录
    task_record = await TaskStorage.create_task(
        name=task.name,
        target_ips=task.target_ips,
        port_range=task.port_range,
        protocol=task.protocol.value,
        scan_type=task.scan_type,
        timeout_ms=task.timeout_ms,
        max_retries=task.max_retries,
        description=task.description,
    )
    task_id = task_record["id"]

    # 确定Agent
    if task.agent_ids:
        agent_ids = task.agent_ids
    else:
        # 自动分配: 获取所有在线Agent
        online_agents = await QueueService.get_online_agents()
        if not online_agents:
            await TaskStorage.update_task_status(task_id, "failed")
            raise HTTPException(
                status_code=400,
                detail="No online agents available. Please create and start an agent first."
            )
        agent_ids = [UUID(a["id"]) for a in online_agents]

    # 计算每个Agent的工作量
    ports = parse_port_range(task.port_range)
    
    # 分发任务到Agent
    for agent_id in agent_ids:
        # 验证Agent存在且未禁用
        agent = await AgentStorage.get_agent(agent_id)
        if not agent or agent["status"] == "disabled":
            continue
        
        # 创建任务分配
        total_scans = len(ports) * len(task.target_ips)
        await TaskStorage.create_assignment(task_id, agent_id, total_scans)
        
        # 构建子任务数据
        sub_task = {
            "task_id": str(task_id),
            "agent_id": str(agent_id),
            "target_ips": task.target_ips,
            "ports": ports,
            "protocol": task.protocol.value,
            "scan_type": task.scan_type,
            "timeout_ms": task.timeout_ms,
            "max_retries": task.max_retries,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # 推送到Agent队列
        await QueueService.push_task(agent_id, sub_task)
        logger.info(f"Sub-task pushed to agent {agent['name']} for task {task_id}")

    # 更新任务状态为running
    await TaskStorage.update_task_status(task_id, "running", progress=0)
    await QueueService.update_task_status(task_id, "running", 0)
    
    # 推送初始进度事件
    await QueueService.publish_task_progress(task_id, 0, "Task created and distributed")

    logger.info(f"Task created: {task.name} (id={task_id}) with {len(agent_ids)} agents")
    return ScanTaskResponse(**task_record)


@router.get("/", response_model=List[ScanTaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出扫描任务"""
    tasks = await TaskStorage.list_tasks(status=status, limit=limit, offset=offset)
    return [ScanTaskResponse(**t) for t in tasks]


@router.get("/{task_id}", response_model=ScanTaskResponse)
async def get_task(task_id: UUID):
    """获取任务详情"""
    task = await TaskStorage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 附加分配信息
    assignments = await TaskStorage.get_task_assignments(task_id)
    
    result = ScanTaskResponse(**task)
    # 将assignments附加到响应中
    return {
        **result.dict(),
        "assignments": assignments,
    }


@router.delete("/{task_id}")
async def delete_task(task_id: UUID):
    """删除任务（软删除：标记为cancelled）"""
    task = await TaskStorage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] in ("running", "pending"):
        await TaskStorage.update_task_status(task_id, "cancelled")
    
    return {"message": "Task deleted", "task_id": str(task_id)}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: UUID):
    """取消运行中的任务"""
    task = await TaskStorage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task["status"] not in ("running", "pending"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {task['status']}")
    
    await TaskStorage.update_task_status(task_id, "cancelled")
    await QueueService.update_task_status(task_id, "cancelled", task["progress"])
    await QueueService.publish_task_progress(task_id, task["progress"], "Task cancelled")
    
    return {"message": "Task cancelled", "task_id": str(task_id)}


# ============================================================
# 任务进度
# ============================================================

@router.get("/{task_id}/progress")
async def get_task_progress(task_id: UUID):
    """获取任务进度（含各Agent进度）"""
    task = await TaskStorage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    assignments = await TaskStorage.get_task_assignments(task_id)
    
    # 计算总体进度
    total_scans = sum(a["total_scans"] for a in assignments)
    completed_scans = sum(a["completed_scans"] for a in assignments)
    progress = int((completed_scans / total_scans * 100)) if total_scans > 0 else 0
    
    return {
        "task_id": str(task_id),
        "task_name": task["name"],
        "status": task["status"],
        "progress": progress,
        "total_scans": total_scans,
        "completed_scans": completed_scans,
        "agents": [
            {
                "agent_id": str(a["agent_id"]),
                "agent_name": a["agent_name"],
                "status": a["status"],
                "progress": a["progress"],
                "total_scans": a["total_scans"],
                "completed_scans": a["completed_scans"],
            }
            for a in assignments
        ],
    }


# ============================================================
# 结果上报 (Agent调用)
# ============================================================

@router.post("/results/report")
async def report_results(
    batch: ScanResultBatch,
    x_agent_token: str,
):
    """
    Agent上报扫描结果
    
    必须通过 X-Agent-Token 请求头认证
    """
    # 验证Token
    agent = await AgentStorage.get_agent_by_token(x_agent_token)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    agent_id = agent["id"]
    task_id = batch.task_id
    
    # 验证权限
    if str(agent_id) != str(batch.agent_id):
        raise HTTPException(status_code=403, detail="Token does not match agent_id in payload")
    
    results = batch.results
    
    # 批量写入ClickHouse
    results_data = [r.dict() for r in results]
    inserted = await ScanResultStorage.batch_insert(results_data)
    
    # 更新IP资产（自动发现）
    target_ips = set()
    for r in results:
        target_ips.add(r.target_ip)
        # 也记录source_ip作为资产
        target_ips.add(r.source_ip)
    
    for ip in target_ips:
        await IPAssetStorage.upsert_ip(ip, discovered_by=agent_id)
    
    # 更新任务分配进度
    completed_count = len(results)
    await TaskStorage.update_assignment(
        task_id, agent_id,
        status="running",
        completed_scans=completed_count,
    )
    
    # 检查是否全部完成
    assignment = await TaskStorage.get_task_assignments(task_id)
    total_expected = 0
    total_completed = 0
    for a in assignment:
        total_expected += a["total_scans"]
        total_completed += a["completed_scans"]
    
    if total_expected > 0 and total_completed >= total_expected:
        # 所有Agent完成
        progress = 100
        open_count = sum(1 for r in results if r.status == "open")
        await TaskStorage.update_task_status(
            task_id, "completed", progress=progress,
            scanned_ports=total_completed, open_ports=open_count,
        )
        await QueueService.publish_task_progress(task_id, 100, "Task completed")
    
    return {
        "status": "ok",
        "received": len(results),
        "inserted": inserted,
    }


# ============================================================
# Agent 拉取任务
# ============================================================

@router.get("/pull/{agent_id}")
async def pull_task(
    agent_id: UUID,
    x_agent_token: str,
):
    """
    Agent拉取下一个任务
    
    必须通过 X-Agent-Token 请求头认证
    """
    # 验证Token
    agent = await AgentStorage.get_agent_by_token(x_agent_token)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    if str(agent["id"]) != str(agent_id):
        raise HTTPException(status_code=403, detail="Token does not match agent")
    
    # 从队列弹出任务
    task_data = await QueueService.pop_task(agent_id)
    
    if task_data:
        # 标记分配为running
        task_uuid = UUID(task_data["task_id"])
        await TaskStorage.update_assignment(task_uuid, agent_id, "running")
    
    return {
        "has_task": task_data is not None,
        "task": task_data,
    }