"""
ASDP - 数据模型单元测试
"""
import unittest
from datetime import datetime, timezone
from uuid import UUID, uuid4

from controller.models.schemas import (
    ScanTaskCreate,
    ScanProtocol,
    AgentCreate,
    AgentHeartbeatRequest,
    IPRelationCreate,
    IPRelationType,
    ScanResultItem,
    ScanResultBatch,
    parse_port_range,
    validate_ip,
)


class TestParsePortRange(unittest.TestCase):
    """测试端口范围解析"""

    def test_single_port(self):
        """单端口"""
        self.assertEqual(parse_port_range("80"), [80])

    def test_port_range(self):
        """端口范围"""
        result = parse_port_range("1-10")
        self.assertEqual(result, list(range(1, 11)))
        self.assertEqual(len(result), 10)

    def test_common_ports(self):
        """常用端口列表"""
        result = parse_port_range("22,80,443,8080")
        self.assertEqual(result, [22, 80, 443, 8080])

    def test_full_range(self):
        """全端口范围"""
        result = parse_port_range("1-65535")
        self.assertEqual(len(result), 65535)
        self.assertEqual(result[0], 1)
        self.assertEqual(result[-1], 65535)

    def test_invalid_range(self):
        """无效范围"""
        with self.assertRaises(ValueError):
            parse_port_range("100-10")

    def test_mixed_format(self):
        """混合格式"""
        result = parse_port_range("22,80-90,443")
        expected = [22] + list(range(80, 91)) + [443]
        self.assertEqual(result, expected)

    def test_invalid_port(self):
        """无效端口号"""
        with self.assertRaises(ValueError):
            parse_port_range("0")
        with self.assertRaises(ValueError):
            parse_port_range("65536")


class TestValidateIP(unittest.TestCase):
    """测试IP验证"""

    def test_valid_ipv4(self):
        for ip in ["192.168.1.1", "10.0.0.1", "172.16.0.1", "0.0.0.0", "255.255.255.255"]:
            self.assertTrue(validate_ip(ip), f"{ip} should be valid")

    def test_invalid_ip(self):
        for ip in ["256.0.0.0", "1.2.3", "abc", "", "192.168.1.1.1", "192.168.1.-1"]:
            self.assertFalse(validate_ip(ip), f"{ip} should be invalid")


class TestScanTaskCreate(unittest.TestCase):
    """测试扫描任务创建模型"""

    def test_minimal_task(self):
        """最小任务创建"""
        task = ScanTaskCreate(
            name="test",
            target_ips=["192.168.1.1"],
            port_range="1-100",
        )
        self.assertEqual(task.name, "test")
        self.assertEqual(task.target_ips, ["192.168.1.1"])
        self.assertEqual(task.port_range, "1-100")
        self.assertEqual(task.protocol, ScanProtocol.TCP)
        self.assertEqual(task.timeout_ms, 3000)
        self.assertEqual(task.max_retries, 3)
        self.assertIsNone(task.agent_ids)

    def test_full_task(self):
        """完整任务创建"""
        task = ScanTaskCreate(
            name="full-test",
            target_ips=["10.0.0.1", "10.0.0.2"],
            port_range="22,80,443",
            protocol=ScanProtocol.BOTH,
            scan_type="connect",
            timeout_ms=5000,
            max_retries=5,
            agent_ids=[uuid4(), uuid4()],
            description="Full test task",
        )
        self.assertEqual(task.protocol, ScanProtocol.BOTH)
        self.assertEqual(task.timeout_ms, 5000)
        self.assertEqual(task.max_retries, 5)
        self.assertEqual(len(task.agent_ids), 2)
        for aid in task.agent_ids:
            self.assertIsInstance(aid, UUID)

    def test_invalid_target_ip(self):
        """无效目标IP"""
        with self.assertRaises(Exception):
            ScanTaskCreate(
                name="bad",
                target_ips=["not-an-ip"],
                port_range="80",
            )

    def test_empty_target_ips(self):
        """空目标列表"""
        with self.assertRaises(Exception):
            ScanTaskCreate(
                name="bad",
                target_ips=[],
                port_range="80",
            )


