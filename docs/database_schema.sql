-- ============================================================
-- 分布式暴露面检测平台 (ASDP) 数据库Schema
-- ============================================================
-- PostgreSQL: 关系数据 (IP资产、关系、Agent、任务)
-- ClickHouse: 扫描结果 (高吞吐时序数据)
-- ============================================================

-- ============================================================
-- PostgreSQL Schema
-- ============================================================

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------
-- 1. Agent 表
-- -----------------------------------------------------------
CREATE TABLE agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    token           VARCHAR(255) NOT NULL UNIQUE DEFAULT crypt(gen_random_bytes(32), gen_salt('bf')),
    description     TEXT,
    
    -- 网络信息
    source_ip       INET,              -- Agent出口IP
    network_zone    VARCHAR(50),       -- 网络区域: vpc-a, vpc-b, dmz, internet
    
    -- 状态
    status          VARCHAR(20) DEFAULT 'offline',  -- offline/online/disabled
    last_heartbeat  TIMESTAMPTZ,
    
    -- 限流配置
    max_concurrency INT DEFAULT 50,    -- 最大并发数
    rate_limit      INT DEFAULT 1000,  -- 每秒最大扫描数
    
    -- 时间戳
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_network_zone ON agents(network_zone);

-- -----------------------------------------------------------
-- 2. IP 资产表
-- -----------------------------------------------------------
CREATE TABLE ip_assets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_address      INET NOT NULL UNIQUE,
    
    -- IP类型
    ip_type         VARCHAR(20) NOT NULL,  -- private_a/private_b/private_c/public/eip
    
    -- 元数据 (JSONB支持灵活扩展)
    metadata        JSONB DEFAULT '{}'::jsonb,
    -- metadata示例:
    -- {
    --   "hostname": "server01.example.com",
    --   "organization": "Example Corp",
    --   "department": "IT",
    --   "os": "Linux",
    --   "geo": {"country": "CN", "city": "Beijing"}
    -- }
    
    -- 发现信息
    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
    discovered_by   UUID REFERENCES agents(id),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- 标签
    tags            TEXT[] DEFAULT '{}'::text[]
);

CREATE INDEX idx_ip_assets_type ON ip_assets(ip_type);
CREATE INDEX idx_ip_assets_tags ON ip_assets USING GIN(tags);
CREATE INDEX idx_ip_assets_metadata ON ip_assets USING GIN(metadata);

-- -----------------------------------------------------------
-- 3. IP 关系表 (图结构建模)
-- -----------------------------------------------------------
CREATE TABLE ip_relations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关系两端
    from_ip_id      UUID NOT NULL REFERENCES ip_assets(id) ON DELETE CASCADE,
    to_ip_id        UUID NOT NULL REFERENCES ip_assets(id) ON DELETE CASCADE,
    
    -- 关系类型 (可扩展，不写死)
    relation_type   VARCHAR(50) NOT NULL,
    -- 预定义关系类型:
    -- nat_mapping: NAT映射 (私网→公网)
    -- eip_binding: EIP绑定
    -- dns_resolution: DNS解析
    -- reverse_nat: 反向NAT
    -- custom_*: 自定义关系
    
    -- 时间维度 (关系可能变化)
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to        TIMESTAMPTZ,  -- NULL表示当前有效
    
    -- 元数据
    metadata        JSONB DEFAULT '{}'::jsonb,
    -- metadata示例:
    -- {
    --   "nat_type": "dnat",
    --   "external_port": 8080,
    --   "internal_port": 80,
    --   "protocol": "tcp"
    -- }
    
    -- 审计
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      UUID REFERENCES agents(id),
    
    -- 防止重复关系
    UNIQUE (from_ip_id, to_ip_id, relation_type, valid_from)
);

CREATE INDEX idx_ip_relations_from ON ip_relations(from_ip_id);
CREATE INDEX idx_ip_relations_to ON ip_relations(to_ip_id);
CREATE INDEX idx_ip_relations_type ON ip_relations(relation_type);
CREATE INDEX idx_ip_relations_valid ON ip_relations(valid_from, valid_to);

-- -----------------------------------------------------------
-- 4. 扫描任务表
-- -----------------------------------------------------------
CREATE TABLE scan_tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    
    -- 扫描目标
    target_ips      INET[] NOT NULL,      -- 目标IP列表
    port_range      VARCHAR(50) NOT NULL, -- 如 "1-10000" 或 "22,80,443,8080"
    protocol        VARCHAR(10) NOT NULL, -- tcp/udp/both
    
    -- 任务状态
    status          VARCHAR(20) DEFAULT 'pending',  -- pending/running/completed/failed/cancelled
    progress        INT DEFAULT 0,          -- 0-100
    
    -- 扫描策略
    scan_type       VARCHAR(20) DEFAULT 'connect',  -- connect/syn (TCP)
    timeout_ms      INT DEFAULT 3000,       -- 超时时间
    max_retries     INT DEFAULT 3,          -- 最大重试次数
    
    -- 统计
    total_ports     INT,                    -- 总端口数
    scanned_ports   INT DEFAULT 0,          -- 已扫描端口数
    open_ports      INT DEFAULT 0,          -- 开放端口数
    
    -- 时间戳
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      VARCHAR(100)           -- 创建用户
);

