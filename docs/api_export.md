# 数据导出 API

## 导出 CSV

```
GET /api/v1/export/csv?target_ip=192.168.1.1&start_time=2024-01-01T00:00:00Z&end_time=2024-01-02T00:00:00Z
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| target_ip | string | 目标IP过滤（可选） |
| source_ip | string | 探测源IP过滤（可选） |
| port | int | 端口过滤（可选） |
| protocol | enum | tcp/udp（可选） |
| status | enum | open/closed/filtered/unknown（可选） |
| start_time | string | 开始时间 ISO 8601（可选） |
| end_time | string | 结束时间 ISO 8601（可选） |

### 响应

返回 CSV 文件流：

```csv
task_id,agent_id,source_ip,target_ip,port,protocol,status,latency_ms,banner,retry_count,error_message,scanned_at
uuid,uuid,10.0.0.1,192.168.1.1,80,tcp,open,1.5,Apache/2.4,0,,2024-01-01T00:00:00Z
uuid,uuid,10.0.0.1,192.168.1.1,443,tcp,open,2.1,nginx/1.24,0,,2024-01-01T00:00:00Z
uuid,uuid,10.0.0.1,192.168.1.1,53,udp,filtered,5000.0,,5,no_response_after_retries,2024-01-01T00:00:00Z
```

---

## 导出 JSON

```
GET /api/v1/export/json?target_ip=192.168.1.1
```

### 参数

与 CSV 导出相同。

### 响应

```json
{
  "total": 3,
  "exported_at": "2024-01-01T00:10:00Z",
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
      "retry_count": 0,
      "error_message": null,
      "scanned_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

---

## 导出 IP 关系

```
GET /api/v1/export/relations?format=csv
```

### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| format | enum | csv/json，默认 csv |
| relation_type | string | 关系类型过滤（可选） |

### CSV 响应

```csv
id,from_ip,to_ip,relation_type,valid_from,valid_to,metadata
edge-uuid,192.168.1.1,203.0.113.1,nat_mapping,2024-01-01T00:00:00Z,,{"provider":"aws"}