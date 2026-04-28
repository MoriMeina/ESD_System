# ASDP API 总览

## Base URL

```
http://localhost:8000/api/v1
```

## 认证

### Controller API
所有 Controller API 需要在 Header 中携带 API Key：

```
X-API-Key: your_controller_api_key
```

### Agent API
Agent 上报结果时需要携带 Token：

```
X-Agent-Token: your_agent_token
```

## 响应格式

所有 API 返回 JSON 格式：

```json
{
  "code": 200,
  "data": { ... },
  "message": "success"
}
```

错误响应：

```json
{
  "code": 400,
  "message": "Invalid input"
}
```

## 端点总览

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 健康检查 | `/health` | 服务状态 |
| 任务管理 | `/tasks/` | 扫描任务 CRUD |
| Agent管理 | `/agents/` | Agent 注册/心跳 |
| 扫描结果 | `/results/` | 查询扫描数据 |
| 关系图谱 | `/graph/` | IP 关系查询 |
| 数据导出 | `/export/` | CSV/JSON 导出 |

---

详见各模块文档：

- [任务管理 API](tasks.md)
- [Agent 管理 API](agents.md)
- [扫描结果 API](results.md)
- [关系图谱 API](graph.md)
- [数据导出 API](export.md)