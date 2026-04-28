# Agent 端部署文档

## 1. 概述

Agent 是分布式扫描节点，部署在不同网络环境中，通过不同的出口 IP 执行扫描任务。每个 Agent 独立运行，通过 HTTP 与 Controller 通信。

### Agent 架构特点

- **无状态设计**: Agent 不存储数据，扫描结果全部上报 Controller
- **水平扩展**: 可根据网络环境增减 Agent 数量
- **自动注册**: Agent 首次连接时向 Controller 注册
- **心跳机制**: 每 30 秒发送心跳，超时判定为离线

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
| 原始 Socket | TCP SYN 扫描 | ⚠️ 需要 CAP_NET_RAW |
| ICMP | ICMP 探测 | ❌ 可选 |

> ⚠️ **注意**: TCP SYN 扫描需要 `CAP_NET_RAW` 能力。Docker 部署时需添加 `cap_add: [NET_RAW]`。

---

## 3. Docker 部署（推荐）

### 3.1 前置条件

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
```

### 3.2 在 docker-compose.yml 中添加 Agent

在项目的 `docker-compose.yml` 中添加 Agent 配置：

```yaml
services:
  agent-vpc-a:
    build:
      context: .
      dockerfile: Dockerfile.agent
    environment:
      AGENT_ID: "agent-vpc-a-001"
      AGENT_TOKEN: "从Controller获取的token"
      AGENT_NAME: "VPC-A Scanner"
      CONTROLLER_URL: http://controller:8000
      TCP_MAX_CONCURRENCY: "50"
      UDP_MAX_CONCURRENCY: "20"
      RATE_LIMIT: "1000"
      HEARTBEAT_INTERVAL: "30"
    cap_add:
      - NET_RAW          # SYN 扫描需要
    restart: unless-stopped
    networks:
      - asdp_net
```

> ⚠️ **重要**: 对于分布式部署，Agent 不应和 Controller 在同一个 docker-compose 中，而应独立部署在不同网络环境的机器上。

### 3.3 启动 Agent

```bash
docker-compose up -d agent-vpc-a

# 查看日志
docker-compose logs -f agent-vpc-a
```

---

## 4. 裸机部署

### 4.1 安装 Python

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### 4.2 创建 Agent 运行环境

```bash
cd /opt
sudo mkdir asdp-agent && sudo chown $USER asdp-agent
cd asdp-agent

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 4.3 创建配置文件

```bash
# /opt/asdp-agent/.env
AGENT_ID=agent-vpc-a-001
AGENT_TOKEN=your_secret_token_here
AGENT_NAME=VPC-A Scanner
CONTROLLER_URL=http://controller.example.com:8000

# 扫描参数
TCP_MAX_CONCURRENCY=50
UDP_MAX_CONCURRENCY=20
RATE_LIMIT=1000
TIMEOUT_MS=3000
MAX_RETRIES=3

# 心跳
HEARTBEAT_INTERVAL=30
```

### 4.4 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/asdp-agent.service <<EOF
[Unit]
Description=ASDP Agent - VPC-A
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/asdp-agent
Environment=PATH=/opt/asdp-agent/venv/bin

# 从 .env 文件加载环境变量
EnvironmentFile=/opt/asdp-agent/.env

ExecStart=/opt/asdp-agent/venv/bin/python -m agent.main
Restart=always
RestartSec=10

