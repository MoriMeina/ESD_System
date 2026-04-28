# 添加 Agent 操作指南

## 1. 概述

本文档介绍如何添加一个新的扫描 Agent。添加 Agent 分两步：
1. **在 Controller 创建 Agent 记录** - 获取 `AGENT_ID` 和 `AGENT_TOKEN`
2. **在目标机器部署 Agent** - 使用获取的凭证启动 Agent

---

## 2. 通过 Web 界面创建 Agent

### 2.1 进入 Agent 管理页面

1. 打开浏览器访问系统
2. 点击导航栏 **"Agent管理"** 标签

### 2.2 填写创建表单

点击 **"+ 创建Agent"** 按钮，填写以下信息：

| 字段 | 说明 | 示例 | 是否必填 |
|------|------|------|---------|
| Agent名称 | 唯一名称，用于识别该Agent | `VPC-A Scanner` | ✅ |
| 描述 | 自由文本说明 | `部署在VPC-A的扫描节点` | ❌ |
| 网络区域 | 网络区域标识 | `vpc-a` / `dmz` / `internet` | ❌ |
| 最大并发 | 该Agent最大扫描并发数 | `100` | ❌ (默认50) |
| 速率限制 | 每秒最大扫描数 | `5000` | ❌ (默认1000) |

### 2.3 记录 Agent 凭据

创建成功后，在 Agent 列表中可以看到：

| 列 | 说明 |
|----|------|
| ID | **这是 `AGENT_ID`**，复制下来用于配置 |
| Token | **这是 `AGENT_TOKEN`**（完整 token 在数据库，界面只显示前12位） |
| 状态 | 初始为 `offline`，Agent 启动后变为 `online` |

> ⚠️ **Token 完整查看**: 界面只显示 Token 前12位。如需查看完整 Token，请通过 API 或数据库查询。

---

## 3. 通过 API 创建 Agent

### 3.1 创建 Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "VPC-A Scanner",
    "description": "部署在VPC-A的扫描节点",
    "network_zone": "vpc-a",
    "max_concurrency": 100,
    "rate_limit": 5000
  }'
```

### 3.2 记录返回结果

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "VPC-A Scanner",
  "token": "hashed_token_xxxxxxxxxxxxxxxx",
  "description": "部署在VPC-A的扫描节点",
  "network_zone": "vpc-a",
  "status": "offline",
  "max_concurrency": 100,
  "rate_limit": 5000,
  "source_ip": null,
  "last_heartbeat": null,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

**需要记录的值：**
- `AGENT_ID` = `"id"` 字段的值
- `AGENT_TOKEN` = `"token"` 字段的值

### 3.3 列出已有 Agent

```bash
curl http://localhost:8000/api/v1/agents/
```

### 3.4 获取单个 Agent 详情（含完整 Token）

```bash
curl http://localhost:8000/api/v1/agents/550e8400-e29b-41d4-a716-446655440000
```

---

## 4. 通过数据库查看 Agent Token

如果忘记 Token，可以直接查询数据库：

```bash
# 连接数据库
psql -h localhost -U asdp -d asdp

# 查看所有 Agent 的 ID 和 Token
SELECT id, name, token, status, network_zone FROM agents;

# 查看特定 Agent
SELECT id, name, token FROM agents WHERE name = 'VPC-A Scanner';
```

输出示例：
```
                  id                  |     name      |         token          | status  | network_zone
--------------------------------------+---------------+------------------------+---------+--------------
 550e8400-e29b-41d4-a716-446655440000 | VPC-A Scanner | $2a$12$hashed_token... | offline | vpc-a
```

---

## 5. 部署 Agent

### 5.1 Docker Compose 方式

在目标机器的 `docker-compose.yml` 中添加 Agent 服务：

```yaml
version: '3.8'

services:
  agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
    environment:
      # 从 Controller 获取的值
      AGENT_ID: "550e8400-e29b-41d4-a716-446655440000"
      AGENT_TOKEN: "hashed_token_xxxxxxxxxxxxxxxx"
      
      # 可选配置
      AGENT_NAME: "VPC-A Scanner"
      CONTROLLER_URL: http://controller:8000
      
      # 扫描参数
      TCP_MAX_CONCURRENCY: "100"
      UDP_MAX_CONCURRENCY: "50"
      RATE_LIMIT: "5000"
    restart: unless-stopped
