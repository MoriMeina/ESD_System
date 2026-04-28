# 关系图谱 API

## 查询 IP 关系子图

```
GET /api/v1/graph/ip/{ip_address}?depth=2
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| depth | int | 图遍历深度，默认 2，范围 1-5 |

### 响应 (200 OK)

```json
{
  "center_ip": "192.168.1.1",
  "depth": 2,
  "total_nodes": 8,
  "total_edges": 6,
  "nodes": [
    {
      "id": "uuid-1",
      "ip_address": "192.168.1.1",
      "ip_type": "private",
      "metadata": {}
    },
    {
      "id": "uuid-2",
      "ip_address": "203.0.113.1",
      "ip_type": "public",
      "metadata": {}
    }
  ],
  "edges": [
    {
      "id": "edge-uuid-1",
      "from": "uuid-1",
      "to": "uuid-2",
      "relation_type": "nat_mapping",
      "valid_from": "2024-01-01T00:00:00Z",
      "valid_to": null
    }
  ]
}
```

---

## 获取 IP 直接邻居

```
GET /api/v1/graph/neighbors/{ip_address}
```

### 响应 (200 OK)

```json
{
  "center_ip": "192.168.1.1",
  "neighbors": [
    {
      "ip": "203.0.113.1",
      "type": "public",
      "relations": ["nat_mapping"]
    },
    {
      "ip": "172.16.0.5",
      "type": "private",
      "relations": ["same_subnet"]
    }
  ],
  "total_neighbors": 2
}
```

> **说明**: 简化版图谱查询，只返回1跳的直接邻居。

---

## 创建 IP 关系

```
POST /api/v1/graph/relation
```

### 请求体

```json
{
  "from_ip": "192.168.1.1",
  "to_ip": "203.0.113.1",
  "relation_type": "nat_mapping",
  "valid_from": "2024-01-01T00:00:00Z",
  "valid_to": null,
  "metadata": {
    "provider": "aws",
    "nat_gateway_id": "nat-xxxxx"
  }
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| from_ip | string | ✅ | 源IP |
| to_ip | string | ✅ | 目标IP |
| relation_type | string | ✅ | 关系类型 |
| valid_from | datetime | ❌ | 生效时间，默认当前时间 |
| valid_to | datetime | ❌ | 失效时间 |
| metadata | object | ❌ | 扩展属性 |

### 支持的关系类型

| 类型 | 说明 |
|------|------|
| nat_mapping | NAT 映射（内网 → 公网） |
| eip_binding | EIP 绑定 |
| same_subnet | 同子网 |
| dns_resolution | DNS 解析 |
| custom | 自定义关系 |

### 响应 (201 Created)

```json
{
  "id": "edge-uuid",
  "from_ip_id": "uuid-1",
  "to_ip_id": "uuid-2",
  "relation_type": "nat_mapping",
  "valid_from": "2024-01-01T00:00:00Z",
  "valid_to": null
}
```

---

## 删除 IP 关系

```
DELETE /api/v1/graph/relation/{relation_id}
```

### 响应 (200 OK)

```json
{
  "message": "Relation invalidated",
  "relation_id": "uuid"
}
```

> **说明**: 软删除，将关系设置为失效（设置 valid_to 为当前时间）。

---

## 列出 IP 关系

```
GET /api/v1/graph/relations?ip_address=192.168.1.1&relation_type=nat_mapping&active_only=true
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| ip_address | string | 过滤指定IP的关系 |
| relation_type | string | 过滤指定类型 |
| active_only | bool | 是否只返回活跃关系，默认 true |

### 响应 (200 OK)

```json
{
  "total": 5,
  "relations": [
    {
      "id": "uuid",
      "from_ip": "192.168.1.1",
      "to_ip": "203.0.113.1",
      "relation_type": "nat_mapping",
      "valid_from": "2024-01-01T00:00:00Z",
      "valid_to": null,
      "metadata": {"provider": "aws"},
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 图谱统计

```
GET /api/v1/graph/stats
```

### 响应 (200 OK)

```json
{
  "total_nodes": 500,
  "total_edges": 1200,
  "type_distribution": {
    "private": 300,
    "public": 150,
    "eip": 50
  },
  "relation_distribution": {
    "nat_mapping": 400,
    "eip_binding": 200,
    "same_subnet": 500,
    "dns_resolution": 100
  },
  "isolated_nodes": 50,
  "connected_nodes": 450
}
```

> **说明**: 包含孤立节点数（没有任何关系的IP）和已连接节点数。