# 安全加固
NoNewPrivileges=no
CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN
AmbientCapabilities=CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF
```

### 4.5 启动 Agent

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

## 5. 多 Agent 部署方案

### 5.1 不同 VPC 部署

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

### 5.2 各 Agent 配置示例

#### Agent-A (VPC-A 内网扫描)

```bash
AGENT_ID=agent-vpc-a
AGENT_TOKEN=token_a_xxx
AGENT_NAME=VPC-A Internal Scanner
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=100      # 内网延迟低，可以更高并发
UDP_MAX_CONCURRENCY=50
RATE_LIMIT=5000              # 内网可以更高速率
```

#### Agent-B (VPC-B 内网扫描)

```bash
AGENT_ID=agent-vpc-b
AGENT_TOKEN=token_b_xxx
AGENT_NAME=VPC-B Internal Scanner
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=100
UDP_MAX_CONCURRENCY=50
RATE_LIMIT=5000
```

#### Agent-C (DMZ 扫描)

```bash
AGENT_ID=agent-dmz
AGENT_TOKEN=token_c_xxx
AGENT_NAME=DMZ Scanner
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=50
UDP_MAX_CONCURRENCY=20
RATE_LIMIT=1000             # DMZ 可能需要限速
```

#### Agent-D (公网扫描)

```bash
AGENT_ID=agent-internet
AGENT_TOKEN=token_d_xxx
AGENT_NAME=Internet Scanner
CONTROLLER_URL=http://controller.internal:8000
TCP_MAX_CONCURRENCY=20      # 公网限速更严格
UDP_MAX_CONCURRENCY=10
RATE_LIMIT=500              # 防止被防火墙封禁
```

---

## 6. Agent 注册流程

### 6.1 在 Controller 创建 Agent

```bash
curl -X POST http://controller:8000/api/v1/agents/ \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "VPC-A Scanner",
    "description": "部署在VPC-A的扫描节点",
    "network_zone": "vpc-a",
    "max_concurrency": 100,
    "rate_limit": 5000
  }'
```

### 6.2 记录返回的 Token

```json
{
  "code": 200,
  "data": {
    "id": "uuid-agent-id",
    "name": "VPC-A Scanner",
    "token": "secret_token_xxxxx",
    "status": "offline"
  }
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

# 应看到：
{
  "data": [{
    "id": "uuid-agent-id",
    "name": "VPC-A Scanner",
    "status": "online",
    "source_ip": "10.0.0.1",    // Agent 的出口IP
    "last_heartbeat": "2024-01-01T00:00:00Z"
  }]
}
```

---

## 7. 性能调优

### 7.1 并发参数调优

| 参数 | 默认值 | 说明 | 调优建议 |
|------|--------|------|---------|
| TCP_MAX_CONCURRENCY | 50 | TCP 扫描并发数 | 内网可提高到 100-200 |
| UDP_MAX_CONCURRENCY | 20 | UDP 扫描并发数 | UDP 开销大，不建议 > 50 |
| RATE_LIMIT | 1000 | 每秒最大探测数 | 公网建议 < 1000 |
| TIMEOUT_MS | 3000 | 单次探测超时 | 公网可提高到 5000 |
| MAX_RETRIES | 3 | 最大重试次数 | UDP 建议 5 |

### 7.2 网络调优

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

## 8. 故障排查

### 8.1 Agent 无法连接 Controller

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

### 8.2 Agent 心跳超时

```bash
# 检查 Agent 进程
sudo systemctl status asdp-agent

# 检查日志
sudo journalctl -u asdp-agent --since "5 minutes ago"

# 常见原因：
# 1. Agent 进程崩溃
# 2. 网络不稳定
# 3. Agent 正在执行大量扫描，心跳线程被阻塞
```

### 8.3 扫描结果为空

```bash
# 检查 Agent 是否成功拉取任务
sudo journalctl -u asdp-agent | grep "Pulled subtask"

# 检查 Token 是否正确
# Controller 端验证
curl -H "X-Agent-Token: your_token" \
  http://controller:8000/api/v1/tasks/pull

# 常见原因：
# 1. Token 错误（401）
# 2. 没有可用的子任务
# 3. 网络不可达目标 IP
```

### 8.4 扫描速度过慢

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

## 9. 安全加固

### 9.1 Token 安全

```bash
# Token 应存储在加密的配置文件中
chmod 600 /opt/asdp-agent/.env

# 定期轮换 Token
# 在 Controller 创建新 Agent，更新 Agent 配置
```

### 9.2 网络隔离

```bash
# Agent 只允许访问 Controller
# iptables 规则
iptables -A OUTPUT -d controller.example.com -p tcp --dport 8000 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 80,443 -j ACCEPT  # 目标扫描
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT      # DNS
```

### 9.3 日志审计

```bash
# 启用详细日志
AGENT_LOG_LEVEL=DEBUG

# 日志轮转
sudo tee /etc/logrotate.d/asdp-agent <<EOF
/var/log/asdp-agent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
EOF