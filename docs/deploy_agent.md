# Agent 端部署文档

## 1. 概述

Agent 是分布式扫描节点，部署在不同网络环境中，通过不同的出口 IP 执行扫描任务。每个 Agent 独立运行，通过 HTTP 与 Controller 通信。

### Agent 架构特点

- **无状态设计**: Agent 不存储数据，扫描结果全部上报 Controller
- **水平扩展**: 可根据网络环境增减 Agent 数量
- **自动注册**: Agent 首次连接时向 Controller 注册
- **心跳机制**: 每 30 秒发送心跳，超时判定为离线
- **任务拉取**: Agent 主动轮询（默认 2 秒间隔）从 Controller 拉取任务
- **批量上报**: 扫描结果缓冲到 100 条后批量上报，减少网络开销

---

## 2. 环境要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 1 核 | 2+ 核 |
| 内存 | 512 MB | 2 GB |
| 磁盘 | 10 GB | 20 GB |
| 网络 | 100 Mbps | 1 Gbps（出口带宽决定扫描速度） |
| 操作系统 | Ubuntu 20.04+ / Debian 11+ | Ubuntu 22.04 LTS |

### 网络权限

| 权限 | 说明 | 是否必须 |
|------|------|---------|
| 出站 HTTP | 访问 Controller API | ✅ 必须 |
| 出站 TCP | TCP CONNECT 扫描 | ✅ 必须 |
| 出站 UDP | UDP 扫描 | ✅ 必须 |

> ⚠️ **注意**: 当前 Agent 默认使用 TCP CONNECT 扫描模式。如需 TCP SYN 扫描需要 `CAP_NET_RAW` 能力。

---

## 3. Docker Compose 部署（推荐）

### 3.1 前置条件

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 3.2 启动服务

Agent 配置已包含在项目 `docker-compose.yml` 中（`agent-1` 和 `agent-2` 两个示例）：

```bash
# 启动所有服务（含 Agent）
docker-compose up -d

# 仅启动 Agent-1
docker-compose up -d agent-1

# 查看 Agent 日志
docker-compose logs -f agent-1
```

### 3.3 配置 Agent

Agent 通过环境变量配置，在 `docker-compose.yml` 中修改：

```yaml
services:
  agent-1:
    build:
      context: .
      dockerfile: Dockerfile.agent
    environment:
      AGENT_ID: ${AGENT_1_ID:-agent-001}
      AGENT_TOKEN: ${AGENT_1_TOKEN:-token_agent_1_secret}
      AGENT_NAME: "Agent-A (Network A)"
      CONTROLLER_URL: http://controller:8000
      TCP_MAX_CONCURRENCY: "50"
      UDP_MAX_CONCURRENCY: "20"
      RATE_LIMIT: "1000"
```

可通过 `.env` 文件覆盖默认值：

```bash
# .env
AGENT_1_ID=your-agent-id-uuid
AGENT_1_TOKEN=your-secret-token
```

> ⚠️ **重要**: `AGENT_ID` 和 `AGENT_TOKEN` 必须在 Controller 创建 Agent 后获取，详见第 6 节。

---

## 4. 独立机器 Docker 部署

对于分布式部署，Agent 应独立部署在不同网络环境的机器上。

### 4.1 准备代码

```bash
# 克隆项目
git clone <repository-url>
cd ESD_System
```

### 4.2 创建 docker-compose

只需 Agent 服务（不需要 Controller/数据库）：

```yaml
# docker-compose.agent.yml
version: '3.8'

services:
  agent:
    build:
      context: .
      dockerfile: Dockerfile.agent
    environment:
      AGENT_ID: "your-agent-id-uuid"
      AGENT_TOKEN: "your-secret-token"
      AGENT_NAME: "VPC-A Scanner"
      CONTROLLER_URL: http://controller.example.com:8000
      TCP_MAX_CONCURRENCY: "50"
      UDP_MAX_CONCURRENCY: "20"
      RATE_LIMIT: "1000"
      HEARTBEAT_INTERVAL: "30"
    restart: unless-stopped
```

### 4.3 启动

```bash
docker-compose -f docker-compose.agent.yml up -d
docker-compose -f docker-compose.agent.yml logs -f
```

---

## 5. 裸机部署

### 5.1 安装 Python

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### 5.2 创建 Agent 运行环境

```bash
cd /opt
sudo mkdir asdp-agent && sudo chown $USER asdp-agent
cd asdp-agent

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖（仅需 httpx 和 pydantic）
pip install httpx pydantic
```

### 5.3 创建配置文件

