# Agent 管理 API

## 创建 Agent

```
POST /api/v1/agents/
```

### 请求体

```json
{
  "name": "agent-network-a",
  "description": "部署在VPC-A的扫描节点",
  "network_zone": "vpc-a",
  "max_concurrency": 50,
  "rate_limit": 1000
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | Agent名称（唯一） |
| description | string | ❌ | 描述 |
| network_zone | string | ❌ | 网络区域标识 |
| max_concurrency | int | ❌ | 最大并发数，默认 50 |
| rate_limit | int | ❌ | 每秒最大扫描数，默认 1000 |

### 响应 (201 Created)

```json
{
  "id": "uuid-agent-id",
  "name": "agent-network-a",
  "description": "部署在VPC-A的扫描节点",
  "network_zone": "vpc-a",
  "token": "secret_token_xxxxx",
  "status": "offline",
  "source_ip": null,
  "max_concurrency": 50,
  "rate_limit": 1000,
  "last_heartbeat": null,
  "created_at": "2024-01-01T00:00:00Z"
}
```

> ⚠️ **重要**: Token 仅在创建时返回一次，请妥善保存。

---

## 查询 Agent 列表

```
GET /api/v1/agents/?status=online
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 状态过滤：online/offline/disabled |

### 响应 (200 OK)

```json
[
  {
    "id": "uuid",
    "name": "agent-network-a",
    "description": "部署在VPC-A的扫描节点",
    "network_zone": "vpc-a",
    "token": "secret_token_xxxxx",
    "status": "online",
    "source_ip": "10.0.0.1",
    "max_concurrency": 50,
    "rate_limit": 1000,
    "last_heartbeat": "2024-01-01T00:05:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

---

## 查询 Agent 详情

```
GET /api/v1/agents/{agent_id}
```

### 响应 (200 OK)

```json
{
  "id": "uuid",
  "name": "agent-network-a",
  "description": "部署在VPC-A的扫描节点",
  "network_zone": "vpc-a",
  "token": "secret_token_xxxxx",
  "status": "online",
  "source_ip": "10.0.0.1",
  "max_concurrency": 50,
  "rate_limit": 1000,
  "last_heartbeat": "2024-01-01T00:05:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

## Agent 心跳

```
POST /api/v1/agents/{agent_id}/heartbeat
Header: X-Agent-Token: your_agent_token
```

### 请求体

```json
{
  "source_ip": "10.0.0.1"
}
```

### 响应 (200 OK)

```json
{
  "status": "ok",
  "agent_id": "uuid"
}
```

> **说明**: 心跳同时更新 Redis（在线状态）和 PostgreSQL（last_heartbeat 时间戳）。

---

## 禁用 Agent

```
POST /api/v1/agents/{agent_id}/disable
```

### 响应 (200 OK)

```json
{
  "message": "Agent disabled",
  "agent_id": "uuid"
}
```

---

## 启用 Agent

```
POST /api/v1/agents/{agent_id}/enable
```

### 响应 (200 OK)

```json
{
  "message": "Agent enabled",
  "agent_id": "uuid"
}
```

> **说明**: 启用后状态设为 `offline`，等待Agent发送心跳后变为 `online`。

---

## 获取 Agent 队列状态

```
GET /api/v1/agents/{agent_id}/queue
```

### 响应 (200 OK)

```json
{
  "agent_id": "uuid",
  "agent_name": "agent-network-a",
  "status": "online",
  "is_online": true,
  "queue_length": 5
}
```

> **说明**: `is_online` 基于 Redis 心跳判断，`queue_length` 为该Agent待执行任务数。