"""
ASDP - 数据导出 API
"""
import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from controller.services.storage_service import ScanResultStorage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/csv")
async def export_csv(
    target_ip: Optional[str] = None,
    ip_pair_from: Optional[str] = None,
    ip_pair_to: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    task_id: Optional[str] = None,
):
    """
    导出扫描结果为CSV
    
    - **target_ip**: 按目标IP筛选
    - **ip_pair_from / ip_pair_to**: 按IP对筛选
    - **start_time / end_time**: 按时间范围筛选
    - **task_id**: 按任务筛选
    """
    results = await ScanResultStorage.query_results(
        target_ip=target_ip or ip_pair_to,
        source_ip=ip_pair_from,
        start_time=start_time,
        end_time=end_time,
        task_id=task_id,
        limit=100000,
    )
    
    if not results:
        raise HTTPException(status_code=404, detail="No results found")
    
    # 生成CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow([
        "task_id", "agent_id", "source_ip", "target_ip",
        "port", "protocol", "status", "latency_ms",
        "banner", "error_message", "retry_count", "scanned_at"
    ])
    
    # 数据行
    for r in results:
        writer.writerow([
            r.get("task_id", ""),
            r.get("agent_id", ""),
            r.get("source_ip", ""),
            r.get("target_ip", ""),
            r.get("port", ""),
            r.get("protocol", ""),
            r.get("status", ""),
            r.get("latency_ms", ""),
            r.get("banner", ""),
            r.get("error_message", ""),
            r.get("retry_count", ""),
            r.get("scanned_at", ""),
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=scan_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/json")
async def export_json(
    target_ip: Optional[str] = None,
    ip_pair_from: Optional[str] = None,
    ip_pair_to: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    task_id: Optional[str] = None,
):
    """
    导出扫描结果为JSON
    
    参数同CSV导出
    """
    results = await ScanResultStorage.query_results(
        target_ip=target_ip or ip_pair_to,
        source_ip=ip_pair_from,
        start_time=start_time,
        end_time=end_time,
        task_id=task_id,
        limit=100000,
    )
    
    export_data = {
        "exported_at": datetime.now().isoformat(),
        "total_records": len(results),
        "filters": {
            "target_ip": target_ip or ip_pair_to,
            "source_ip": ip_pair_from,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "task_id": task_id,
        },
        "results": results,
    }
    
    return StreamingResponse(
        iter([json.dumps(export_data, ensure_ascii=False, default=str)]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=scan_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )