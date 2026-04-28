"""
ASDP - 存储服务
负责 PostgreSQL (关系数据) 和 ClickHouse (扫描结果) 的数据存取
"""
import json
import logging
import ipaddress
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from controller.database import pg_connection, get_clickhouse
from controller.config import CLICKHOUSE_DB

logger = logging.getLogger(__name__)


# ============================================================
# IP 类型判断工具
# ============================================================
def classify_ip_type(ip_str: str) -> str:
    """
    根据IP地址判断类型
    
    Returns:
        private_a / private_b / private_c / public / eip
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private:
            if ip in ipaddress.ip_network("10.0.0.0/8"):
                return "private_a"
            elif ip in ipaddress.ip_network("172.16.0.0/12"):
                return "private_b"
            elif ip in ipaddress.ip_network("192.168.0.0/16"):
                return "private_c"
        return "public"
    except ValueError:
        return "public"


# ============================================================
# Agent 数据操作
# ============================================================
class AgentStorage:
    """Agent 数据存储"""

    @staticmethod
    async def create_agent(
        name: str,
        description: Optional[str] = None,
        network_zone: Optional[str] = None,
        max_concurrency: int = 50,
        rate_limit: int = 1000,
    ) -> Dict[str, Any]:
        """创建Agent并生成Token"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO agents (name, description, network_zone, max_concurrency, rate_limit)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, name, token, description, network_zone, 
                          max_concurrency, rate_limit, created_at, updated_at
                """,
                name, description, network_zone, max_concurrency, rate_limit,
            )
            return dict(row)

    @staticmethod
    async def get_agent(agent_id: UUID) -> Optional[Dict[str, Any]]:
        """获取Agent信息"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agents WHERE id = $1",
                agent_id,
            )
            return dict(row) if row else None

    @staticmethod
    async def get_agent_by_token(token: str) -> Optional[Dict[str, Any]]:
        """通过Token获取Agent"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agents WHERE token = $1 AND status != $2",
                token, "disabled",
            )
            return dict(row) if row else None

    @staticmethod
    async def list_agents(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出Agent（不含token）"""
        async with pg_connection() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT id, name, description, source_ip, network_zone, status, "
                    "last_heartbeat, max_concurrency, rate_limit, created_at, updated_at "
                    "FROM agents WHERE status = $1 ORDER BY created_at DESC",
                    status,
                )
            else:
                rows = await conn.fetch(
                    "SELECT id, name, description, source_ip, network_zone, status, "
                    "last_heartbeat, max_concurrency, rate_limit, created_at, updated_at "
                    "FROM agents ORDER BY created_at DESC"
                )
            return [dict(r) for r in rows]

    @staticmethod
    async def update_heartbeat(agent_id: UUID, source_ip: Optional[str] = None) -> None:
        """更新Agent心跳"""
        async with pg_connection() as conn:
            await conn.execute(
                "UPDATE agents SET last_heartbeat = NOW(), status = 'online', source_ip = COALESCE($2, source_ip) "
                "WHERE id = $1",
                agent_id, source_ip,
            )

    @staticmethod
    async def update_status(agent_id: UUID, status: str) -> None:
        """更新Agent状态"""
        async with pg_connection() as conn:
            await conn.execute(
                "UPDATE agents SET status = $2, updated_at = NOW() WHERE id = $1",
                agent_id, status,
            )