```

启动：
```bash
docker-compose up -d agent
docker-compose logs -f agent
```

### 5.2 裸机方式

```bash
# 创建目录和虚拟环境
sudo mkdir -p /opt/asdp-agent
cd /opt/asdp-agent
python3.11 -m venv venv
source venv/bin/activate
pip install httpx pydantic

# 复制 agent 代码
cp -r /path/to/ESD_System/agent .

# 创建环境变量文件
cat > .env <<'EOF'
# Agent 身份（必填）
AGENT_ID=550e8400-e29b-41d4-a716-446655440000
AGENT_TOKEN=hashed_token_xxxxxxxxxxxxxxxx

# Controller 地址
CONTROLLER_URL=http://controller:8000
AGENT_NAME=VPC-A Scanner

# 扫描参数
TCP_TIMEOUT_MS=3000
TCP_MAX_CONCURRENCY=100
UDP_MAX_CONCURRENCY=50
RATE_LIMIT=5000

# 心跳和任务拉取
HEARTBEAT_INTERVAL=30
POLL_INTERVAL=2.0

# 日志
LOG_LEVEL=INFO
EOF

# 配置 systemd
sudo tee /etc/systemd/system/asdp-agent.service <<'EOF'
[Unit]
Description=ASDP Scanner Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/asdp-agent
EnvironmentFile=/opt/asdp-agent/.env
ExecStart=/opt/asdp-agent/venv/bin/python -m agent.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启动
sudo systemctl daemon-reload
sudo systemctl enable asdp-agent
sudo systemctl start asdp-agent
```

---

## 6. 验证 Agent 运行

### 6.1 检查 Agent 日志

```bash
# Docker 方式
docker-compose logs -f agent

# systemd 方式
sudo journalctl -u asdp-agent -f
```

**正常日志示例：**
```
2024-01-15 10:30:05 - agent - INFO - ASDP Agent starting (id=550e8400-...)
2024-01-15 10:30:05 - agent - INFO - Source IP detected: 10.0.1.50
2024-01-15 10:30:05 - agent - INFO - Heartbeat loop started
2024-01-15 10:30:05 - agent - INFO - Task poll loop started
2024-01-15 10:30:05 - agent - DEBUG - Heartbeat sent successfully
```

### 6.2 在 Web 界面检查

1. 进入 **"Agent管理"** 页面
2. 确认 Agent 状态从 `offline` 变为 `online`
3. 确认 `出口IP` 已显示
4. 确认 `最后心跳` 时间正在更新

### 6.3 通过 API 检查

```bash
# 查看 Agent 列表
curl http://localhost:8000/api/v1/agents/

# 查看单个 Agent
curl http://localhost:8000/api/v1/agents/550e8400-e29b-41d4-a716-446655440000

# 查看队列状态
curl http://localhost:8000/api/v1/agents/550e8400-e29b-41d4-a716-446655440000/queue
```

**正常响应：**
```json
{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_name": "VPC-A Scanner",
  "status": "online",
  "is_online": true,
  "queue_length": 0
}
```

---

## 7. Agent 管理操作

### 7.1 禁用 Agent

```bash
# API 方式
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/disable

# Web 方式：点击 Agent 列表中的 "禁用" 按钮
```

禁用后 Agent 将无法拉取新任务，但已完成的任务结果仍可上报。

### 7.2 启用 Agent

```bash
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/enable
```

启用后 Agent 状态变为 `offline`，等待心跳后变为 `online`。

### 7.3 轮换 Token

如果需要更换 Agent Token（安全轮换）：

```sql
-- 在数据库中直接更新
UPDATE agents SET token = crypt(gen_random_bytes(32), gen_salt('bf'))
WHERE id = '550e8400-e29b-41d4-a716-446655440000';