CREATE INDEX idx_scan_tasks_status ON scan_tasks(status);
CREATE INDEX idx_scan_tasks_created ON scan_tasks(created_at);

-- -----------------------------------------------------------
-- 5. 任务分配表 (任务→Agent)
-- -----------------------------------------------------------
CREATE TABLE task_assignments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id         UUID NOT NULL REFERENCES scan_tasks(id) ON DELETE CASCADE,
    agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    
    -- 分配状态
    status          VARCHAR(20) DEFAULT 'pending',  -- pending/running/completed/failed
    progress        INT DEFAULT 0,
    
    -- 结果统计
    total_scans     INT DEFAULT 0,
    completed_scans INT DEFAULT 0,
    
    -- 时间戳
    assigned_at     TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    
    -- 错误信息
    error_message   TEXT,
    
    UNIQUE (task_id, agent_id)
);

CREATE INDEX idx_task_assignments_task ON task_assignments(task_id);
CREATE INDEX idx_task_assignments_agent ON task_assignments(agent_id);
CREATE INDEX idx_task_assignments_status ON task_assignments(status);

-- -----------------------------------------------------------
-- 6. 用户表 (简化版)
-- -----------------------------------------------------------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        VARCHAR(100) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    role            VARCHAR(20) DEFAULT 'viewer',  -- admin/operator/viewer
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- 7. API 密钥表
-- -----------------------------------------------------------
CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key             VARCHAR(255) NOT NULL UNIQUE,
    user_id         UUID REFERENCES users(id),
    description     TEXT,
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT true,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- 8. 关系类型字典表 (支持动态扩展)
-- -----------------------------------------------------------
CREATE TABLE relation_types (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,
    description     TEXT,
    category        VARCHAR(50),  -- network/dns/custom
    is_built_in     BOOLEAN DEFAULT false,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 插入预定义关系类型
INSERT INTO relation_types (name, description, category, is_built_in) VALUES
('nat_mapping', 'NAT映射 (私网→公网)', 'network', true),
('eip_binding', '弹性IP绑定', 'network', true),
('dns_resolution', 'DNS解析关系', 'dns', true),
('reverse_nat', '反向NAT映射', 'network', true),
('vlan_mapping', 'VLAN映射', 'network', true),
('proxy_forward', '代理转发', 'network', true);

-- ============================================================
-- ClickHouse Schema (扫描结果)
-- ============================================================
-- 以下SQL在ClickHouse中执行

/*
CREATE DATABASE IF NOT EXISTS asdp;

CREATE TABLE asdp.scan_results (
    task_id               UUID,
    agent_id              UUID,
    source_ip             String,      -- 探测出口IP
    target_ip             String,      -- 目标IP
    port                  UInt16,
    protocol              Enum8('tcp' = 1, 'udp' = 2),
    status                Enum8('open' = 1, 'closed' = 2, 'filtered' = 3, 'unknown' = 4),
    latency_ms            Float64,     -- 延迟(毫秒)
    banner                String,      -- 服务横幅
    error_message         String,      -- 错误信息
    retry_count           UInt8,       -- 重试次数
    scanned_at            DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(scanned_at)
ORDER BY (task_id, source_ip, target_ip, port, protocol, scanned_at)
TTL scanned_at + INTERVAL 90 DAY;

-- 物化视图: 按IP聚合
CREATE MATERIALIZED VIEW asdp.ip_exposure_summary
ENGINE = AggregatingMergeTree()
ORDER BY (target_ip, port, protocol)
AS SELECT
    target_ip,
    port,
    protocol,
    countState() as total_scans,
    countIfState(status = 'open') as open_scans,
    maxState(scanned_at) as last_scanned,
    groupArrayState(source_ip) as scanning_agents
FROM asdp.scan_results
GROUP BY target_ip, port, protocol;

-- 索引
CREATE INDEX idx_target_ip ON asdp.scan_results(target_ip) TYPE minmax GRANULARITY 4;
CREATE INDEX idx_task_id ON asdp.scan_results(task_id) TYPE minmax GRANULARITY 4;
*/

-- ============================================================
-- Redis Key 设计
-- ============================================================
/*
# 任务队列
task_queue:{agent_id}          -- List, 待执行任务
task_result_queue              -- List, 待处理结果

# Agent心跳
agent:heartbeat:{agent_id}     -- String, 最后心跳时间 (TTL 60s)
agent:status:{agent_id}        -- Hash, Agent状态信息

# 任务状态缓存
task:status:{task_id}          -- Hash, 任务实时状态
task:progress:{task_id}        -- String, 任务进度

# 分布式锁
lock:task:{task_id}            -- String, 任务锁
lock:agent:{agent_id}          -- String, Agent锁

# 速率限制
rate:agent:{agent_id}          -- String, 滑动窗口计数
*/