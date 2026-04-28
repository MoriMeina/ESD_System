-- ============================================================
-- ClickHouse 初始化脚本
-- 分布式暴露面检测平台 (ASDP)
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS asdp;

-- 扫描结果表
CREATE TABLE IF NOT EXISTS asdp.scan_results (
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
CREATE MATERIALIZED VIEW IF NOT EXISTS asdp.ip_exposure_summary
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
CREATE INDEX IF NOT EXISTS idx_target_ip ON asdp.scan_results(target_ip) TYPE minmax GRANULARITY 4;
CREATE INDEX IF NOT EXISTS idx_task_id ON asdp.scan_results(task_id) TYPE minmax GRANULARITY 4;