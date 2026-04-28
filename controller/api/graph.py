"""
ASDP - IP 关系图谱 API
"""
import logging
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from controller.models.schemas import IPRelationCreate, IPGraphResponse
from controller.services.storage_service import IPRelationStorage, IPAssetStorage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/ip/{ip_address}")
async def get_ip_graph(
    ip_address: str,
    depth: int = Query(2, ge=1, le=5, description="图遍历深度"),
):
    """
    获取IP关系子图
    
    以指定IP为中心，返回其关系子图（节点+边）
    
    - **ip_address**: 中心IP
    - **depth**: 遍历深度（1-5）
    """
    # 验证IP格式
    try:
        import ipaddress
        ipaddress.ip_address(ip_address)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid IP address: {ip_address}")
    
    graph = await IPRelationStorage.get_ip_graph(ip_address, depth)
    return IPGraphResponse(**graph)


@router.get("/stats")
async def get_graph_stats():
    """
    获取图谱统计信息
    
    返回节点数、边数、关系类型分布等
    """
    from controller.database import pg_connection
    
    async with pg_connection() as conn:
        # 总节点数
        total_nodes = await conn.fetchval("SELECT COUNT(*) FROM ip_assets")
        
        # 总边数（活跃）
        total_edges = await conn.fetchval(
            "SELECT COUNT(*) FROM ip_relations WHERE valid_to IS NULL OR valid_to > NOW()"
        )
        
        # 按IP类型分布
        type_dist_rows = await conn.fetch("""
            SELECT ip_type, COUNT(*) as count 
            FROM ip_assets 
            GROUP BY ip_type 
            ORDER BY count DESC
        """)
        type_distribution = {row["ip_type"]: row["count"] for row in type_dist_rows}
        
        # 按关系类型分布
        rel_dist_rows = await conn.fetch("""
            SELECT relation_type, COUNT(*) as count 
            FROM ip_relations 
            WHERE valid_to IS NULL OR valid_to > NOW()
            GROUP BY relation_type 
            ORDER BY count DESC
        """)
        relation_distribution = {row["relation_type"]: row["count"] for row in rel_dist_rows}
        
        # 孤立节点（没有关系）
        isolated_nodes = await conn.fetchval("""
            SELECT COUNT(*) FROM ip_assets ia
            WHERE NOT EXISTS (
                SELECT 1 FROM ip_relations ir 
                WHERE (ir.from_ip_id = ia.id OR ir.to_ip_id = ia.id)
                AND (ir.valid_to IS NULL OR ir.valid_to > NOW())
            )
        """)
    
    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "type_distribution": type_distribution,
        "relation_distribution": relation_distribution,
        "isolated_nodes": isolated_nodes,
        "connected_nodes": total_nodes - isolated_nodes,
    }


@router.post("/relation", status_code=201)
async def create_relation(relation: IPRelationCreate):
    """
    创建IP关系
    
    - **from_ip**: 源IP
    - **to_ip**: 目标IP
    - **relation_type**: 关系类型（如 nat_mapping, eip_binding 等）
    - **valid_from**: 生效时间
    - **valid_to**: 失效时间
    - **metadata**: 扩展属性
    """
    # 验证IP格式
    for ip_field in ["from_ip", "to_ip"]:
        try:
            import ipaddress
            ipaddress.ip_address(getattr(relation, ip_field))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid IP address: {getattr(relation, ip_field)}")
    
    result = await IPRelationStorage.create_relation(
        from_ip=relation.from_ip,
        to_ip=relation.to_ip,
        relation_type=relation.relation_type,
        valid_from=relation.valid_from,
        valid_to=relation.valid_to,
        metadata=relation.metadata,
    )
    
    return {
        "id": str(result["id"]),
        "from_ip_id": str(result["from_ip_id"]),
        "to_ip_id": str(result["to_ip_id"]),
        "relation_type": result["relation_type"],
        "valid_from": result["valid_from"],
        "valid_to": result["valid_to"],
    }


@router.delete("/relation/{relation_id}")
async def delete_relation(relation_id: UUID):
    """
    删除IP关系（软删除：设置为失效）
    """
    await IPRelationStorage.invalidate_relation(relation_id)
    return {"message": "Relation invalidated", "relation_id": str(relation_id)}


@router.get("/relations")
async def list_relations(
    ip_address: Optional[str] = None,
    relation_type: Optional[str] = None,
    active_only: bool = Query(True, description="只返回活跃关系"),
):
    """
    列出IP关系
    
    - **ip_address**: 过滤指定IP的关系
    - **relation_type**: 过滤指定类型
    - **active_only**: 是否只返回活跃关系
    """
    relations = await IPRelationStorage.list_relations(
        ip_address=ip_address,
        relation_type=relation_type,
        active_only=active_only,
    )
    
    return {
        "total": len(relations),
        "relations": relations,
    }


@router.get("/neighbors/{ip_address}")
async def get_ip_neighbors(ip_address: str):
    """
    获取IP的直接邻居（1跳）
    
    简化版的图谱查询，只返回直接关联的IP
    """
    graph = await IPRelationStorage.get_ip_graph(ip_address, depth=1)
    
    return {
        "center_ip": ip_address,
        "neighbors": [
            {
                "ip": n["ip_address"],
                "type": n["ip_type"],
                "relations": [
                    e["relation_type"] for e in graph["edges"]
                    if e["from"] == n["id"] or e["to"] == n["id"]
                ]
            }
            for n in graph["nodes"]
            if n["ip_address"] != ip_address
        ],
        "total_neighbors": len(graph["nodes"]) - 1,  # 减去自身
    }