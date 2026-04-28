# 扫描结果 API

## 查询扫描结果

```
GET /api/v1/results/?target_ip=192.168.1.1&port=80&protocol=tcp&status=open&limit=100
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| target_ip | string | 目标IP过滤 |
| source_ip | string | 探测源IP过滤 |
| port | int | 端口过滤 |
| protocol | string | tcp/udp |
| status | string | open/closed/filtered/unknown |
| task_id | string | 任务ID过滤 |
| start_time | datetime | 开始时间 (ISO 8601) |
| end_time | datetime | 结束时间 (ISO 8601) |
| limit | int | 数量限制，默认 1000，最大 100000 |

### 响应 (200 OK)

```json
{
  "total": 5000,
  "results": [
    {
      "task_id": "uuid",
      "agent_id": "uuid",
      "source_ip": "10.0.0.1",
      "target_ip": "192.168.1.1",
      "port": 80,
      "protocol": "tcp",
      "status": "open",
      "latency_ms": 1.5,
      "banner": "Apache/2.4",
      "error_message": null,
      "retry_count": 0,
      "scanned_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 查询单 IP 暴露面

```
GET /api/v1/results/ip/{ip_address}
```

### 响应 (200 OK)

```json
{
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
      "last_scanned": "2024-01-01T00:05:00Z"
    }
  ],
  "asset": {
    "id": "uuid",
    "ip_address": "192.168.1.1",
    "ip_type": "private",
    "discovered_by": "uuid-agent-1",
    "first_seen": "2024-01-01T00:00:00Z",
    "last_seen": "2024-01-01T00:05:00Z"
  }
}
```

> **说明**: 返回该IP的端口统计信息，以及从 PostgreSQL 获取的IP资产信息。

---

## 查询 IP 对扫描结果

```
GET /api/v1/results/pair?from=10.0.0.1&to=192.168.1.1&limit=1000
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| from | string | 源IP（探测出口） |
| to | string | 目标IP |
| limit | int | 数量限制，默认 1000，最大 100000 |

### 响应 (200 OK)

```json
{
  "from_ip": "10.0.0.1",
  "to_ip": "192.168.1.1",
  "total": 500,
  "summary": [
    {
      "port": 80,
      "protocol": "tcp",
      "statuses": {
        "open": 5,
        "closed": 0
      },
      "count": 5
    },
    {
      "port": 443,
      "protocol": "tcp",
      "statuses": {
        "open": 3,
        "filtered": 2
      },
      "count": 5
    }
  ],
  "results": [...]
}
```

> **说明**: 返回两个IP之间的所有扫描结果，并按端口+协议聚合统计。

---

## 扫描统计

```
GET /api/v1/results/stats?start_time=2024-01-01T00:00:00Z&end_time=2024-01-02T00:00:00Z
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |

### 响应 (200 OK)

```json
{
  "total": 100000,
  "open_count": 5000,
  "closed_count": 80000,
  "filtered_count": 10000,
  "unknown_count": 5000,
  "unique_targets": 200,
  "tcp_count": 80000,
  "udp_count": 20000
}