class TestAgentCreate(unittest.TestCase):
    """测试Agent创建模型"""

    def test_minimal_agent(self):
        agent = AgentCreate(name="test-agent")
        self.assertEqual(agent.name, "test-agent")
        self.assertEqual(agent.max_concurrency, 50)
        self.assertEqual(agent.rate_limit, 1000)

    def test_custom_agent(self):
        agent = AgentCreate(
            name="custom",
            description="A custom agent",
            network_zone="vpc-a",
            max_concurrency=100,
            rate_limit=2000,
        )
        self.assertEqual(agent.network_zone, "vpc-a")
        self.assertEqual(agent.max_concurrency, 100)


class TestAgentHeartbeatRequest(unittest.TestCase):
    """测试心跳请求模型"""

    def test_heartbeat(self):
        hb = AgentHeartbeatRequest(source_ip="10.0.0.1")
        self.assertEqual(hb.source_ip, "10.0.0.1")
        self.assertIsNone(hb.stats)

    def test_heartbeat_with_stats(self):
        hb = AgentHeartbeatRequest(
            source_ip="10.0.0.1",
            stats={"buffer_size": 50},
        )
        self.assertEqual(hb.stats["buffer_size"], 50)


class TestIPRelationCreate(unittest.TestCase):
    """测试IP关系创建模型"""

    def test_relation_without_time(self):
        rel = IPRelationCreate(
            from_ip="192.168.1.1",
            to_ip="203.0.113.1",
            relation_type=IPRelationType.NAT_MAPPING,
        )
        self.assertEqual(rel.from_ip, "192.168.1.1")
        self.assertEqual(rel.relation_type, IPRelationType.NAT_MAPPING)
        self.assertIsNone(rel.valid_to)

    def test_relation_with_time_range(self):
        now = datetime.now(timezone.utc)
        rel = IPRelationCreate(
            from_ip="192.168.1.1",
            to_ip="203.0.113.1",
            relation_type=IPRelationType.EIP_BINDING,
            valid_from=now,
            valid_to=now.replace(day=now.day + 30),
            metadata={"provider": "aws"},
        )
        self.assertIsNotNone(rel.valid_from)
        self.assertIsNotNone(rel.valid_to)
        self.assertEqual(rel.metadata["provider"], "aws")


class TestScanResultItem(unittest.TestCase):
    """测试扫描结果模型"""

    def test_tcp_result(self):
        now = datetime.now(timezone.utc)
        result = ScanResultItem(
            task_id=str(uuid4()),
            agent_id=str(uuid4()),
            source_ip="10.0.0.1",
            target_ip="192.168.1.1",
            port=80,
            protocol="tcp",
            status="open",
            latency_ms=1.5,
            scanned_at=now,
        )
        self.assertEqual(result.status, "open")
        self.assertEqual(result.protocol, "tcp")
        self.assertEqual(result.retry_count, 0)

    def test_udp_filtered_result(self):
        now = datetime.now(timezone.utc)
        result = ScanResultItem(
            task_id=str(uuid4()),
            agent_id=str(uuid4()),
            source_ip="10.0.0.1",
            target_ip="192.168.1.1",
            port=53,
            protocol="udp",
            status="filtered",
            latency_ms=5000.0,
            error_message="no_response_after_retries",
            retry_count=5,
            scanned_at=now,
        )
        self.assertEqual(result.status, "filtered")
        self.assertEqual(result.retry_count, 5)
        self.assertEqual(result.error_message, "no_response_after_retries")

    def test_udp_unknown_result(self):
        now = datetime.now(timezone.utc)
        result = ScanResultItem(
            task_id=str(uuid4()),
            agent_id=str(uuid4()),
            source_ip="10.0.0.1",
            target_ip="192.168.1.1",
            port=53,
            protocol="udp",
            status="unknown",
            latency_ms=3000.0,
            error_message="timeout",
            scanned_at=now,
        )
        self.assertEqual(result.status, "unknown")


class TestScanResultBatch(unittest.TestCase):
    """测试结果批量模型"""

    def test_batch(self):
        now = datetime.now(timezone.utc)
        results = [
            ScanResultItem(
                task_id="task-1", agent_id="agent-1",
                source_ip="10.0.0.1", target_ip="192.168.1.1",
                port=80, protocol="tcp", status="open",
                latency_ms=1.0, scanned_at=now,
            )
            for _ in range(10)
        ]
        batch = ScanResultBatch(
            agent_id="agent-1",
            task_id="task-1",
            results=results,
        )
        self.assertEqual(len(batch.results), 10)
        self.assertEqual(batch.task_id, "task-1")


if __name__ == "__main__":
    unittest.main()