```bash
# /opt/asdp-agent/.env
AGENT_ID=your-agent-id-uuid
AGENT_TOKEN=your-secret-token
AGENT_NAME=VPC-A Scanner
CONTROLLER_URL=http://controller.example.com:8000

# 扫描参数
TCP_TIMEOUT_MS=3000
TCP_MAX_CONCURRENCY=50
TCP_SCAN_TYPE=connect
UDP_TIMEOUT_MS=5000
UDP_MAX_RETRIES=5
UDP_RETRY_DELAY_MS=1000
UDP_MAX_CONCURRENCY=20
RATE_LIMIT=1000
BANNER_READ_TIMEOUT_MS=2000
BANNER_MAX_BYTES=1024

# 心跳
HEARTBEAT_INTERVAL=30

# 任务拉取
POLL_INTERVAL=2.0

# 结果上报
REPORT_BATCH_SIZE=100
REPORT_INTERVAL=5.0

# 日志
LOG_LEVEL=INFO
```

### 5.4 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/asdp-agent.service <<'EOF'
[Unit]
Description=ESD System Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/asdp-agent
Environment=PATH=/opt/asdp-agent/venv/bin
EnvironmentFile=/opt/asdp-agent/.env
ExecStart=/opt/asdp-agent/venv/bin/python -m agent.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 5.5 启动 Agent

```bash
# 启动
sudo systemctl daemon-reload
sudo systemctl enable asdp-agent
sudo systemctl start asdp-agent

# 查看状态
sudo systemctl status asdp-agent

# 查看日志
sudo journalctl -u asdp-agent -f
```

---

## 6. Agent 注册流程

### 6.1 在 Controller 创建 Agent

```bash
curl -X POST http://controller:8000/api/v1/agents/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "VPC-A Scanner",
    "description": "部署在VPC-A的扫描节点",
    "network_zone": "vpc-a",
    "max_concurrency": 100,
    "rate_limit": 5000
  }'
```

### 6.2 记录返回的 ID 和 Token

```json
{
  "id": "uuid-agent-id",
  "name": "VPC-A Scanner",
  "token": "secret_token_xxxxx",
  "status": "offline"
}
```

### 6.3 配置 Agent 环境变量

```bash
AGENT_ID=uuid-agent-id
AGENT_TOKEN=secret_token_xxxxx
```

### 6.4 启动 Agent 验证

```bash
# Agent 启动后会自动发送心跳
# 在 Controller 验证 Agent 状态
curl http://controller:8000/api/v1/agents/

# 应看到 Agent 状态为 online（心跳更新后）
```

---

## 7. 环境变量参考

### 必需配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AGENT_ID` | Agent唯一ID（从Controller获取） | 无 |
| `AGENT_TOKEN` | Agent认证Token（从Controller获取） | 无 |

### Controller 连接

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CONTROLLER_URL` | Controller API地址 | `http://localhost:8000` |
| `AGENT_NAME` | Agent显示名称 | `default-agent` |

### TCP 扫描

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TCP_TIMEOUT_MS` | 单次TCP探测超时(ms) | `3000` |
| `TCP_MAX_CONCURRENCY` | TCP扫描并发数 | `50` |
| `TCP_SCAN_TYPE` | 扫描类型: connect/syn | `connect` |

### UDP 扫描

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `UDP_TIMEOUT_MS` | 单次UDP探测超时(ms) | `5000` |
| `UDP_MAX_RETRIES` | UDP最大重试次数 | `5` |
| `UDP_RETRY_DELAY_MS` | UDP重试延迟(ms) | `1000` |
| `UDP_MAX_CONCURRENCY` | UDP扫描并发数 | `20` |

### 通用

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `RATE_LIMIT` | 每秒最大探测数 | `1000` |
| `BANNER_READ_TIMEOUT_MS` | Banner读取超时(ms) | `2000` |
| `BANNER_MAX_BYTES` | Banner最大读取字节数 | `1024` |

### 心跳和任务拉取

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HEARTBEAT_INTERVAL` | 心跳间隔(秒) | `30` |
| `POLL_INTERVAL` | 任务拉取间隔(秒) | `2.0` |

### 结果上报

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `REPORT_BATCH_SIZE` | 批量上报大小 | `100` |
| `REPORT_INTERVAL` | 上报间隔(秒) | `5.0` |

### 日志

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LOG_LEVEL` | 日志级别: DEBUG/INFO/WARNING/ERROR | `INFO` |

---

## 8. 多 Agent 部署方案

### 8.1 不同网络区域部署

```
                    ┌─────────────────────────────────┐
                    │        Controller (中心)          │
                    │  PostgreSQL + ClickHouse + Redis  │
                    └──────────┬──────────┬────────────┘
                               │          │
                    ┌──────────┘          └──────────┐
                    ▼                                  ▼
          ┌─────────────────┐              ┌─────────────────┐
          │   VPC-A         │              │   VPC-B         │
          │                 │              │                 │
          │  Agent-A        │              │  Agent-B        │
          │  出口: 10.0.0.1  │              │  出口: 172.16.0.1│
          │  扫描内网 A 段   │              │  扫描内网 B 段   │
          └─────────────────┘              └─────────────────┘
                    │                                  │
                    ▼                                  ▼
          ┌─────────────────┐              ┌─────────────────┐
          │   DMZ           │              │   Internet      │
          │                 │              │                 │
          │  Agent-C        │              │  Agent-D        │
          │  出口: DMZ IP    │              │  出口: 公网 IP   │
          │  扫描DMZ资产    │              │  扫描公网资产   │
          └─────────────────┘              └─────────────────┘
