# 分布式暴露面检测平台（ASDP）架构设计

## 📋 目录

1. [系统概述](#系统概述)
2. [整体架构](#整体架构)
3. [组件详解](#组件详解)
4. [数据模型](#数据模型)
5. [核心流程](#核心流程)
6. [关键设计决策](#关键设计决策)
7. [API设计](#api设计)
8. [部署架构](#部署架构)

---

## 系统概述

### 项目定位

分布式暴露面检测平台（Attack Surface Detection Platform, ASDP）是一个**企业级资产测绘与关系建模系统**，用于：

- 从多网络视角探测资产暴露面
- 构建IP资产关系图谱
- 可视化分析与导出

### 核心特性

| 特性 | 说明 |
|------|------|
| 分布式扫描 | 支持多Agent协同，不同网络视角 |
| 关系建模 | 图结构IP关系建模，支持NAT/EIP映射 |
| 多协议支持 | TCP/UDP/ICMP，UDP支持unknown/filtered状态 |
| 结果去重 | 多Agent结果去重与聚合 |
| 实时追踪 | WebSocket实时进度推送 |
| 水平扩展 | Agent无状态设计，可无限扩展 |

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Web 前端                                  │
│                    (Vue 3 + TypeScript + ECharts)                   │
└──────────────┬──────────────────────────────────────┬───────────────┘
               │ HTTP/WS                              │ HTTP
               ▼                                      ▼
┌──────────────────────────┐              ┌──────────────────────┐
│   Controller (API Server)│              │   Auth Service       │
│                          │              │   (JWT + RBAC)       │
│  ┌────────────────────┐  │              └──────────────────────┘
│  │   Task Scheduler   │  │
│  ├────────────────────┤  │        ┌──────────────────────┐
│  │   Result Aggregator│◄─┤────────│   PostgreSQL         │
│  │   (去重+聚合)      │  │        │   (关系数据)          │
│  ├────────────────────┤  │        └──────────────────────┘
│  │   IP Graph Engine  │  │        ┌──────────────────────┐
│  │   (关系建模)       │  │        │   ClickHouse         │
│  ├────────────────────┤  │        │   (扫描结果)          │
│  │   API Router       │  │        └──────────────────────┘
│  └──────────┬─────────┘  │        ┌──────────────────────┐
└─────────────┼────────────┘        │   Redis              │
              │                     │   (队列+缓存+心跳)    │
              │ TCP/HTTP            └──────────────────────┘
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent 网络                                    │
│                                                                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│   │  Agent-1 │    │  Agent-2 │    │  Agent-N │                   │
│   │ (出口IP1)│    │ (出口IP2)│    │ (出口IPN)│                   │
│   │          │    │          │    │          │                   │
│   │ Scanner  │    │ Scanner  │    │ Scanner  │                   │
│   │ Engine   │    │ Engine   │    │ Engine   │                   │
│   └──────────┘    └──────────┘    └──────────┘                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 组件详解

### 1. Controller（中心控制端）

**技术栈**: FastAPI (Python 3.10+)

**核心模块**:

```
controller/
├── api/                  # API路由层
│   ├── tasks.py         # 任务管理API
│   ├── results.py       # 结果查询API
│   ├── graph.py         # 图谱查询API
│   ├── agents.py        # Agent管理API
│   └── export.py        # 数据导出API
├── core/                 # 核心业务层
│   ├── scheduler.py     # 任务调度器
│   ├── aggregator.py    # 结果聚合器（去重+合并）
│   ├── graph_engine.py  # IP关系图引擎
│   └── auth.py          # 鉴权中间件
├── models/               # 数据模型
│   ├── task.py          # 任务模型
│   ├── result.py        # 扫描结果模型
│   ├── ip_asset.py      # IP资产模型
│   └── ip_relation.py   # IP关系模型
├── services/             # 服务层
│   ├── queue_service.py  # Redis队列服务
│   ├── storage_service.py# 存储服务
│   └── ws_service.py     # WebSocket服务
└── config.py             # 配置管理
```

### 2. Agent（分布式扫描节点）

**技术栈**: Python 3.10+ (独立进程)

**核心模块**:

```
agent/
├── scanner/              # 扫描引擎
│   ├── tcp_scanner.py   # TCP扫描器（SYN/CONNECT）
│   ├── udp_scanner.py   # UDP扫描器（弱探测）
│   └── icmp_scanner.py  # ICMP探测
├── engine/               # 执行引擎
│   ├── executor.py      # 任务执行器
│   ├── rate_limiter.py  # 速率限制器
│   └── retry_handler.py # 重试处理器
├── reporter/             # 结果上报
│   └── http_reporter.py # HTTP上报客户端
├── heartbeat/            # 心跳机制
│   └── heartbeat.py     # 心跳发送器
└── config.py             # Agent配置
```

### 3. Web 前端

**技术栈**: Vue 3 + TypeScript + Vite + ECharts

```
frontend/
├── src/
│   ├── views/
│   │   ├── Dashboard.vue      # 总览仪表板
│   │   ├── TaskView.vue       # 任务管理
│   │   ├── AssetView.vue      # 资产管理
│   │   ├── GraphView.vue      # IP关系图谱
│   │   └── ExportView.vue     # 数据导出
│   ├── components/
│   │   ├── IpGraph.vue        # IP关系图组件
│   │   ├── ScanChart.vue      # 扫描统计图表
│   │   └── Timeline.vue       # 时间线组件
│   ├── services/
│   │   ├── api.ts             # API客户端
│   │   └── websocket.ts       # WebSocket客户端
│   └── types/                 # TypeScript类型定义
```

---

## 数据模型

### 数据库选择理由

| 数据库 | 用途 | 理由 |
|--------|------|------|
| PostgreSQL | 关系数据 | IP资产、关系、Agent信息、任务元数据 |
| ClickHouse | 扫描结果 | 高吞吐写入、高效聚合查询、时序数据 |
| Redis | 队列+缓存 | 任务队列、Agent心跳、实时缓存 |

### ER图

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   agents     │       │     tasks        │       │   ip_assets  │
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ id          │       │ id               │       │ id           │
│ name        │───┐   │ name             │       │ ip_address   │
│ token       │   │   │ target_ips[]     │       │ ip_type      │
│ status      │   │   │ port_range       │       │ metadata     │
│ heartbeat   │   │   │ protocol         │       │ discovered   │
│ created_at  │   │   │ status           │       │ updated_at   │
└──────────────┘   │   │ created_at       │       └──────┬───────┘
                   │   └────────┬─────────┘              │
                   │            │                         │
                   │            ▼                         │
                   │   ┌──────────────────┐       ┌──────▼───────┐
                   │   │  task_assignments│       │ ip_relations │
                   │   ├──────────────────┤       ├──────────────┤
                   │   │ task_id    ──────┤       │ from_ip_id   │
                   │   │ agent_id   ──────┤───────│ to_ip_id     │
                   │   │ assigned_at      │       │ relation_type│
                   │   │ status           │       │ valid_from   │
                   │   └──────────────────┘       │ valid_to     │
                   │                              │ metadata     │
                   │                              └──────────────┘
                   │
                   ▼
           ┌──────────────────┐
           │  scan_results    │  ← ClickHouse表
           ├──────────────────┤
           │ task_id          │
           │ agent_id         │
           │ source_ip        │  ← 探测出口IP
           │ target_ip        │
           │ port             │
           │ protocol         │
           │ status           │  ← open/closed/filtered/unknown
           │ latency_ms       │
           │ banner           │
           │ scanned_at       │
           └──────────────────┘
```

---

## 核心流程

### 1. 分布式扫描流程

```
用户创建任务
     │
     ▼
Controller: 创建任务记录 → 拆分任务子任务
     │
     ▼
Controller: 分发到Redis队列（按Agent分组）
     │
     ▼
Agent: 从队列获取任务
     │
     ▼
Agent: 执行扫描（TCP/UDP）
     │    ├─ TCP: connect扫描（可靠）
     │    ├─ UDP: 弱探测 + 重试（处理不可靠）
     │    └─ 速率限制 + 超时控制
     │
     ▼
Agent: 上报结果 → Controller
     │
     ▼
Controller: 结果去重 → 写入ClickHouse
     │
     ▼
Controller: 更新任务状态
     │
     ▼
WebSocket: 推送进度到前端
```

### 2. UDP扫描可靠性处理

```
UDP探测流程:
┌─────────────┐
│ 发送UDP包   │
└──────┬──────┘
       ▼
┌─────────────┐     是      ┌─────────────┐
│ 收到响应?   │─────────────▶│ status=open │
└──────┬──────┘              └─────────────┘
       │ 否
       ▼
┌─────────────┐     是      ┌─────────────┐
│ 收到ICMP    │─────────────▶│ status=     │
│ Unreachable?│              │ closed      │
└──────┬──────┘              └─────────────┘
       │ 否
       ▼
┌─────────────┐     是      ┌─────────────┐
│ 超过重试    │─────────────▶│ status=     │
│ 次数(3次)?  │              │ filtered    │
└──────┬──────┘              └─────────────┘
       │ 否
       ▼
┌─────────────┐
│ 延迟后重试   │  ← 指数退避
└─────────────┘
```

### 3. 多Agent结果去重策略

```python
# 结果唯一键
unique_key = (
    source_ip,      # 探测出口IP
    target_ip,      # 目标IP
    port,           # 端口
    protocol,       # TCP/UDP
    time_window     # 时间窗口（5分钟）
)

# 去重规则
1. 相同unique_key → 保留最新结果
2. 不同source_ip → 保留所有结果（不同视角）
3. 冲突处理 → 多结果并存，不覆盖
```

### 4. IP关系图建模

```python
# IP类型
IP_TYPE = {
    "private_a": "10.0.0.0/8",
    "private_b": "172.16.0.0/12",
    "private_c": "192.168.0.0/16",
    "public": "其他"
}

# 关系类型（可扩展）
RELATION_TYPE = {
    "nat_mapping": "NAT映射（私网→公网）",
    "eip_binding": "EIP绑定",
    "dns_resolution": "DNS解析",
    "reverse_nat": "反向NAT",
    "custom": "自定义关系"
}

# 关系结构
class IPRelation:
    from_ip: str       # 源IP
    to_ip: str         # 目标IP
    relation_type: str # 关系类型
    valid_from: datetime  # 生效时间
    valid_to: datetime    # 失效时间（可选）
    metadata: dict      # 扩展属性
```

---

## API设计

### 任务管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/tasks | 创建扫描任务 |
| GET | /api/v1/tasks | 列出任务 |
| GET | /api/v1/tasks/{id} | 获取任务详情 |
| DELETE | /api/v1/tasks/{id} | 删除任务 |

### 结果查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/results | 查询扫描结果 |
| GET | /api/v1/results/ip/{ip} | 查询单IP暴露面 |
| GET | /api/v1/results/pair?from=x&to=y | 查询IP对关系 |

### 图谱查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/graph/ip/{ip} | 获取IP关系子图 |
| GET | /api/v1/graph/stats | 获取图谱统计 |

### Agent管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/agents | 列出Agent |
| POST | /api/v1/agents/{id}/heartbeat | Agent心跳 |
| GET | /api/v1/agents/{id} | Agent详情 |

### 数据导出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/export/csv | 导出CSV |
| GET | /api/v1/export/json | 导出JSON |

---

## 部署架构

```
                    ┌─────────────────┐
                    │   Nginx (LB)    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
      ┌───────▼──────┐ ┌────▼──────┐ ┌─────▼──────┐
      │ Controller-1 │ │Controller│ │Controller- │
      │              │ │   -2     │ │     N      │
      └───────┬──────┘ └────┬─────┘ └─────┬──────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
      ┌───────▼──────┐ ┌────▼──────┐ ┌─────▼──────┐
      │  PostgreSQL  │ │ClickHouse│ │   Redis    │
      │   (主从)     │ │          │ │  (集群)    │
      └──────────────┘ └──────────┘ └────────────┘

分布式Agent部署:
┌──────────┐     ┌──────────┐     ┌──────────┐
│ VPC-A    │     │ VPC-B    │     │ DMZ      │
│ Agent-1  │────▶│ Agent-2  │────▶│ Agent-3  │
│ (出口IP1)│     │ (出口IP2)│     │ (出口IP3)│
└──────────┘     └──────────┘     └──────────┘
```

---

## 关键设计决策

### Q1: 为什么选择FastAPI而非Go?

- Python生态丰富（扫描库、图数据库客户端）
- 异步支持完善
- 开发效率高
- 性能满足需求（非CPU密集型）

### Q2: 为什么扫描结果用ClickHouse?

- 高吞吐写入（每秒百万行）
- 高效聚合查询
- 原生时序支持
- 压缩率高

### Q3: 如何处理UDP不可靠?

- 多次重试（3次，指数退避）
- 区分filtered/unknown状态
- 不强制open/closed二元分类
- 记录延迟和响应时间

### Q4: 如何水平扩展?

- Agent无状态设计
- Redis队列解耦
- ClickHouse分片
- PostgreSQL读写分离

### Q5: IP关系为什么用图结构?

- 关系多对多
- 关系类型可扩展
- 支持时间维度
- 支持复杂查询（路径发现）

---

## 安全设计

1. **Agent鉴权**: Token-based，每个Agent独立token
2. **API鉴权**: JWT + RBAC
3. **传输安全**: HTTPS/TLS
4. **输入校验**: 严格的请求参数校验
5. **速率限制**: 防止滥用