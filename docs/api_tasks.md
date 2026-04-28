# 任务管理 API

## 创建扫描任务

```
POST /api/v1/tasks/
```

### 请求体

```json
{
  "name": "scan-prod-env",
  "description": "生产环境扫描",
  "target_ips": ["192.168.1.0/24", "10.0.0.1"],
  "port_range": "1-1000",
  "protocol": "tcp",
  "scan_type": "connect",
  "timeout_ms": 3000,
  "max_retries": 3,
  "agent_ids": ["uuid-1", "uuid-2"]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 任务名称 |
| description | string | ❌ | 描述 |
| target_ips | string[] | ✅ | 目标IP列表 |
| port_range | string | ✅ | 端口范围，如 "1-1000" 或 "22,80,443" |
| protocol | enum | ❌ | tcp/udp/both，默认 tcp |
| scan_type | enum | ❌ | connect/syn，默认 connect |
| timeout_ms | int | ❌ | 超时(ms)，默认 3000 |
| max_retries | int | ❌ | 最大重试次数，默认 3 |
| agent_ids | string[] | ❌ | 指定Agent，为空则自动分配 |

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "uuid-task-id",
    "name": "scan-prod-env",
    "status": "pending",
    "created_at": "2024-01-01T00:00:00Z",
    "sub_tasks": [
      {
        "agent_id": "uuid-agent-1",
        "targets": ["192.168.1.1"],
        "ports": [1, 2, 3]
      }
    ]
  }
}
```

---

## 查询任务列表

```
GET /api/v1/tasks/?limit=50&offset=0&status=running
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| limit | int | 数量限制，默认 50 |
| offset | int | 偏移量，默认 0 |
| status | enum | 状态过滤：pending/running/completed/failed/cancelled |

### 响应

```json
{
  "code": 200,
  "data": [
    {
      "id": "uuid",
      "name": "task-name",
      "status": "running",
      "progress": 65,
      "total_targets": 100,
      "scanned_targets": 65,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:05:00Z"
    }
  ]
}
```

---

## 查询任务详情

```
GET /api/v1/tasks/{task_id}/progress
```

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "name": "task-name",
    "status": "running",
    "progress": 65,
    "total_targets": 100,
    "scanned_targets": 65,
    "total_ports": 1000,
    "scanned_ports": 65000,
    "sub_tasks": [
      {
        "agent_id": "uuid-agent-1",
        "status": "completed",
        "progress": 100
      },
      {
        "agent_id": "uuid-agent-2",
        "status": "running",
        "progress": 30
      }
    ],
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z"
  }
}
```

---

## 取消任务

```
POST /api/v1/tasks/{task_id}/cancel
```

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "status": "cancelled",
    "message": "Task cancelled successfully"
  }
}
```

---

## Agent 拉取子任务

```
POST /api/v1/tasks/pull
Header: X-Agent-Token: your_token
```

### 响应

```json
{
  "code": 200,
  "data": {
    "task_id": "uuid",
    "sub_targets": [
      {
        "target_ip": "192.168.1.1",
        "ports": [1, 2, 3],
        "protocol": "tcp",
        "timeout_ms": 3000,
        "max_retries": 3
      }
    ]
  }
}
```

---

## 上报扫描结果

```
POST /api/v1/tasks/{task_id}/results
Header: X-Agent-Token: your_token
```

### 请求体

```json
{
  "agent_id": "uuid-agent-1",
  "results": [
    {
      "source_ip": "10.0.0.1",
      "target_ip": "192.168.1.1",
      "port": 80,
      "protocol": "tcp",
      "status": "open",
      "latency_ms": 1.5,
      "banner": "Apache/2.4",
      "scanned_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 响应

```json
{
  "code": 200,
  "data": {
    "accepted": 100,
    "task_id": "uuid"
  }
}