# ============================================================
# 扫描任务数据操作
# ============================================================
class TaskStorage:
    """扫描任务数据存储"""

    @staticmethod
    async def create_task(
        name: str,
        target_ips: List[str],
        port_range: str,
        protocol: str,
        scan_type: str = "connect",
        timeout_ms: int = 3000,
        max_retries: int = 3,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建扫描任务"""
        async with pg_connection() as conn:
            # 计算总端口数
            from controller.models.schemas import parse_port_range
            ports = parse_port_range(port_range)
            total_ports = len(ports) * len(target_ips)

            row = await conn.fetchrow(
                """
                INSERT INTO scan_tasks (
                    name, description, target_ips, port_range, protocol,
                    scan_type, timeout_ms, max_retries, total_ports, created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
                """,
                name, description, target_ips, port_range, protocol,
                scan_type, timeout_ms, max_retries, total_ports, created_by,
            )
            return dict(row)

    @staticmethod
    async def get_task(task_id: UUID) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM scan_tasks WHERE id = $1",
                task_id,
            )
            return dict(row) if row else None

    @staticmethod
    async def list_tasks(
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出任务"""
        async with pg_connection() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM scan_tasks WHERE status = $1 "
                    "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM scan_tasks ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
            return [dict(r) for r in rows]

    @staticmethod
    async def update_task_status(
        task_id: UUID,
        status: str,
        progress: Optional[int] = None,
        scanned_ports: Optional[int] = None,
        open_ports: Optional[int] = None,
    ) -> None:
        """更新任务状态"""
        async with pg_connection() as conn:
            sets = ["status = $2"]
            params = [task_id, status]
            param_idx = 3

            if progress is not None:
                sets.append(f"progress = ${param_idx}")
                params.append(progress)
                param_idx += 1

            if scanned_ports is not None:
                sets.append(f"scanned_ports = ${param_idx}")
                params.append(scanned_ports)
                param_idx += 1

            if open_ports is not None:
                sets.append(f"open_ports = ${param_idx}")
                params.append(open_ports)
                param_idx += 1

            if status == "running" and not any("started_at" in s for s in sets):
                sets.append("started_at = COALESCE(started_at, NOW())")

            if status in ("completed", "failed"):
                sets.append("completed_at = NOW()")

            params.append(task_id)
            query = f"UPDATE scan_tasks SET {', '.join(sets)} WHERE id = ${param_idx}"
            await conn.execute(query, *params)

    @staticmethod
    async def create_assignment(
        task_id: UUID,
        agent_id: UUID,
        total_scans: int = 0,
    ) -> Dict[str, Any]:
        """创建任务分配"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO task_assignments (task_id, agent_id, total_scans)
                VALUES ($1, $2, $3)
                ON CONFLICT (task_id, agent_id) DO UPDATE SET
                    status = 'pending', assigned_at = NOW()
                RETURNING *
                """,
                task_id, agent_id, total_scans,
            )
            return dict(row)

    @staticmethod
    async def get_task_assignments(task_id: UUID) -> List[Dict[str, Any]]:
        """获取任务的所有分配"""
        async with pg_connection() as conn:
            rows = await conn.fetch(
                "SELECT ta.*, a.name as agent_name, a.status as agent_status "
                "FROM task_assignments ta "
                "JOIN agents a ON ta.agent_id = a.id "
                "WHERE ta.task_id = $1",
                task_id,
            )
            return [dict(r) for r in rows]

    @staticmethod
    async def update_assignment(
        task_id: UUID,
        agent_id: UUID,
        status: str,
        progress: Optional[int] = None,
        completed_scans: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """更新任务分配状态"""
        async with pg_connection() as conn:
            if status == "running":
                await conn.execute(
                    "UPDATE task_assignments SET status = $3, started_at = COALESCE(started_at, NOW()) "
                    "WHERE task_id = $1 AND agent_id = $2",
                    task_id, agent_id, status,
                )
            elif status in ("completed", "failed"):
                sets = ["status = $3"]
                params = [task_id, agent_id, status]
                param_idx = 4

                if completed_scans is not None:
                    sets.append(f"completed_scans = ${param_idx}")
                    params.append(completed_scans)
                    param_idx += 1

                if error_message is not None:
                    sets.append(f"error_message = ${param_idx}")
                    params.append(error_message)
                    param_idx += 1

                sets.append("completed_at = NOW()")
                params.append(task_id)
                params.append(agent_id)

                query = f"UPDATE task_assignments SET {', '.join(sets)} WHERE task_id = $1 AND agent_id = $2"
                await conn.execute(query, task_id, agent_id, status)
            else:
                if progress is not None:
                    await conn.execute(
                        "UPDATE task_assignments SET status = $3, progress = $4 "
                        "WHERE task_id = $1 AND agent_id = $2",
                        task_id, agent_id, status, progress,
                    )
                else:
                    await conn.execute(
                        "UPDATE task_assignments SET status = $3 "
                        "WHERE task_id = $1 AND agent_id = $2",
                        task_id, agent_id, status,
                    )


# ============================================================
# IP 资产数据操作
# ============================================================
class IPAssetStorage:
    """IP资产数据存储"""

    @staticmethod
    async def upsert_ip(
        ip_address: str,
        ip_type: Optional[str] = None,
        metadata: Dict[str, Any] = None,
        tags: List[str] = None,
        discovered_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """插入或更新IP资产"""
        if ip_type is None:
            ip_type = classify_ip_type(ip_address)
        
        if metadata is None:
            metadata = {}
        if tags is None:
            tags = []

        async with pg_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ip_assets (ip_address, ip_type, metadata, tags, discovered_by)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (ip_address) DO UPDATE SET
                    ip_type = LEAST(ip_assets.ip_type, $2),
                    metadata = ip_assets.metadata || $3,
                    tags = ARRAY_CAT(ip_assets.tags, $4),
                    updated_at = NOW()
                RETURNING *
                """,
                ip_address, ip_type, json.dumps(metadata), tags, discovered_by,
            )
            return dict(row)

    @staticmethod
    async def get_ip(ip_address: str) -> Optional[Dict[str, Any]]:
        """获取IP资产"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ip_assets WHERE ip_address = $1::INET",
                ip_address,
            )
            return dict(row) if row else None

    @staticmethod
    async def get_ip_by_id(ip_id: UUID) -> Optional[Dict[str, Any]]:
        """按ID获取IP资产"""
        async with pg_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM ip_assets WHERE id = $1",
                ip_id,
            )
            return dict(row) if row else None

    @staticmethod
    async def list_ips(
        ip_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """列出IP资产"""
        async with pg_connection() as conn:
            conditions = []
            params = []
            param_idx = 1

            if ip_type:
                conditions.append(f"ip_type = ${param_idx}")
                params.append(ip_type)
                param_idx += 1

            if search:
                conditions.append(f"ip_address::TEXT LIKE ${param_idx}")
                params.append(f"%{search}%")
                param_idx += 1

            where = f"WHERE {' AND '.join(conditions)} " if conditions else ""

            rows = await conn.fetch(
                f"SELECT * FROM ip_assets {where}ORDER BY ip_address LIMIT ${param_idx} OFFSET ${param_idx + 1}",
                *params, limit, offset,
            )
            return [dict(r) for r in rows]


# ============================================================
# IP 关系数据操作
# ============================================================
class IPRelationStorage:
    """IP关系数据存储（图结构）"""

    @staticmethod
    async def create_relation(
        from_ip: str,
        to_ip: str,
        relation_type: str,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None,
        metadata: Dict[str, Any] = None,
        created_by: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """创建IP关系"""
        if valid_from is None:
            valid_from = datetime.now(timezone.utc)
        if metadata is None:
            metadata = {}

        async with pg_connection() as conn:
            # 获取或创建两端IP
            from_row = await conn.fetchrow(
                """
                INSERT INTO ip_assets (ip_address, ip_type, discovered_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (ip_address) DO NOTHING
                RETURNING id
                """,
                from_ip, classify_ip_type(from_ip), created_by,
            )
            to_row = await conn.fetchrow(
                """
                INSERT INTO ip_assets (ip_address, ip_type, discovered_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (ip_address) DO NOTHING
                RETURNING id
                """,
                to_ip, classify_ip_type(to_ip), created_by,
            )

            if not from_row or not to_row:
                # 尝试查询
                from_row = from_row or await conn.fetchrow(
                    "SELECT id FROM ip_assets WHERE ip_address = $1::INET", from_ip
                )
                to_row = to_row or await conn.fetchrow(
                    "SELECT id FROM ip_assets WHERE ip_address = $1::INET", to_ip
                )

            row = await conn.fetchrow(
                """
                INSERT INTO ip_relations (from_ip_id, to_ip_id, relation_type, valid_from, valid_to, metadata, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (from_ip_id, to_ip_id, relation_type, valid_from) DO UPDATE SET
                    valid_to = EXCLUDED.valid_to, metadata = EXCLUDED.metadata
                RETURNING *
                """,
                from_row["id"], to_row["id"], relation_type,
                valid_from, valid_to, json.dumps(metadata), created_by,
            )
            return dict(row)

    @staticmethod
    async def get_ip_graph(
        ip_address: str,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """
        获取IP关系子图
        使用递归CTE实现图遍历
        """
        async with pg_connection() as conn:
            # 获取中心IP
            center = await conn.fetchrow(
                "SELECT id, ip_address, ip_type FROM ip_assets WHERE ip_address = $1::INET",
                ip_address,
            )
            if not center:
                return {"center_ip": ip_address, "nodes": [], "edges": [], "depth": depth, "total_nodes": 0, "total_edges": 0}

            # 递归查询关系图
            query = f"""
            WITH RECURSIVE graph AS (
                -- 锚点: 中心IP的直接关系
                SELECT 
                    ir.id as relation_id,
                    ir.from_ip_id,
                    ir.to_ip_id,
                    ir.relation_type,
                    ir.valid_from,
                    ir.valid_to,
                    ir.metadata,
                    1 as hop,
                    ARRAY[ir.from_ip_id, ir.to_ip_id] as visited
                FROM ip_relations ir
                WHERE ir.from_ip_id = $1 OR ir.to_ip_id = $1
                WHERE ir.valid_to IS NULL OR ir.valid_to > NOW()
                
                UNION
                
                -- 递归: 扩展下一层
                SELECT 
                    ir.id as relation_id,
                    ir.from_ip_id,
                    ir.to_ip_id,
                    ir.relation_type,
                    ir.valid_from,
                    ir.valid_to,
                    ir.metadata,
                    g.hop + 1,
                    g.visited || ARRAY[ir.from_ip_id, ir.to_ip_id]
                FROM ip_relations ir
                JOIN graph g ON (
                    (ir.from_ip_id = ANY(g.visited) OR ir.to_ip_id = ANY(g.visited))
                    AND ir.from_ip_id != ALL(g.visited)
                    AND ir.to_ip_id != ALL(g.visited)
                )
                WHERE g.hop < $2
                AND ir.valid_to IS NULL OR ir.valid_to > NOW()
            )
            SELECT * FROM graph
            """
            rows = await conn.fetch(query, center["id"], depth)

            # 构建节点和边
            node_ids = set()
            edges = []
            for r in rows:
                node_ids.add(r["from_ip_id"])
                node_ids.add(r["to_ip_id"])
                edges.append({
                    "id": str(r["relation_id"]),
                    "from": str(r["from_ip_id"]),
                    "to": str(r["to_ip_id"]),
                    "relation_type": r["relation_type"],
                    "metadata": r["metadata"] or {},
                })

            # 获取节点详情
            nodes = []
            if node_ids:
                ip_rows = await conn.fetch(
                    "SELECT id, ip_address, ip_type, metadata FROM ip_assets WHERE id = ANY($1)",
                    list(node_ids),
                )
                for r in ip_rows:
                    nodes.append({
                        "id": str(r["id"]),
                        "ip_address": str(r["ip_address"]),
                        "ip_type": r["ip_type"],
                        "metadata": r["metadata"] or {},
                    })

            return {
                "center_ip": ip_address,
                "nodes": nodes,
                "edges": edges,
                "depth": depth,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }

    @staticmethod
    async def invalidate_relation(relation_id: UUID) -> None:
        """使关系失效（设置valid_to）"""
        async with pg_connection() as conn:
            await conn.execute(
                "UPDATE ip_relations SET valid_to = NOW() WHERE id = $1",
                relation_id,
            )

    @staticmethod
    async def list_relations(
        ip_address: Optional[str] = None,
        relation_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """列出IP关系"""
        async with pg_connection() as conn:
            conditions = ["1=1"]
            params = []
            param_idx = 1

            if ip_address:
                conditions.append(f"(ir.from_ip_id = ia.id AND ia.ip_address = ${param_idx}::INET "
                                  f"OR ir.to_ip_id = ia.id AND ia.ip_address = ${param_idx}::INET)")
                params.append(ip_address)
                param_idx += 1

            if relation_type:
                conditions.append(f"ir.relation_type = ${param_idx}")
                params.append(relation_type)
                param_idx += 1

            if active_only:
                conditions.append("ir.valid_to IS NULL OR ir.valid_to > NOW()")

            query = f"""
                SELECT ir.*, 
                       from_ia.ip_address as from_ip, from_ia.ip_type as from_ip_type,
                       to_ia.ip_address as to_ip, to_ia.ip_type as to_ip_type
                FROM ip_relations ir
                JOIN ip_assets from_ia ON ir.from_ip_id = from_ia.id
                JOIN ip_assets to_ia ON ir.to_ip_id = to_ia.id
                CROSS JOIN ip_assets ia
                WHERE {' AND '.join(conditions)}
                ORDER BY ir.created_at DESC
                LIMIT 1000
            """
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]


# ============================================================
# 扫描结果存储 (ClickHouse)
# ============================================================
class ScanResultStorage:
    """扫描结果存储 (ClickHouse)"""

    @staticmethod
    async def batch_insert(results: List[Dict[str, Any]]) -> int:
        """
        批量插入扫描结果
        
        Args:
            results: 扫描结果列表
            
        Returns:
            插入行数
        """
        if not results:
            return 0

        ch = get_clickhouse()
        
        # 准备数据
        data = []
        for r in results:
            data.append({
                "task_id": str(r.get("task_id", "")),
                "agent_id": str(r.get("agent_id", "")),
                "source_ip": r.get("source_ip", ""),
                "target_ip": r.get("target_ip", ""),
                "port": r.get("port", 0),
                "protocol": r.get("protocol", "tcp"),
                "status": r.get("status", "unknown"),
                "latency_ms": r.get("latency_ms") or 0.0,
                "banner": r.get("banner") or "",
                "error_message": r.get("error_message") or "",
                "retry_count": r.get("retry_count", 0),
                "scanned_at": r.get("scanned_at") or datetime.now(timezone.utc),
            })

        try:
            ch.insert(f"{CLICKHOUSE_DB}.scan_results", data)
            logger.info(f"Inserted {len(data)} scan results to ClickHouse")
            return len(data)
        except Exception as e:
            logger.error(f"Failed to insert scan results: {e}")
            return 0

    @staticmethod
    async def query_results(
        target_ip: Optional[str] = None,
        source_ip: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        status: Optional[str] = None,
        task_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """查询扫描结果"""
        ch = get_clickhouse()
        
        conditions = []
        if target_ip:
            conditions.append(f"target_ip = '{target_ip}'")
        if source_ip:
            conditions.append(f"source_ip = '{source_ip}'")
        if port:
            conditions.append(f"port = {port}")
        if protocol:
            conditions.append(f"protocol = '{protocol}'")
        if status:
            conditions.append(f"status = '{status}'")
        if task_id:
            conditions.append(f"task_id = '{task_id}'")
        if start_time:
            conditions.append(f"scanned_at >= '{start_time}'")
        if end_time:
            conditions.append(f"scanned_at <= '{end_time}'")

        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        
        query = f"""
            SELECT * FROM {CLICKHOUSE_DB}.scan_results
            {where}
            ORDER BY scanned_at DESC
            LIMIT {limit}
        """
        
        result = ch.query(query)
        return result.result_rows

    @staticmethod
    async def get_ip_exposure(ip_address: str) -> Dict[str, Any]:
        """获取单IP暴露面"""
        ch = get_clickhouse()
        
        # 获取该IP的所有扫描结果统计
        query = f"""
            SELECT 
                port,
                protocol,
                status,
                count() as scan_count,
                max(scanned_at) as last_scanned,
                arrayDistinct(groupArray(source_ip)) as scanning_agents,
                avg(latency_ms) as avg_latency
            FROM {CLICKHOUSE_DB}.scan_results
            WHERE target_ip = '{ip_address}'
            GROUP BY port, protocol, status
            ORDER BY port, protocol
        """
        
        result = ch.query(query)
        exposures = []
        for row in result.result_rows:
            exposures.append({
                "port": row[0],
                "protocol": row[1],
                "status": row[2],
                "scan_count": row[3],
                "last_scanned": str(row[4]),
                "scanning_agents": row[5],
                "avg_latency": row[6],
            })

        return {
            "ip": ip_address,
            "exposures": exposures,
            "total_ports": len(exposures),
            "open_ports": sum(1 for e in exposures if e["status"] == "open"),
        }

    @staticmethod
    async def get_scan_stats(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """获取扫描统计"""
        ch = get_clickhouse()
        
        conditions = []
        if start_time:
            conditions.append(f"scanned_at >= '{start_time}'")
        if end_time:
            conditions.append(f"scanned_at <= '{end_time}'")
        
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        
        query = f"""
            SELECT 
                count() as total,
                countIf(status = 'open') as open_count,
                countIf(status = 'closed') as closed_count,
                countIf(status = 'filtered') as filtered_count,
                countIf(status = 'unknown') as unknown_count,
                countDistinct(target_ip) as unique_targets,
                countDistinct(source_ip) as unique_sources,
                min(scanned_at) as earliest,
                max(scanned_at) as latest
            FROM {CLICKHOUSE_DB}.scan_results
            {where}
        """
        
        result = ch.query(query)
        row = result.result_rows[0] if result.result_rows else None
        
        if row:
            return {
                "total": row[0],
                "open_count": row[1],
                "closed_count": row[2],
                "filtered_count": row[3],
                "unknown_count": row[4],
                "unique_targets": row[5],
                "unique_sources": row[6],
                "earliest": str(row[7]) if row[7] else None,
                "latest": str(row[8]) if row[8] else None,
            }
        return {}