-- ============================================================
-- PostgreSQL 初始化脚本
-- 分布式暴露面检测平台 (ASDP)
-- ============================================================

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------
-- 1. Agent 表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    token           VARCHAR(255) NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
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

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_network_zone ON agents(network_zone);

-- -----------------------------------------------------------
-- 2. IP 资产表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ip_assets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_address      INET NOT NULL UNIQUE,
    
    -- IP类型
    ip_type         VARCHAR(20) NOT NULL,  -- private_a/private_b/private_c/public/eip
    
    -- 元数据 (JSONB支持灵活扩展)
    metadata        JSONB DEFAULT '{}'::jsonb,
    
    -- 发现信息
    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
    discovered_by   UUID REFERENCES agents(id),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    -- 标签
    tags            TEXT[] DEFAULT '{}'::text[]
);

CREATE INDEX IF NOT EXISTS idx_ip_assets_type ON ip_assets(ip_type);
CREATE INDEX IF NOT EXISTS idx_ip_assets_tags ON ip_assets USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_ip_assets_metadata ON ip_assets USING GIN(metadata);

-- -----------------------------------------------------------
-- 3. IP 关系表 (图结构建模)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ip_relations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关系两端
    from_ip_id      UUID NOT NULL REFERENCES ip_assets(id) ON DELETE CASCADE,
    to_ip_id        UUID NOT NULL REFERENCES ip_assets(id) ON DELETE CASCADE,
    
    -- 关系类型
    relation_type   VARCHAR(50) NOT NULL,
    
    -- 时间维度
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to        TIMESTAMPTZ,
    
    -- 元数据
    metadata        JSONB DEFAULT '{}'::jsonb,
    
    -- 审计
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      UUID REFERENCES agents(id),
    
    -- 防止重复关系
    UNIQUE (from_ip_id, to_ip_id, relation_type, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_ip_relations_from ON ip_relations(from_ip_id);
CREATE INDEX IF NOT EXISTS idx_ip_relations_to ON ip_relations(to_ip_id);
CREATE INDEX IF NOT EXISTS idx_ip_relations_type ON ip_relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_ip_relations_valid ON ip_relations(valid_from, valid_to);

-- -----------------------------------------------------------
-- 4. 扫描任务表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS scan_tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    
    -- 扫描目标
    target_ips      INET[] NOT NULL,
    port_range      VARCHAR(50) NOT NULL,
    protocol        VARCHAR(10) NOT NULL,
    
    -- 任务状态
    status          VARCHAR(20) DEFAULT 'pending',
    progress        INT DEFAULT 0,
    
    -- 扫描策略
    scan_type       VARCHAR(20) DEFAULT 'connect',
    timeout_ms      INT DEFAULT 3000,
    max_retries     INT DEFAULT 3,
    
    -- 统计
    total_ports     INT,
    scanned_ports   INT DEFAULT 0,
    open_ports      INT DEFAULT 0,
    
    -- 时间戳
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_scan_tasks_status ON scan_tasks(status);
CREATE INDEX IF NOT EXISTS idx_scan_tasks_created ON scan_tasks(created_at);

-- -----------------------------------------------------------
-- 5. 任务分配表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS task_assignments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id         UUID NOT NULL REFERENCES scan_tasks(id) ON DELETE CASCADE,
    agent_id        UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    
    -- 分配状态
    status          VARCHAR(20) DEFAULT 'pending',
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

CREATE INDEX IF NOT EXISTS idx_task_assignments_task ON task_assignments(task_id);
CREATE INDEX IF NOT EXISTS idx_task_assignments_agent ON task_assignments(agent_id);
CREATE INDEX IF NOT EXISTS idx_task_assignments_status ON task_assignments(status);

-- -----------------------------------------------------------
-- 6. 用户表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        VARCHAR(100) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    email           VARCHAR(255),
    role            VARCHAR(20) DEFAULT 'viewer',
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------
-- 7. API 密钥表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
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
-- 8. 关系类型字典表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS relation_types (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE,
    description     TEXT,
    category        VARCHAR(50),
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
('proxy_forward', '代理转发', 'network', true)
ON CONFLICT (name) DO NOTHING;