# 任务管理 API

## 创建扫描任务

```
POST /api/v1/tasks/
```

### 请求体

```json
{
  "name": "scan-prod-env",
  "target_ips": ["192.168.1.0/24", "10.0.0.1"],
  "port_range": "1-1000",
  "protocol": "tcp",
  "scan_type": "connect",
  "timeout_ms": 3000,
  "max_retries": 3,
  "agent_ids": ["uuid-1", "uuid-2"],
  "description": "生产环境扫描"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 任务名称 |
| target_ips | string[] | ✅ | 目标IP列表 |
| port_range | string | ✅ | 端口范围，如 "1-1000" 或 "22,80,443" |
| protocol | enum | ❌ | tcp/udp/both，默认 tcp |
| scan_type | string | ❌ | connect/syn，默认 connect |
| timeout_ms | int | ❌ | 超时(ms)，默认 3000 |
| max_retries | int | ❌ | 最大重试次数，默认 3 |
| agent_ids | string[] | ❌ | 指定Agent，为空则自动分配在线Agent |
| description | string | ❌ | 任务描述 |

### 响应 (201 Created)

```json
{
  "id": "uuid-task-id",
  "name": "scan-prod-env",
  "target_ips": ["192.168.1.0/24", "10.0.0.1"],
  "port_range": "1-1000",
  "protocol": "tcp",
  "scan_type": "connect",
  "timeout_ms": 3000,
  "max_retries": 3,
  "status": "running",
  "progress": 0,
  "created_at": "2024-01-01T00:00:00Z"
}
```

> **说明**: 任务创建后自动分发到Agent队列，状态直接设为 `running`。如果没有在线Agent，返回 400 错误。

---

## 查询任务列表

```
GET /api/v1/tasks/?status=running&limit=50&offset=0
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 状态过滤：pending/running/completed/failed/cancelled |
| limit | int | 数量限制，默认 50，最大 200 |
| offset | int | 偏移量，默认 0 |

### 响应 (200 OK)

```json
[
  {
    "id": "uuid",
    "name": "task-name",
    "target_ips": ["192.168.1.0/24"],
    "port_range": "1-1000",
    "protocol": "tcp",
    "status": "running",
    "progress": 65,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

## 查询任务详情

```
GET /api/v1/tasks/{task_id}
```

### 响应 (200 OK)

```json
{
  "id": "uuid",
  "name": "task-name",
  "target_ips": ["192.168.1.0/24"],
  "port_range": "1-1000",
  "protocol": "tcp",
  "status": "running",
  "progress": 65,
  "created_at": "2024-01-01T00:00:00Z",
  "assignments": [
    {
      "agent_id": "uuid-agent-1",
      "agent_name": "agent-a",
      "status": "running",
      "progress": 80,
      "total_scans": 1000,
      "completed_scans": 800
    }
  ]
}
```

---

## 删除任务

```
DELETE /api/v1/tasks/{task_id}
```

### 响应 (200 OK)

```json
{
  "message": "Task deleted",
  "task_id": "uuid"
}
```

> **说明**: 软删除，运行中的任务会被标记为 `cancelled`。

---

## 取消任务

```
POST /api/v1/tasks/{task_id}/cancel
```

### 响应 (200 OK)

```json
{
  "message": "Task cancelled",
  "task_id": "uuid"
}
```

> **错误**: 如果任务状态不是 `running` 或 `pending`，返回 400。

---

## 获取任务进度

```
GET /api/v1/tasks/{task_id}/progress
```

### 响应 (200 OK)

```json
{
  "task_id": "uuid",
  "task_name": "task-name",
  "status": "running",
  "progress": 65,
  "total_scans": 2000,
  "completed_scans": 1300,
  "agents": [
    {
      "agent_id": "uuid-agent-1",
      "agent_name": "agent-a",
      "status": "completed",
      "progress": 100,
      "total_scans": 1000,
      "completed_scans": 1000
    },
    {
      "agent_id": "uuid-agent-2",
      "agent_name": "agent-b",
      "status": "running",
      "progress": 30,
      "total_scans": 1000,
      "completed_scans": 300
    }
  ]
}
```

---

## Agent 拉取任务

```
GET /api/v1/tasks/pull/{agent_id}
Header: X-Agent-Token: your_agent_token
```

### 响应 (200 OK)

```json
{
  "has_task": true,
  "task": {
    "task_id": "uuid",
    "agent_id": "uuid-agent-1",
    "target_ips": ["192.168.1.1"],
    "ports": [1, 2, 3],
    "protocol": "tcp",
    "scan_type": "connect",
    "timeout_ms": 3000,
    "max_retries": 3,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

无任务时：

```json
{
  "has_task": false,
  "task": null
}
```

---

## 上报扫描结果

```
POST /api/v1/tasks/results/report
Header: X-Agent-Token: your_agent_token
```

### 请求体

```json
{
  "task_id": "uuid",
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
      "error_message": null,
      "retry_count": 0,
      "scanned_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 响应 (200 OK)

```json
{
  "status": "ok",
  "received": 100,
  "inserted": 100
}
```

> **说明**: 上报后自动更新任务分配进度，当所有Agent完成后自动标记任务为 `completed`。同时自动发现并记录IP资产。