-- 查看新 Token
SELECT id, name, token FROM agents WHERE id = '550e8400-e29b-41d4-a716-446655440000';
```

然后更新 Agent 机器上的配置：
```bash
# 更新 .env 中的 AGENT_TOKEN
# 重启 Agent
sudo systemctl restart asdp-agent
```

---

## 8. 常见场景

### 8.1 新增网络区域的扫描能力

**场景**: 需要在新的 VPC-B 区域扫描该区域的内网资产

**步骤**:
1. 在 VPC-B 中准备一台机器（或容器）
2. 通过 API 创建 Agent（`network_zone: "vpc-b"`）
3. 记录返回的 `id` 和 `token`
4. 在 VPC-B 机器上部署 Agent
5. 验证 Agent 上线，出口 IP 为 VPC-B 内网 IP

### 8.2 替换故障 Agent

**场景**: 某个 Agent 机器故障，需要迁移到新机器

**步骤**:
1. 在新机器上部署 Agent（使用相同的 `AGENT_ID` 和 `AGENT_TOKEN`）
2. 旧 Agent 心跳超时后自动变为 `offline`
3. 新 Agent 发送心跳后变为 `online`
4. 原 IP 不同可能导致已有任务的扫描结果来自新 IP

### 8.3 为已有 Agent 调整性能参数

```bash
# 只需修改 Agent 机器上的环境变量，重启即可
# .env
TCP_MAX_CONCURRENCY=200   # 从 100 提升到 200
RATE_LIMIT=10000          # 从 5000 提升到 10000

sudo systemctl restart asdp-agent
```

> ⚠️ **注意**: `max_concurrency` 和 `rate_limit` 在数据库中有记录，但 Agent 实际运行参数读取的是环境变量。如需同步更新数据库：
>
> ```sql
> UPDATE agents SET max_concurrency = 200, rate_limit = 10000
> WHERE id = 'agent-id';
> ```

---

## 9. 故障排查

### 9.1 Token 认证失败 (401)

```
ERROR - Heartbeat error: 401 Unauthorized
```

**排查**:
```bash
# 1. 确认 AGENT_TOKEN 正确
echo $AGENT_TOKEN

# 2. 在数据库中验证
psql -h localhost -U asdp -d asdp -c "SELECT id, name, token FROM agents WHERE id = 'your-agent-id';"

# 3. 手动测试 Token
curl -X POST http://localhost:8000/api/v1/agents/your-agent-id/heartbeat \
  -H "X-Agent-Token: your-token" \
  -H "Content-Type: application/json" \
  -d '{"source_ip": "10.0.1.50", "stats": {}}'
```

### 9.2 Agent ID 不匹配 (403)

```
ERROR - Heartbeat error: 403 Token does not match agent
```

**原因**: `AGENT_ID` 环境变量与 URL 中的 agent_id 不匹配，或 Token 属于另一个 Agent。

**解决**: 确认 `AGENT_ID` 环境变量与创建时返回的 `id` 一致。

### 9.3 Agent 持续显示 offline

```bash
# 检查 Agent 日志中是否有错误
sudo journalctl -u asdp-agent --since "5 minutes ago"

# 检查网络连通性
curl -v http://controller:8000/health

# 检查 Agent 进程是否存活
sudo systemctl status asdp-agent
```

### 9.4 出口 IP 不正确

```bash
# 查看 Agent 日志中的 Source IP
sudo journalctl -u asdp-agent | grep "Source IP detected"

# 手动验证出口 IP
curl ifconfig.me
```

---

## 10. 完整添加流程检查清单

- [ ] 在 Controller 创建 Agent（API 或 Web 界面）
- [ ] 记录返回的 `id`（AGENT_ID）
- [ ] 记录返回的 `token`（AGENT_TOKEN）
- [ ] 在目标机器准备运行环境（Docker 或裸机）
- [ ] 配置 `AGENT_ID` 和 `AGENT_TOKEN` 环境变量
- [ ] 配置 `CONTROLLER_URL` 指向 Controller
- [ ] 启动 Agent
- [ ] 查看 Agent 日志确认心跳成功
- [ ] 在 Web 界面确认 Agent 状态为 `online`
- [ ] 创建测试任务验证扫描功能