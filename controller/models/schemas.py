"""
ASDP Controller - Pydantic 数据模型
用于 API 请求/响应验证
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

from pydantic import BaseModel, Field, validator


# ============================================================
# 枚举定义
# ============================================================
class ProtocolType(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    BOTH = "both"


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PortStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    FILTERED = "filtered"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DISABLED = "disabled"


class IPType(str, Enum):
    PRIVATE_A = "private_a"
    PRIVATE_B = "private_b"
    PRIVATE_C = "private_c"
    PUBLIC = "public"
    EIP = "eip"


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# ============================================================
# Agent 模型
# ============================================================
class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    network_zone: Optional[str] = Field(None, max_length=50)
    max_concurrency: int = Field(50, ge=1, le=500)
    rate_limit: int = Field(1000, ge=100, le=10000)


class AgentResponse(BaseModel):
    id: UUID
    name: str
    token: Optional[str] = None
    description: Optional[str]
    source_ip: Optional[str]
    network_zone: Optional[str]
    status: str
    last_heartbeat: Optional[datetime]
    max_concurrency: int
    rate_limit: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentHeartbeatRequest(BaseModel):
    source_ip: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# 扫描任务模型
# ============================================================
class ScanTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    target_ips: List[str] = Field(..., min_items=1)
    port_range: str = Field(..., description='端口范围，如 "1-10000" 或 "22,80,443"')
    protocol: ProtocolType = ProtocolType.TCP
    agent_ids: Optional[List[UUID]] = Field(
        None, description="指定Agent，为空则自动分配"
    )
    scan_type: str = Field("connect", description="connect/syn")
    timeout_ms: int = Field(3000, ge=100, le=10000)
    max_retries: int = Field(3, ge=0, le=10)

    @validator("target_ips")
    def validate_ips(cls, v):
        import ipaddress
        for ip_str in v:
            try:
                ipaddress.ip_address(ip_str)
            except ValueError:
                raise ValueError(f"Invalid IP address: {ip_str}")
        return v

    @validator("port_range")
    def validate_port_range(cls, v):
        """验证端口范围格式"""
        try:
            ports = parse_port_range(v)
            if not ports:
                raise ValueError("Empty port range")
            if len(ports) > 65535:
                raise ValueError("Too many ports (max 65535)")
            return v
        except Exception as e:
            if "Empty" in str(e) or "Too" in str(e):
                raise e
            raise ValueError(f"Invalid port range format: {v}")


class TaskAssignmentCreate(BaseModel):
    agent_id: UUID
    total_scans: int


class ScanTaskResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    target_ips: List[str]
    port_range: str
    protocol: str
    status: str
    progress: int
    scan_type: str
    timeout_ms: int
    max_retries: int
    total_ports: Optional[int]
    scanned_ports: int
    open_ports: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: Optional[str]

    class Config:
        from_attributes = True


# ============================================================
# 扫描结果模型
# ============================================================
class ScanResultItem(BaseModel):
    """单条扫描结果"""
    task_id: UUID
    agent_id: UUID
    source_ip: str       # 探测出口IP
    target_ip: str       # 目标IP
    port: int
    protocol: str
    status: str          # open/closed/filtered/unknown
    latency_ms: Optional[float]
    banner: Optional[str]
    error_message: Optional[str]
    retry_count: int = 0
    scanned_at: Optional[datetime] = None


class ScanResultBatch(BaseModel):
    """批量扫描结果上报"""
    agent_id: UUID
    task_id: UUID
    results: List[ScanResultItem] = Field(..., min_items=1)


class ScanResultQuery(BaseModel):
    """扫描结果查询条件"""
    task_id: Optional[UUID] = None
    target_ip: Optional[str] = None
    source_ip: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    status: Optional[str] = None
    agent_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(1000, ge=1, le=100000)
    offset: int = Field(0, ge=0)


# ============================================================
# IP 资产模型
# ============================================================
class IPAssetCreate(BaseModel):
    ip_address: str
    ip_type: IPType
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    @validator("ip_address")
    def validate_ip(cls, v):
        import ipaddress
        try:
            ipaddress.ip_address(v)
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")
        return v


class IPAssetResponse(BaseModel):
    id: UUID
    ip_address: str
    ip_type: str
    metadata: Dict[str, Any]
    discovered_at: datetime
    discovered_by: Optional[UUID]
    updated_at: datetime
    tags: List[str]

    class Config:
        from_attributes = True


# ============================================================
# IP 关系模型
# ============================================================
class IPRelationCreate(BaseModel):
    from_ip: str
    to_ip: str
    relation_type: str = Field(..., min_length=1, max_length=50)
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IPRelationResponse(BaseModel):
    id: UUID
    from_ip: IPAssetResponse
    to_ip: IPAssetResponse
    relation_type: str
    valid_from: datetime
    valid_to: Optional[datetime]
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class IPGraphResponse(BaseModel):
    """IP关系子图响应"""
    center_ip: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    depth: int
    total_nodes: int
    total_edges: int


# ============================================================
# 导出模型
# ============================================================
class ExportRequest(BaseModel):
    format: str = Field(..., description="csv/json")
    target_ip: Optional[str] = None
    ip_pair_from: Optional[str] = None
    ip_pair_to: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    task_id: Optional[UUID] = None


# ============================================================
# 通用响应
# ============================================================
class ApiResponse(BaseModel):
    success: bool = True
    message: str = "OK"
    data: Optional[Union[Dict[str, Any], List[Any], Any]] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============================================================
# 工具函数
# ============================================================
def parse_port_range(port_range: str) -> List[int]:
    """
    解析端口范围字符串
    支持: "1-1000", "22,80,443", "1-1000,8080,9000-9100"
    """
    ports = set()
    parts = port_range.split(",")
    for part in parts:
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.update(range(int(start), int(end) + 1))
        else:
            ports.add(int(part))
    return sorted(ports)