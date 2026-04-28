"""
ASDP Agent - 主入口
分布式扫描节点

功能：
1. 心跳机制（定时上报存活状态）
2. 任务拉取（从Controller获取扫描任务）
3. 任务执行（TCP/UDP扫描）
4. 结果上报（批量提交扫描结果）
"""
import asyncio
import logging
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

import httpx

from agent import config
from agent.scanner import (
    TCPScanner, UDPScanner, ScanTarget, ScanResult, scan_batch,
)

logger = logging.getLogger(__name__)


class Agent:
    """ASDP 分布式扫描Agent"""

    def __init__(self):
        self.agent_id = config.AGENT_ID
        self.agent_token = config.AGENT_TOKEN
        self.controller_url = config.CONTROLLER_URL.rstrip("/")
        
        # 验证必需配置
        if not self.agent_id or not self.agent_token:
            logger.error("AGENT_ID and AGENT_TOKEN must be set")
            sys.exit(1)
        
        # 扫描器
        self.tcp_scanner = TCPScanner()
        self.udp_scanner = UDPScanner()
        
        # 运行状态
        self._running = False
        self._source_ip = None
        
        # 结果缓冲
        self._result_buffer: List[Dict[str, Any]] = []
        self._current_task_id = None

    async def get_source_ip(self) -> str:
        """获取本机出口IP"""
        if self._source_ip:
            return self._source_ip
        
        try:
            # 通过连接外网获取出口IP
            reader, writer = await asyncio.open_connection("1.1.1.1", 53)
            local_addr = writer.get_extra_info('sockname')[0]
            writer.close()
            await writer.wait_closed()
            self._source_ip = local_addr
            logger.info(f"Source IP detected: {self._source_ip}")
        except Exception:
            #  fallback: 获取本机IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self._source_ip = s.getsockname()[0]
                s.close()
            except Exception:
                self._source_ip = "127.0.0.1"
        
        return self._source_ip

    async def heartbeat_loop(self):
        """心跳循环"""
        logger.info("Heartbeat loop started")
        
        while self._running:
            try:
                source_ip = await self.get_source_ip()
                
                url = f"{self.controller_url}/api/v1/agents/{self.agent_id}/heartbeat"
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        url,
                        json={
                            "source_ip": source_ip,
                            "stats": {
                                "buffer_size": len(self._result_buffer),
                                "uptime": time.time(),
                            }
                        },
                        headers={"X-Agent-Token": self.agent_token},
                    )
                
                if response.status_code == 200:
                    logger.debug("Heartbeat sent successfully")
                else:
                    logger.warning(f"Heartbeat failed: {response.status_code}")
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            await asyncio.sleep(config.HEARTBEAT_INTERVAL)

    async def poll_and_execute(self):
        """任务拉取与执行循环"""
        logger.info("Task poll loop started")
        
        while self._running:
            try:
                # 拉取任务
                task_data = await self.pull_task()
                
                if task_data:
                    self._current_task_id = task_data.get("task_id")
                    logger.info(
                        f"Received task: {self._current_task_id}, "
                        f"targets={len(task_data.get('target_ips', []))}, "
                        f"ports={len(task_data.get('ports', []))}"
                    )
                    
                    # 执行任务
                    await self.execute_task(task_data)
                    
                    # 上报剩余结果
                    await self.report_results()
                    
                    self._current_task_id = None
                else:
                    # 没有任务，上报缓冲的结果后等待
                    if self._result_buffer:
                        await self.report_results()
                    await asyncio.sleep(config.POLL_INTERVAL)
                    
            except Exception as e:
                logger.error(f"Task poll error: {e}")
                await asyncio.sleep(config.POLL_INTERVAL * 2)

    async def pull_task(self) -> Dict[str, Any]:
        """从Controller拉取任务"""
        url = f"{self.controller_url}/api/v1/tasks/pull/{self.agent_id}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"X-Agent-Token": self.agent_token},
            )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("has_task"):
                return data.get("task")
        else:
            logger.warning(f"Pull task failed: {response.status_code}")
        
        return None

    async def execute_task(self, task_data: Dict[str, Any]):
        """执行扫描任务"""
        task_id = task_data["task_id"]
        target_ips = task_data["target_ips"]
        ports = task_data["ports"]
        protocol = task_data["protocol"]
        timeout_ms = task_data.get("timeout_ms", config.TCP_TIMEOUT_MS)
        max_retries = task_data.get("max_retries", config.UDP_MAX_RETRIES)
        
        # 构建扫描目标列表
        targets = []
        for ip in target_ips:
            for port in ports:
                # 根据协议筛选
                if protocol in ("tcp", "both"):
                    targets.append(ScanTarget(ip=ip, port=port, protocol="tcp"))
                if protocol in ("udp", "both"):
                    targets.append(ScanTarget(ip=ip, port=port, protocol="udp"))
        
        total = len(targets)
        logger.info(f"Scanning {total} targets for task {task_id}")
        
        # 分批扫描
        batch_size = 100
        completed = 0
        
        for i in range(0, total, batch_size):
            if not self._running:
                break
            
            batch = targets[i:i + batch_size]
            results = await scan_batch(batch, self.tcp_scanner, self.udp_scanner)
            
            # 处理结果
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Scan error: {result}")
                    continue
                
                if isinstance(result, ScanResult):
                    result_data = {
                        "task_id": task_id,
                        "agent_id": self.agent_id,
                        "source_ip": await self.get_source_ip(),
                        "target_ip": result.target_ip,
                        "port": result.port,
                        "protocol": result.protocol,
                        "status": result.status,
                        "latency_ms": result.latency_ms,
                        "banner": result.banner,
                        "error_message": result.error_message,
                        "retry_count": result.retry_count,
                        "scanned_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self._result_buffer.append(result_data)
                
                completed += 1
            
            # 批量上报
            if len(self._result_buffer) >= config.REPORT_BATCH_SIZE:
                await self.report_results()
            
            # 日志
            if completed % 500 == 0 or completed == total:
                logger.info(f"Task {task_id}: {completed}/{total} completed")
        
        logger.info(f"Task {task_id} finished: {completed}/{total}")

    async def report_results(self):
        """批量上报扫描结果"""
        if not self._result_buffer:
            return
        
        batch = self._result_buffer[:config.REPORT_BATCH_SIZE]
        self._result_buffer = self._result_buffer[config.REPORT_BATCH_SIZE:]
        
        url = f"{self.controller_url}/api/v1/tasks/results/report"
        
        payload = {
            "agent_id": self.agent_id,
            "task_id": batch[0]["task_id"] if batch else "",
            "results": batch,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"X-Agent-Token": self.agent_token},
                )
            
            if response.status_code == 200:
                logger.info(f"Reported {len(batch)} results")
            else:
                logger.error(f"Report failed: {response.status_code} {response.text}")
                # 失败时把结果放回缓冲区
                self._result_buffer = batch + self._result_buffer
                
        except Exception as e:
            logger.error(f"Report error: {e}")
            self._result_buffer = batch + self._result_buffer

    async def start(self):
        """启动Agent"""
        self._running = True
        
        logger.info(f"ASDP Agent starting (id={self.agent_id})")
        
        # 注册信号处理
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        
        # 启动协程
        tasks = [
            asyncio.create_task(self.heartbeat_loop()),
            asyncio.create_task(self.poll_and_execute()),
        ]
        
        # 等待所有任务完成
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """停止Agent"""
        logger.info("Stopping Agent...")
        self._running = False
        
        # 上报剩余结果
        while self._result_buffer:
            await self.report_results()
        
        logger.info("Agent stopped")
        sys.exit(0)


def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT,
    )
    
    agent = Agent()
    
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        asyncio.run(agent.stop())


if __name__ == "__main__":
    main()