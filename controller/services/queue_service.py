"""
ASDP - Redis 队列服务
负责任务分发、结果收集、Agent心跳管理
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from controller.database import get_redis
from controller.config import (
    TASK_QUEUE_PREFIX,
    RESULT_QUEUE_KEY,
    AGENT_HEARTBEAT_TIMEOUT,
)

logger = logging.getLogger(__name__)


class QueueService:
    """Redis 队列服务"""

    # ============================================================
    # 任务队列操作
    # ============================================================

    @staticmethod
    async def push_task(agent_id: UUID, task_data: Dict[str, Any]) -> int:
        """
        将任务推送到指定Agent的队列
        
        Args:
            agent_id: Agent ID
            task_data: 任务数据
            
        Returns:
            队列长度
        """
        redis = await get_redis()
        queue_key = f"{TASK_QUEUE_PREFIX}:{agent_id}"
        await redis.rpush(queue_key, json.dumps(task_data, default=str))
        length = await redis.llen(queue_key)
        logger.info(f"Task pushed to agent {agent_id}, queue length: {length}")
        return length

    @staticmethod
    async def pop_task(agent_id: UUID) -> Optional[Dict[str, Any]]:
        """
        从Agent队列中弹出任务（阻塞式）
        
        Args:
            agent_id: Agent ID
            
        Returns:
            任务数据或None
        """
        redis = await get_redis()
        queue_key = f"{TASK_QUEUE_PREFIX}:{agent_id}"
        result = await redis.lpop(queue_key)
        if result:
            return json.loads(result)
        return None

    @staticmethod
    async def get_queue_length(agent_id: UUID) -> int:
        """获取Agent队列长度"""
        redis = await get_redis()
        queue_key = f"{TASK_QUEUE_PREFIX}:{agent_id}"
        return await redis.llen(queue_key)

    @staticmethod
    async def peek_queue(agent_id: UUID, start: int = 0, end: int = -1) -> List[Dict[str, Any]]:
        """查看Agent队列中的任务（不弹出）"""
        redis = await get_redis()
        queue_key = f"{TASK_QUEUE_PREFIX}:{agent_id}"
        results = await redis.lrange(queue_key, start, end)
        return [json.loads(r) for r in results]

    # ============================================================
    # 结果队列操作
    # ============================================================

    @staticmethod
    async def push_result(result_data: Dict[str, Any]) -> int:
        """
        将扫描结果推送到结果队列
        
        Args:
            result_data: 扫描结果数据
            
        Returns:
            队列长度
        """
        redis = await get_redis()
        await redis.rpush(RESULT_QUEUE_KEY, json.dumps(result_data, default=str))
        length = await redis.llen(RESULT_QUEUE_KEY)
        return length

    @staticmethod
    async def pop_result() -> Optional[Dict[str, Any]]:
        """从结果队列中弹出结果"""
        redis = await get_redis()
        result = await redis.lpop(RESULT_QUEUE_KEY)
        if result:
            return json.loads(result)
        return None

    @staticmethod
    async def pop_results_batch(batch_size: int = 100) -> List[Dict[str, Any]]:
        """批量弹出结果"""
        redis = await get_redis()
        results = []
        for _ in range(batch_size):
            result = await redis.lpop(RESULT_QUEUE_KEY)
            if result:
                results.append(json.loads(result))
            else:
                break
        return results

    # ============================================================
    # Agent 心跳管理
    # ============================================================

    @staticmethod
    async def update_heartbeat(agent_id: UUID, source_ip: Optional[str] = None) -> None:
        """
        更新Agent心跳
        
        Args:
            agent_id: Agent ID
            source_ip: Agent出口IP
        """
        redis = await get_redis()
        heartbeat_key = f"agent:heartbeat:{agent_id}"
        status_key = f"agent:status:{agent_id}"
        
        heartbeat_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_ip": source_ip,
        }
        
        # 设置心跳（60秒过期）
        await redis.setex(
            heartbeat_key,
            AGENT_HEARTBEAT_TIMEOUT,
            json.dumps(heartbeat_data)
        )
        
        # 更新状态
        await redis.hset(status_key, mapping={
            "status": "online",
            "last_update": datetime.now(timezone.utc).isoformat(),
            "source_ip": source_ip or "",
        })
        await redis.expire(status_key, AGENT_HEARTBEAT_TIMEOUT * 2)

    @staticmethod
    async def is_agent_online(agent_id: UUID) -> bool:
        """检查Agent是否在线"""
        redis = await get_redis()
        heartbeat_key = f"agent:heartbeat:{agent_id}"
        return bool(await redis.exists(heartbeat_key))

    @staticmethod
    async def get_online_agents() -> List[Dict[str, Any]]:
        """获取所有在线Agent"""
        redis = await get_redis()
        keys = await redis.keys("agent:status:*")
        agents = []
        for key in keys:
            agent_id = key.split(":")[-1]
            status = await redis.hgetall(key)
            if status.get("status") == "online":
                agents.append({
                    "id": agent_id,
                    **status
                })
        return agents

    # ============================================================
    # 任务状态缓存
    # ============================================================

    @staticmethod
    async def update_task_status(task_id: UUID, status: str, progress: int = 0) -> None:
        """更新任务状态缓存"""
        redis = await get_redis()
        key = f"task:status:{task_id}"
        await redis.hset(key, mapping={
            "status": status,
            "progress": progress,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await redis.expire(key, 3600)  # 1小时过期

    @staticmethod
    async def get_task_status(task_id: UUID) -> Optional[Dict[str, Any]]:
        """获取任务状态缓存"""
        redis = await get_redis()
        key = f"task:status:{task_id}"
        status = await redis.hgetall(key)
        return status if status else None

    # ============================================================
    # 分布式锁
    # ============================================================

    @staticmethod
    async def acquire_lock(resource: str, timeout: int = 30) -> bool:
        """
        获取分布式锁
        
        Args:
            resource: 资源标识
            timeout: 锁超时秒数
            
        Returns:
            是否获取成功
        """
        redis = await get_redis()
        lock_key = f"lock:{resource}"
        return bool(await redis.set(lock_key, "1", nx=True, ex=timeout))

    @staticmethod
    async def release_lock(resource: str) -> None:
        """释放分布式锁"""
        redis = await get_redis()
        lock_key = f"lock:{resource}"
        await redis.delete(lock_key)

    # ============================================================
    # 速率限制
    # ============================================================

    @staticmethod
    async def check_rate_limit(agent_id: UUID, limit: int, window: int = 1) -> bool:
        """
        检查Agent是否超过速率限制（滑动窗口）
        
        Args:
            agent_id: Agent ID
            limit: 窗口内最大请求数
            window: 窗口大小（秒）
            
        Returns:
            是否允许（True=未超限）
        """
        redis = await get_redis()
        rate_key = f"rate:agent:{agent_id}"
        
        # 使用滑动窗口
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - window
        
        # 移除过期条目
        await redis.zremrangebyscore(rate_key, 0, window_start)
        
        # 检查当前数量
        current = await redis.zcard(rate_key)
        if current >= limit:
            return False
        
        # 添加当前请求
        await redis.zadd(rate_key, {f"{now}": now})
        await redis.expire(rate_key, window + 1)
        
        return True

    # ============================================================
    # WebSocket 消息推送
    # ============================================================

    @staticmethod
    async def publish_event(channel: str, event: str, data: Dict[str, Any]) -> None:
        """发布WebSocket事件"""
        redis = await get_redis()
        message = {
            "event": event,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await redis.publish(channel, json.dumps(message))

    @staticmethod
    async def publish_task_progress(task_id: UUID, progress: int, message: str = "") -> None:
        """推送任务进度"""
        await QueueService.publish_event(
            f"task:events:{task_id}",
            "task_progress",
            {
                "task_id": str(task_id),
                "progress": progress,
                "message": message,
            }
        )