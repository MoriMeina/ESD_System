"""
ASDP Agent - 扫描引擎
包含 TCP 和 UDP 扫描器，处理UDP不可靠问题
"""
import asyncio
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from agent.config import (
    TCP_TIMEOUT_MS, UDP_TIMEOUT_MS, UDP_MAX_RETRIES,
    UDP_RETRY_DELAY_MS, TCP_MAX_CONCURRENCY, UDP_MAX_CONCURRENCY,
    BANNER_READ_TIMEOUT_MS, BANNER_MAX_BYTES,
)

logger = logging.getLogger(__name__)


@dataclass
class ScanTarget:
    """扫描目标"""
    ip: str
    port: int
    protocol: str  # tcp / udp


@dataclass
class ScanResult:
    """扫描结果"""
    target_ip: str
    port: int
    protocol: str
    status: str  # open / closed / filtered / unknown
    latency_ms: float = 0.0
    banner: str = ""
    error_message: str = ""
    retry_count: int = 0


class RateLimiter:
    """
    令牌桶速率限制器
    
    控制每秒最大扫描数，避免被防火墙限流
    """
    def __init__(self, rate: int):
        self.rate = rate
        self.tokens = rate
        self.max_tokens = rate
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class TCPScanner:
    """
    TCP 扫描器
    
    支持 CONNECT 扫描模式
    """

    def __init__(self, timeout_ms: int = TCP_TIMEOUT_MS, max_concurrency: int = TCP_MAX_CONCURRENCY):
        self.timeout = timeout_ms / 1000.0
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.rate_limiter = RateLimiter(rate=1000)

    async def scan(self, target: ScanTarget) -> ScanResult:
        """扫描单个TCP端口"""
        async with self.semaphore:
            await self.rate_limiter.acquire()
            
            start_time = time.monotonic()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(target.ip, target.port),
                    timeout=self.timeout
                )
                latency = (time.monotonic() - start_time) * 1000
                
                # 尝试读取Banner
                banner = ""
                try:
                    # 发送空请求触发banner
                    writer.write(b"\r\n")
                    await writer.drain()
                    banner_data = await asyncio.wait_for(
                        reader.read(BANNER_MAX_BYTES),
                        timeout=BANNER_READ_TIMEOUT_MS / 1000.0
                    )
                    if banner_data:
                        banner = banner_data.decode("utf-8", errors="replace").strip()[:512]
                except (asyncio.TimeoutError, OSError):
                    pass  # Banner读取失败不影响端口状态
                
                writer.close()
                try:
                    writer.wait_closed()
                except Exception:
                    pass
                
                return ScanResult(
                    target_ip=target.ip,
                    port=target.port,
                    protocol="tcp",
                    status="open",
                    latency_ms=round(latency, 2),
                    banner=banner,
                )
                
            except asyncio.TimeoutError:
                latency = (time.monotonic() - start_time) * 1000
                return ScanResult(
                    target_ip=target.ip,
                    port=target.port,
                    protocol="tcp",
                    status="filtered",  # 超时可能是被防火墙过滤
                    latency_ms=round(latency, 2),
                    error_message="timeout",
                )
            except ConnectionRefusedError:
                latency = (time.monotonic() - start_time) * 1000
                return ScanResult(
                    target_ip=target.ip,
                    port=target.port,
                    protocol="tcp",
                    status="closed",
                    latency_ms=round(latency, 2),
                )
            except OSError as e:
                latency = (time.monotonic() - start_time) * 1000
                # 网络不可达或连接被拒绝
                if "Network is unreachable" in str(e):
                    status = "filtered"
                elif "Connection refused" in str(e):
                    status = "closed"
                else:
                    status = "filtered"
                
                return ScanResult(
                    target_ip=target.ip,
                    port=target.port,
                    protocol="tcp",
                    status=status,
                    latency_ms=round(latency, 2),
                    error_message=str(e),
                )


