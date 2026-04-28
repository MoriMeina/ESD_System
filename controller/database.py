"""
ASDP Controller 数据库连接管理
"""
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import redis.asyncio as aioredis
from clickhouse_connect import get_client as get_ch_client

from controller.config import (
    DATABASE_URL,
    REDIS_URL,
    CLICKHOUSE_HOST,
    CLICKHOUSE_PORT,
    CLICKHOUSE_DB,
    CLICKHOUSE_USER,
    CLICKHOUSE_PASSWORD,
)

# ============================================================
# PostgreSQL 连接池
# ============================================================
_pg_pool: Optional[asyncpg.Pool] = None


async def get_pg_pool() -> asyncpg.Pool:
    """获取PostgreSQL连接池（单例）"""
    global _pg_pool
    if _pg_pool is None or _pg_pool.is_closed():
        _pg_pool = await asyncpg.create_pool(
            databasetimeout=10,
            min_size=5,
            max_size=20,
        )
    return _pg_pool


async def close_pg_pool():
    """关闭PostgreSQL连接池"""
    global _pg_pool
    if _pg_pool and not _pg_pool.is_closed():
        await _pg_pool.close()


@asynccontextmanager
async def pg_transaction():
    """PostgreSQL事务上下文管理器"""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        tx = await conn.transaction()
        await tx.start()
        try:
            yield conn
            await tx.commit()
        except Exception:
            await tx.rollback()
            raise


@asynccontextmanager
async def pg_connection():
    """PostgreSQL连接上下文管理器"""
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        yield conn

# ============================================================
# Redis 连接
# ============================================================
_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """获取Redis客户端（单例）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
    return _redis_client


async def close_redis():
    """关闭Redis连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()

# ============================================================
# ClickHouse 连接
# ============================================================
_ch_client = None


def get_clickhouse():
    """获取ClickHouse客户端（单例）"""
    global _ch_client
    if _ch_client is None:
        _ch_client = get_ch_client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DB,
            username=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
        )
    return _ch_client


def close_clickhouse():
    """关闭ClickHouse连接"""
    global _ch_client
    if _ch_client:
        _ch_client.close()


# ============================================================
# 生命周期管理
# ============================================================
async def init_databases():
    """初始化所有数据库连接"""
    await get_pg_pool()
    await get_redis()
    get_clickhouse()


async def close_databases():
    """关闭所有数据库连接"""
    await close_pg_pool()
    await close_redis()
    close_clickhouse()