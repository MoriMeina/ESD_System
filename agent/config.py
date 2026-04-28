"""
ASDP Agent 配置
"""
import os

# ============================================================
# Agent 身份
# ============================================================
AGENT_ID: str = os.getenv("AGENT_ID", "")
AGENT_TOKEN: str = os.getenv("AGENT_TOKEN", "")
AGENT_NAME: str = os.getenv("AGENT_NAME", "default-agent")

# ============================================================
# Controller 地址
# ============================================================
CONTROLLER_URL: str = os.getenv("CONTROLLER_URL", "http://localhost:8000")

# ============================================================
# 扫描配置
# ============================================================
# TCP 扫描
TCP_TIMEOUT_MS: int = int(os.getenv("TCP_TIMEOUT_MS", "3000"))
TCP_MAX_CONCURRENCY: int = int(os.getenv("TCP_MAX_CONCURRENCY", "50"))
TCP_SCAN_TYPE: str = os.getenv("TCP_SCAN_TYPE", "connect")  # connect/syn

# UDP 扫描
UDP_TIMEOUT_MS: int = int(os.getenv("UDP_TIMEOUT_MS", "5000"))
UDP_MAX_RETRIES: int = int(os.getenv("UDP_MAX_RETRIES", "5"))
UDP_RETRY_DELAY_MS: int = int(os.getenv("UDP_RETRY_DELAY_MS", "1000"))
UDP_MAX_CONCURRENCY: int = int(os.getenv("UDP_MAX_CONCURRENCY", "20"))

# 通用
RATE_LIMIT: int = int(os.getenv("RATE_LIMIT", "1000"))  # 每秒最大探测数
BANNER_READ_TIMEOUT_MS: int = int(os.getenv("BANNER_READ_TIMEOUT_MS", "2000"))
BANNER_MAX_BYTES: int = int(os.getenv("BANNER_MAX_BYTES", "1024"))

# ============================================================
# 心跳配置
# ============================================================
HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # 秒

# ============================================================
# 任务拉取配置
# ============================================================
POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "2.0"))  # 秒

# ============================================================
# 结果上报配置
# ============================================================
REPORT_BATCH_SIZE: int = int(os.getenv("REPORT_BATCH_SIZE", "100"))
REPORT_INTERVAL: float = float(os.getenv("REPORT_INTERVAL", "5.0"))  # 秒

# ============================================================
# 日志
# ============================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"