class UDPScanner:
    """
    UDP 扫描器（弱探测）
    
    ⚠️ UDP 扫描不可靠性处理：
    
    1. 发送UDP探测包
    2. 如果收到响应 → port is OPEN
    3. 如果收到 ICMP Port Unreachable → port is CLOSED
    4. 如果没有任何响应 → 可能是 FILTERED（防火墙丢弃）或端口真的开放但不响应
    5. 使用多次重试 + 指数退避来提高可靠性
    6. UDP状态不强制二分为 open/closed，支持 filtered/unknown
    """

    # 常见UDP服务的探测响应
    UDP_PROBE_RESPONSES = {
        53: b"\x00" * 16,  # DNS
        123: b"\x1b" + b"\x00" * 47,  # NTP
        161: b"\x30\x26\x02\x01\x01\x04\x06\x70\x75\x62\x6c\x69\x63\xa0\x19\x02\x04",  # SNMP
        500: b"\x30\x4a\x02\x01\x01\x61\x45\x30\x0d\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x05\x00\xa0\x00\x30\x2d\xa0\x0b\x30\x09\x06\x05\x2b\x0e\x01\x02\x02\xa0\x00\xa2\x16\x04\x14",  # ISAKMP
    }

    def __init__(
        self,
        timeout_ms: int = UDP_TIMEOUT_MS,
        max_retries: int = UDP_MAX_RETRIES,
        max_concurrency: int = UDP_MAX_CONCURRENCY,
    ):
        self.timeout = timeout_ms / 1000.0
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.rate_limiter = RateLimiter(rate=500)  # UDP限速更严格

    def _get_probe_data(self, port: int) -> bytes:
        """获取指定端口的探测数据"""
        return self.UDP_PROBE_RESPONSES.get(port, b"\x00" * 16)

    async def _scan_once(self, target: ScanTarget) -> Dict[str, Any]:
        """
        单次UDP探测
        
        Returns:
            {"status": str, "latency_ms": float, "error": str}
        """
        start_time = time.monotonic()
        socket_fd = None
        
        try:
            socket_fd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_fd.setblocking(False)
            
            # 发送探测包
            probe_data = self._get_probe_data(target.port)
            socket_fd.sendto(probe_data, (target.ip, target.port))
            
            # 等待响应
            try:
                loop = asyncio.get_event_loop()
                data, addr = await asyncio.wait_for(
                    loop.run_in_executor(None, socket_fd.recvfrom, BANNER_MAX_BYTES),
                    timeout=self.timeout
                )
                latency = (time.monotonic() - start_time) * 1000
                
                return {
                    "status": "open",
                    "latency_ms": round(latency, 2),
                    "has_response": True,
                    "response_size": len(data),
                    "error": "",
                }
            except asyncio.TimeoutError:
                latency = (time.monotonic() - start_time) * 1000
                # 超时：可能是filtered或unknown
                # 尝试检查是否收到ICMP unreachable（通过select检测）
                return {
                    "status": "unknown",  # 首次探测超时标记为unknown
                    "latency_ms": round(latency, 2),
                    "has_response": False,
                    "error": "timeout",
                }
                
        except OSError as e:
            latency = (time.monotonic() - start_time) * 1000
            error_msg = str(e)
            
            # 判断ICMP unreachable类型
            if "Port unreachable" in error_msg or "Connection refused" in error_msg:
                return {
                    "status": "closed",
                    "latency_ms": round(latency, 2),
                    "has_response": False,
                    "error": "icmp_unreachable",
                }
            elif "Network is unreachable" in error_msg:
                return {
                    "status": "filtered",
                    "latency_ms": round(latency, 2),
                    "has_response": False,
                    "error": "network_unreachable",
                }
            else:
                return {
                    "status": "unknown",
                    "latency_ms": round(latency, 2),
                    "has_response": False,
                    "error": error_msg,
                }
        finally:
            if socket_fd:
                try:
                    socket_fd.close()
                except Exception:
                    pass

    async def scan(self, target: ScanTarget) -> ScanResult:
        """
        UDP扫描（带重试机制）
        
        重试策略：
        - 第1次: 立即
        - 第2次: 延迟 1s
        - 第3次: 延迟 2s
        - 第4次: 延迟 4s
        - 第5次: 延迟 8s
        
        状态判定逻辑：
        - 任何一次返回 open → open
        - 任何一次返回 closed (ICMP unreachable) → closed
        - 所有都超时且重试次数用尽 → filtered（防火墙可能丢弃了包）
        """
        async with self.semaphore:
            await self.rate_limiter.acquire()
            
            last_result = None
            has_closed = False
            
            for attempt in range(self.max_retries):
                if attempt > 0:
                    # 指数退避
                    delay = min(UDP_RETRY_DELAY_MS * (2 ** (attempt - 1)), 8000) / 1000.0
                    await asyncio.sleep(delay)
                
                result = await self._scan_once(target)
                last_result = result
                
                if result["status"] == "open":
                    # 确认开放，不再重试
                    return ScanResult(
                        target_ip=target.ip,
                        port=target.port,
                        protocol="udp",
                        status="open",
                        latency_ms=result["latency_ms"],
                        retry_count=attempt + 1,
                    )
                
                if result["status"] == "closed":
                    has_closed = True
            
            # 所有重试用完
            if has_closed:
                # 收到过ICMP unreachable → closed
                return ScanResult(
                    target_ip=target.ip,
                    port=target.port,
                    protocol="udp",
                    status="closed",
                    latency_ms=last_result["latency_ms"] if last_result else 0,
                    retry_count=self.max_retries,
                )
            else:
                # 从未收到任何响应 → filtered（可能是防火墙丢弃）
                # ⚠️ 不标记为unknown，因为多次重试后仍然无响应更可能是filtered
                return ScanResult(
                    target_ip=target.ip,
                    port=target.port,
                    protocol="udp",
                    status="filtered",
                    latency_ms=last_result["latency_ms"] if last_result else 0,
                    retry_count=self.max_retries,
                    error_message="no_response_after_retries",
                )


async def scan_target(
    target: ScanTarget,
    tcp_scanner: TCPScanner,
    udp_scanner: UDPScanner,
) -> ScanResult:
    """根据协议类型选择扫描器"""
    if target.protocol == "udp":
        return await udp_scanner.scan(target)
    else:
        return await tcp_scanner.scan(target)


async def scan_batch(
    targets: List[ScanTarget],
    tcp_scanner: TCPScanner,
    udp_scanner: UDPScanner,
) -> List[ScanResult]:
    """批量扫描"""
    tasks = [
        asyncio.create_task(scan_target(t, tcp_scanner, udp_scanner))
        for t in targets
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)