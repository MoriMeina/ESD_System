# 扫描结果 API

## 查询扫描结果

```
GET /api/v1/results/?target_ip=192.168.1.1&port=80&protocol=tcp&status=open&limit=100&offset=0
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| target_ip | string | 目标IP过滤 |
| source_ip | string | 探测源IP过滤 |
| port | int | 端口过滤 |
| protocol | enum | tcp/udp |
| status | enum | open/closed/filtered/unknown |
| task_id | string | 任务ID过滤 |
| agent_id | string | Agent ID过滤 |
| start_time | string | 开始时间 (ISO 8601) |
| end_time | string | 结束时间 (ISO 8601) |
| limit | int | 数量限制，默认 100 |
| offset | int | 偏移量，默认 0 |

### 响应

```json
{
  "code": 200,
  "data": {
    "total": 5000,
    "results": [
      {
        "id": "uuid",
        "task_id": "uuid",
        "agent_id": "uuid",
        "source_ip": "10.0.0.1",
        "target_ip": "192.168.1.1",
        "port": 80,
        "protocol": "tcp",
        "status": "open",
        "latency_ms": 1.5,
        "banner": "Apache/2.4",
        "retry_count": 0,
        "scanned_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

## 查询单 IP 暴露面

```
GET /api/v1/results/ip/{target_ip}
```

### 响应

```json
{
  "code": 200,
  "data": {
    "ip": "192.168.1.1",
    "total_ports": 1000,
    "open_ports": 15,
    "filtered_ports": 200,
    "exposures": [
      {
        "port": 22,
        "protocol": "tcp",
        "status": "open",
        "scan_count": 5,
        "avg_latency": 2.3,
        "banner": "OpenSSH 8.9",
        "scanning_agents": ["agent-1", "agent-2"],
        "last_scanned": "2024-01-01T00:05:00Z"
      },
      {
        "port": 80,
        "protocol": "tcp",
        "status": "open",
        "scan_count": 5,
        "avg_latency": 1.1,
        "banner": "Nginx/1.24",
        "scanning_agents": ["agent-1", "agent-2"],
        "last_scanned": "2024-01-01T00:05:00Z"
      }
    ]
  }
}
```

---

## 扫描统计

```
GET /api/v1/results/stats
```

### 响应

```json
{
  "code": 200,
  "data": {
    "total": 100000,
    "open_count": 5000,
    "closed_count": 80000,
    "filtered_count": 10000,
    "unknown_count": 5000,
    "unique_targets": 200,
    "tcp_count": 80000,
    "udp_count": 20000
  }
}