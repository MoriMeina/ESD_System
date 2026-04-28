"""
ASDP - 扫描结果查询 API
"""
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from controller.services.storage_service import ScanResultStorage, IPAssetStorage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def query_results(
    target_ip: Optional[str] = None,
    source_ip: Optional[str] = None,
    port: Optional[int] = None,
    protocol: Optional[str] = None,
    status: Optional[str] = None,
    task_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(1000, ge=1, le=100000),
):
    """
    查询扫描结果
    
    支持多条件过滤:
    - **target_ip**: 目标IP
    - **source_ip**: 探测出口IP
    - **port**: 端口号
    - **protocol**: tcp/udp
    - **status**: open/closed/filtered/unknown
    - **task_id**: 任务ID
    - **start_time / end_time**: 时间范围
    """
    results = await ScanResultStorage.query_results(
        target_ip=target_ip,
        source_ip=source_ip,
        port=port,
        protocol=protocol,
        status=status,
        task_id=task_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    
    return {
        "total": len(results),
        "results": results,
    }


@router.get("/ip/{ip_address}")
async def get_ip_exposure(ip_address: str):
    """
    获取单IP暴露面
    
    返回该IP的所有端口扫描结果统计
    """
    # 验证IP格式
    try:
        import ipaddress
        ipaddress.ip_address(ip_address)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid IP address: {ip_address}")
    
    exposure = await ScanResultStorage.get_ip_exposure(ip_address)
    
    # 获取IP资产信息
    asset = await IPAssetStorage.get_ip(ip_address)
    
    return {
        **exposure,
        "asset": asset,
    }


@router.get("/pair")
async def get_ip_pair_results(
    from_ip: str = Query(..., alias="from"),
    to_ip: str = Query(..., alias="to"),
    limit: int = Query(1000, ge=1, le=100000),
):
    """
    查询IP对之间的扫描结果
    
    - **from**: 源IP（探测出口）
    - **to**: 目标IP
    """
    results = await ScanResultStorage.query_results(
        source_ip=from_ip,
        target_ip=to_ip,
        limit=limit,
    )
    
    # 聚合统计
    stats = {}
    for r in results:
        key = (r.get("port"), r.get("protocol"))
        if key not in stats:
            stats[key] = {
                "port": r.get("port"),
                "protocol": r.get("protocol"),
                "statuses": {},
                "count": 0,
            }
        status = r.get("status", "unknown")
        stats[key]["statuses"][status] = stats[key]["statuses"].get(status, 0) + 1
        stats[key]["count"] += 1
    
    return {
        "from_ip": from_ip,
        "to_ip": to_ip,
        "total": len(results),
        "summary": list(stats.values()),
        "results": results,
    }


@router.get("/stats")
async def get_scan_stats(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    """
    获取扫描统计数据
    
    返回总体统计信息
    """
    stats = await ScanResultStorage.get_scan_stats(
        start_time=start_time,
        end_time=end_time,
    )
    return stats