```

### 8.2 各 Agent 配置示例

#### Agent-A (VPC-A 内网扫描)

```bash
AGENT_ID=agent-vpc-a
AGENT_TOKEN=token_a_xxx
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=100      # 内网延迟低，可以更高并发
UDP_MAX_CONCURRENCY=50
RATE_LIMIT=5000              # 内网可以更高速率
```

#### Agent-B (VPC-B 内网扫描)

```bash
AGENT_ID=agent-vpc-b
AGENT_TOKEN=token_b_xxx
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=100
UDP_MAX_CONCURRENCY=50
RATE_LIMIT=5000
```

#### Agent-C (DMZ 扫描)

```bash
AGENT_ID=agent-dmz
AGENT_TOKEN=token_c_xxx
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=50
UDP_MAX_CONCURRENCY=20
RATE_LIMIT=1000             # DMZ 可能需要限速
```

#### Agent-D (公网扫描)

```bash
AGENT_ID=agent-internet
AGENT_TOKEN=token_d_xxx
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=20      # 公网限速更严格
UDP_MAX_CONCURRENCY=10
RATE_LIMIT=500              # 防止被防火墙封禁
```

---

## 9. 性能调优

### 9.1 并发参数调优

| 参数 | 默认值 | 说明 | 调优建议 |
|------|--------|------|---------|
| TCP_MAX_CONCURRENCY | 50 | TCP 扫描并发数 | 内网可提高到 100-200 |
| UDP_MAX_CONCURRENCY | 20 | UDP 扫描并发数 | UDP 开销大，不建议 > 50 |
| RATE_LIMIT | 1000 | 每秒最大探测数 | 公网建议 < 1000 |
| TCP_TIMEOUT_MS | 3000 | TCP探测超时 | 公网可提高到 5000 |
| UDP_MAX_RETRIES | 5 | UDP最大重试次数 | 根据网络稳定性调整 |
| REPORT_BATCH_SIZE | 100 | 批量上报大小 | 网络差时可增大到 500 |

### 9.2 网络调优

```bash
# 增加文件描述符限制
sudo sysctl -w fs.file-max=1000000
echo "* soft nofile 100000" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 100000" | sudo tee -a /etc/security/limits.conf

# 优化 TCP 参数
sudo sysctl -w net.ipv4.tcp_fin_timeout=15
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
sudo sysctl -w net.core.somaxconn=65535
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
```

---

## 10. 故障排查

### 10.1 Agent 无法连接 Controller

```bash
# 检查网络连通性
ping controller.example.com
telnet controller.example.com 8000

# 检查 Agent 日志
sudo journalctl -u asdp-agent -n 100

# 常见原因：
# 1. CONTROLLER_URL 配置错误
# 2. 防火墙阻断了出站连接
# 3. DNS 解析失败
```

### 10.2 Agent 心跳超时

```bash
# 检查 Agent 进程
sudo systemctl status asdp-agent

# 检查日志
sudo journalctl -u asdp-agent --since "5 minutes ago"

# 常见原因：
# 1. Agent 进程崩溃
# 2. 网络不稳定
# 3. Agent 正在执行大量扫描
```

### 10.3 扫描结果为空

```bash
# 检查 Agent 是否成功拉取任务
sudo journalctl -u asdp-agent | grep "Received task"

# 检查 Token 是否正确
curl -H "X-Agent-Token: your_token" \
  http://controller:8000/api/v1/tasks/pull/agent-id

# 常见原因：
# 1. Token 错误（401）
# 2. 没有可用的任务
# 3. 网络不可达目标 IP
```

### 10.4 扫描速度过慢

```bash
# 检查系统资源
top
free -h
ss -s

# 检查网络延迟
ping -c 10 target_ip

# 提高并发参数
TCP_MAX_CONCURRENCY=200
RATE_LIMIT=5000
```

---

## 11. 安全加固

### 11.1 Token 安全

```bash
# Token 应存储在加密的配置文件中
chmod 600 /opt/asdp-agent/.env

# 定期轮换 Token
# 在 Controller 创建新 Agent，更新 Agent 配置
```

### 11.2 网络隔离

```bash
# Agent 只允许访问 Controller 和目标扫描网段
# iptables 规则示例
iptables -A OUTPUT -d controller.example.com -p tcp --dport 8000 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 80,443 -j ACCEPT  # 目标扫描
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT      # DNS
```

### 11.3 日志审计

```bash
# 启用详细日志
LOG_LEVEL=DEBUG

# 日志轮转
sudo tee /etc/logrotate.d/asdp-agent <<'EOF'
/var/log/asdp-agent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
EOF