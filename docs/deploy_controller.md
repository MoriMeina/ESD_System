# Controller 服务端部署文档

## 1. 环境要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4+ 核 |
| 内存 | 4 GB | 8+ GB |
| 磁盘 | 50 GB | 100+ GB SSD |
| 网络 | 100 Mbps | 1 Gbps |
| 操作系统 | Ubuntu 20.04+ / CentOS 8+ | Ubuntu 22.04 LTS |

### 依赖服务

| 服务 | 版本 | 端口 | 说明 |
|------|------|------|------|
| PostgreSQL | 16+ | 5432 | 关系型数据存储 |
| ClickHouse | 23.8+ | 8123/9000 | 扫描结果 OLAP 存储 |
| Redis | 7+ | 6379 | 任务队列 + 缓存 |

---

## 2. Docker Compose 部署（推荐）

### 2.1 前置条件

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 验证
docker --version
docker-compose --version
```

### 2.2 获取项目

```bash
git clone <repository-url>
cd flaskProject
```

### 2.3 配置环境变量

复制 `.env.example` 并修改：

```bash
# Controller 配置
PG_HOST=postgres
PG_PORT=5432
PG_USER=asdp
PG_PASSWORD=asdp_secure_password_2024
PG_DB=asdp

# ClickHouse 配置
CH_HOST=clickhouse
CH_PORT=8123
CH_USER=asdp
CH_PASSWORD=asdp_secure_password_2024
CH_DB=asdp

# Redis 配置
REDIS_HOST=redis
REDIS_PORT=6379

# CORS
CORS_ORIGINS='["http://localhost:3000","http://localhost:8080"]'

# API Key (Controller 认证)
CONTROLLER_API_KEY=your_super_secret_api_key_here
```

### 2.4 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看启动状态
docker-compose ps

# 查看日志
docker-compose logs -f controller
docker-compose logs -f postgres
docker-compose logs -f clickhouse
docker-compose logs -f redis
```

### 2.5 健康检查

```bash
# 等待服务就绪
sleep 10

# 检查 Controller
curl http://localhost:8000/api/v1/health

# 检查 PostgreSQL
docker-compose exec postgres pg_isready -U asdp

# 检查 ClickHouse
docker-compose exec clickhouse clickhouse-client --query "SELECT 1"

# 检查 Redis
docker-compose exec redis redis-cli ping
```

### 2.6 常用操作

```bash
# 重启 Controller
docker-compose restart controller

# 停止所有服务
docker-compose down

# 停止并清除数据卷
docker-compose down -v

# 升级（拉取最新代码后）
docker-compose up -d --build

# 查看 Controller 日志
docker-compose logs -f --tail=100 controller
```

---

## 3. 裸机部署

### 3.1 安装 PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# 创建数据库和用户
sudo -u postgres psql <<EOF
CREATE DATABASE asdp;
CREATE USER asdp WITH PASSWORD 'asdp_secure_password_2024';
GRANT ALL PRIVILEGES ON DATABASE asdp TO asdp;
EOF

# 初始化 Schema
psql -U asdp -d asdp -f init.sql
```

### 3.2 安装 ClickHouse

```bash
# Ubuntu/Debian
sudo apt-get install -y apt-transport-https ca-certificates dirmngr
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 8919F6BD2B48D754
echo "deb https://packages.clickhouse.com/deb stable main" | sudo tee /etc/apt/sources.list.d/clickhouse.list
sudo apt-get update
sudo apt-get install -y clickhouse-server clickhouse-client

# 启动
sudo systemctl enable clickhouse-server
sudo systemctl start clickhouse-server

# 创建数据库和用户
clickhouse-client --query "CREATE DATABASE IF NOT EXISTS asdp"
clickhouse-client --query "CREATE USER asdp IDENTIFIED WITH sha256_password BY 'asdp_secure_password_2024'"
clickhouse-client --query "GRANT ALL ON asdp.* TO asdp"

# 初始化 Schema
clickhouse-client --multiquery -f init_ch.sql
```

### 3.3 安装 Redis

```bash
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 3.4 安装 Controller

```bash
# 安装 Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 创建虚拟环境
cd /opt
python3.11 -m venv asdp-env
source asdp-env/bin/activate

# 安装依赖
pip install -r controller/requirements.txt

# 创建 systemd 服务
sudo tee /etc/systemd/system/asdp-controller.service <<EOF
[Unit]
Description=ASDP Controller
After=network.target postgresql.service clickhouse-server.service redis-server.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/flaskProject
Environment=PATH=/opt/asdp-env/bin
Environment=PG_HOST=localhost
Environment=PG_PORT=5432
Environment=PG_USER=asdp
Environment=PG_PASSWORD=asdp_secure_password_2024
Environment=PG_DB=asdp
Environment=CH_HOST=localhost
Environment=CH_PORT=8123
Environment=CH_USER=asdp
Environment=CH_PASSWORD=asdp_secure_password_2024
Environment=CH_DB=asdp
Environment=REDIS_HOST=localhost
Environment=REDIS_PORT=6379
Environment=CONTROLLER_API_KEY=your_super_secret_api_key_here
ExecStart=/opt/asdp-env/bin/uvicorn controller.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动
sudo systemctl daemon-reload
sudo systemctl enable asdp-controller
sudo systemctl start asdp-controller

# 查看状态
sudo systemctl status asdp-controller
sudo journalctl -u asdp-controller -f
```

---

## 4. Nginx 反向代理（可选）

```nginx
server {
    listen 80;
    server_name asdp.example.com;

    # 前端静态资源
    location / {
        root /opt/flaskProject/frontend;
        try_files $uri $uri/ /index.html;
    }

    # CSS/JS 静态资源
    location /static/ {
        alias /opt/flaskProject/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # 扫描任务可能耗时较长
    }

    # WebSocket（如果启用）
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 5. 数据库备份

```bash
# PostgreSQL 备份
pg_dump -U asdp asdp > backup_$(date +%Y%m%d).sql

# ClickHouse 备份
clickhouse-client --query "BACKUP TABLE asdp.scan_results TO Disk('backups', 'backup_$(date +%Y%m%d)_')"

# 定时备份（crontab）
0 2 * * * pg_dump -U asdp asdp > /backups/asdp_$(date +\%Y\%m\%d).sql
```

---

## 6. 监控指标

| 指标 | 查询方式 | 告警阈值 |
|------|---------|---------|
| 任务队列积压 | `redis-cli LLEN task_queue` | > 1000 |
| PostgreSQL 连接数 | `SELECT count(*) FROM pg_stat_activity` | > 80 |
| ClickHouse 写入延迟 | 监控 clickhouse-server 日志 | > 5s |
| Controller CPU | `top` / Prometheus | > 80% |
| Controller 内存 | `free -h` | > 90% |
| Agent 离线 | API: `GET /agents/?status=offline` | 任意 |