# Agent 管理 API

## 创建 Agent

```
POST /api/v1/agents/
Header: X-API-Key: your_controller_api_key
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
| name | string | ✅ | Agent名称 |
| description | string | ❌ | 描述 |
| network_zone | string | ❌ | 网络区域 |
| max_concurrency | int | ❌ | 最大并发数，默认 50 |
| rate_limit | int | ❌ | 速率限制(次/秒)，默认 1000 |

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "uuid-agent-id",
    "name": "agent-network-a",
    "token": "secret_token_xxxxx",
    "status": "offline",
    "network_zone": "vpc-a",
    "max_concurrency": 50,
    "rate_limit": 1000,
    "created_at": "2024-01-01T00:00:00Z"
  }
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
| status | enum | 状态过滤：online/offline/disabled |

### 响应

```json
{
  "code": 200,
  "data": [
    {
      "id": "uuid",
      "name": "agent-network-a",
      "status": "online",
      "network_zone": "vpc-a",
      "source_ip": "10.0.0.1",
      "max_concurrency": 50,
      "rate_limit": 1000,
      "last_heartbeat": "2024-01-01T00:05:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
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
  "source_ip": "10.0.0.1",
  "stats": {
    "buffer_size": 0
  }
}
```

### 响应

```json
{
  "code": 200,
  "data": {
    "status": "ok",
    "pending_tasks": 2
  }
}
```

---

## 启用 Agent

```
POST /api/v1/agents/{agent_id}/enable
Header: X-API-Key: your_controller_api_key
```

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "name": "agent-network-a",
    "status": "online"
  }
}
```

---

## 禁用 Agent

```
POST /api/v1/agents/{agent_id}/disable
Header: X-API-Key: your_controller_api_key
```

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "uuid",
    "name": "agent-network-a",
    "status": "disabled"
  }
}