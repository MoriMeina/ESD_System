# ESD System API 总览

## Base URL

```
http://localhost:8000/api/v1
```

## 认证

### Agent API
Agent 上报结果和心跳时需要携带 Token：

```
X-Agent-Token: your_agent_token
```

## 响应格式

所有 API 直接返回 JSON 数据，不使用 `{code, data}` 包装格式。

成功响应示例：

```json
{
  "id": "uuid",
  "name": "task-name",
  "status": "running"
}
```

错误响应（HTTP 状态码 + detail）：

```json
{
  "detail": "Task not found"
}
```

## 端点总览

| 模块 | 路径前缀 | 说明 |
|------|----------|------|
| 任务管理 | `/tasks/` | 扫描任务 CRUD + 结果上报 + Agent拉取 |
| Agent管理 | `/agents/` | Agent 注册/心跳/队列状态 |
| 扫描结果 | `/results/` | 查询扫描数据 |
| 关系图谱 | `/graph/` | IP 关系查询 |
| 数据导出 | `/export/` | CSV/JSON 导出 |

---

详见各模块文档：

- [任务管理 API](api_tasks.md)
- [Agent 管理 API](api_agents.md)
- [扫描结果 API](api_results.md)
- [关系图谱 API](api_graph.md)
- [数据导出 API](api_export.md)