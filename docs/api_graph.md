# 关系图谱 API

## 查询 IP 关系子图

```
GET /api/v1/graph/ip/{ip_address}?depth=2
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| depth | int | 查询深度，默认 1，最大 3 |

### 响应

```json
{
  "code": 200,
  "data": {
    "center_ip": "192.168.1.1",
    "depth": 2,
    "total_nodes": 8,
    "total_edges": 6,
    "nodes": [
      {
        "id": "uuid-1",
        "ip_address": "192.168.1.1",
        "ip_type": "private",
        "metadata": {"env": "prod"}
      },
      {
        "id": "uuid-2",
        "ip_address": "203.0.113.1",
        "ip_type": "public",
        "metadata": {"provider": "aws"}
      },
      {
        "id": "uuid-3",
        "ip_address": "172.16.0.5",
        "ip_type": "private",
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
      },
      {
        "id": "edge-uuid-2",
        "from": "uuid-1",
        "to": "uuid-3",
        "relation_type": "same_subnet",
        "valid_from": "2024-01-01T00:00:00Z",
        "valid_to": null
      }
    ]
  }
}
```

---

## 创建 IP 关系

```
POST /api/v1/graph/relation
Header: X-API-Key: your_controller_api_key
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
| relation_type | string | ✅ | 关系类型（可扩展） |
| valid_from | datetime | ❌ | 生效时间，默认当前时间 |
| valid_to | datetime | ❌ | 失效时间 |
| metadata | object | ❌ | 附加信息 |

### 支持的关系类型

| 类型 | 说明 |
|------|------|
| nat_mapping | NAT 映射（内网 → 公网） |
| eip_binding | EIP 绑定 |
| same_subnet | 同子网 |
| dns_resolution | DNS 解析 |
| custom | 自定义关系 |

### 响应

```json
{
  "code": 200,
  "data": {
    "id": "edge-uuid",
    "from_ip": "192.168.1.1",
    "to_ip": "203.0.113.1",
    "relation_type": "nat_mapping",
    "valid_from": "2024-01-01T00:00:00Z",
    "valid_to": null,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

## 图谱统计

```
GET /api/v1/graph/stats
```

### 响应

```json
{
  "code": 200,
  "data": {
    "total_ips": 500,
    "total_relations": 1200,
    "ip_type_breakdown": {
      "private": 300,
      "public": 150,
      "eip": 50
    },
    "relation_type_breakdown": {
      "nat_mapping": 400,
      "eip_binding": 200,
      "same_subnet": 500,
      "dns_resolution": 100
    }
  }
}