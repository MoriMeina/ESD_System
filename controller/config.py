"""
ASDP Controller 配置管理
"""
import os
from typing import Optional

# ============================================================
# 应用配置
# ============================================================
APP_NAME: str = "ASDP Controller"
APP_VERSION: str = "1.0.0"
DEBUG: bool = os.getenv("ASDP_DEBUG", "false").lower() == "true"
SECRET_KEY: str = os.getenv("ASDP_SECRET_KEY", "change-me-in-production")

# ============================================================
# 服务器配置
# ============================================================
HOST: str = os.getenv("ASDP_HOST", "0.0.0.0")
PORT: int = int(os.getenv("ASDP_PORT", "8000"))
WORKERS: int = int(os.getenv("ASDP_WORKERS", "4"))

# ============================================================
# PostgreSQL 配置
# ============================================================
POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "asdp")
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "asdp")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "asdp")

DATABASE_URL: str = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# ============================================================
# ClickHouse 配置
# ============================================================
CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB: str = os.getenv("CLICKHOUSE_DB", "asdp")
CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "")

# ============================================================
# Redis 配置
# ============================================================
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD") or None

REDIS_URL: str = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# ============================================================
# 队列配置
# ============================================================
TASK_QUEUE_PREFIX: str = "asdp:task_queue"
RESULT_QUEUE_KEY: str = "asdp:result_queue"

# ============================================================
# Agent 配置
# ============================================================
AGENT_HEARTBEAT_TIMEOUT: int = 60  # 心跳超时(秒)
AGENT_TOKEN_EXPIRY: int = 3600  # Token有效期(秒)

# ============================================================
# 扫描默认配置
# ============================================================
DEFAULT_SCAN_TIMEOUT_MS: int = 3000
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_UDP_RETRIES: int = 5  # UDP需要更多重试
DEFAULT_MAX_CONCURRENCY: int = 50
DEFAULT_RATE_LIMIT: int = 1000

# ============================================================
# JWT 配置
# ============================================================
JWT_SECRET: str = os.getenv("JWT_SECRET", SECRET_KEY)
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_MINUTES: int = 60

# ============================================================
# CORS 配置
# ============================================================
CORS_ORIGINS: list = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]

# ============================================================
# 日志配置
# ============================================================
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"