# Nginx 反向代理配置指南

## 1. 概述

Nginx 作为反向代理部署在 Controller 前端，提供：
- **静态文件服务**: 前端 HTML/CSS/JS
- **API 反向代理**: 将 `/api/v1/*` 转发到 Controller
- **HTTPS 终止**: TLS/SSL 加密
- **负载均衡**: 多 Controller 实例时的流量分发

### 架构拓扑

```
                    ┌─────────────┐
   用户浏览器 ──────▶│    Nginx     │
                    │  反向代理     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    ┌─────────▼──┐  ┌─────▼────┐  ┌───▼────────┐
    │  静态文件   │  │   API    │  │  WebSocket  │
    │ /css/      │  │ /api/v1/ │  │ (如有)      │
    │ /js/       │  │          │  │             │
    │ /index.html│  │          │  │             │
    └────────────┘  └─────┬────┘  └──────┬──────┘
                          │              │
                    ┌─────▼──────────────▼─────┐
                    │     Controller (FastAPI)  │
                    │       :8000               │
                    └──────────────────────────┘
```

---

## 2. 路径映射说明

### 前端资源路径

根据 `frontend/index.html` 和 `static/` 目录结构：

| 浏览器请求路径 | 实际文件路径 | 服务方式 |
|---------------|-------------|---------|
| `/` | `frontend/index.html` | Nginx 静态文件 |
| `/css/style.css` | `static/css/style.css` | Nginx 静态文件 |
| `/js/app.js` | `static/js/app.js` | Nginx 静态文件 |

### API 路径

根据 `static/js/app.js` 中的 `API_BASE = '/api/v1'`：

| 浏览器请求路径 | Controller 路径 | 说明 |
|---------------|----------------|------|
| `/api/v1/agents/` | `/api/v1/agents/` | Agent 管理 |
| `/api/v1/tasks/` | `/api/v1/tasks/` | 任务管理 |
| `/api/v1/results/` | `/api/v1/results/` | 扫描结果 |
| `/api/v1/graph/` | `/api/v1/graph/` | 关系图谱 |
| `/api/v1/export/` | `/api/v1/export/` | 数据导出 |

### Agent 通信路径

Agent 通过 `CONTROLLER_URL` 直接访问 Controller，**不经过 Nginx**（分布式场景下 Agent 可能在不同的网络区域）。如果 Agent 和 Controller 在同一网络且希望通过 Nginx 访问，需要配置相同的路由规则。

---

## 3. 基本配置

### 3.1 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx

# CentOS/RHEL
sudo yum install epel-release
sudo yum install nginx
```

### 3.2 配置文件

```nginx
# /etc/nginx/conf.d/asdp.conf

upstream controller {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name asdp.example.com;

    # ============================================
    # 静态文件 - 前端
    # ============================================

    # 前端入口
    root /opt/asdp;

    # 首页
    location = / {
        try_files /frontend/index.html =404;
    }

    # CSS 文件: /css/style.css -> static/css/style.css
    location /css/ {
        alias /opt/asdp/static/css/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # JS 文件: /js/app.js -> static/js/app.js
    location /js/ {
        alias /opt/asdp/static/js/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 其他静态资源
    location /static/ {
        alias /opt/asdp/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # ============================================
    # API 反向代理
    # ============================================
    location /api/ {
        proxy_pass http://controller;
        proxy_http_version 1.1;

        # 代理头
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # 缓冲
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;

        # 大文件支持（导出功能）
        client_max_body_size 50m;
    }

    # ============================================
    # 健康检查
    # ============================================
    location = /health {
        proxy_pass http://controller;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # ============================================
    # 安全头
    # ============================================
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

### 3.3 测试配置

```bash
# 检查配置语法
sudo nginx -t

# 重载配置
sudo systemctl reload nginx

# 查看日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 4. HTTPS 配置

### 4.1 使用 Let's Encrypt（推荐）

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d asdp.example.com

# 自动续期（Certbot 会配置 systemd timer）
sudo certbot renew --dry-run
```

### 4.2 手动配置 SSL

```nginx
# /etc/nginx/conf.d/asdp-ssl.conf

upstream controller {
    server 127.0.0.1:8000;
    keepalive 32;
}

# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name asdp.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name asdp.example.com;

    # SSL 证书
    ssl_certificate /etc/letsencrypt/live/asdp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/asdp.example.com/privkey.pem;

    # SSL 优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # 静态文件配置（同上）
    root /opt/asdp;

    location = / {
        try_files /frontend/index.html =404;
    }

    location /css/ {
        alias /opt/asdp/static/css/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location /js/ {
        alias /opt/asdp/static/js/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://controller;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        client_max_body_size 50m;
    }

    location = /health {
        proxy_pass http://controller;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

---

## 5. 多 Controller 负载均衡

### 5.1 配置多个 Controller 实例

```nginx
upstream controller {
    # 权重负载均衡
    server controller-01:8000 weight=3;
    server controller-02:8000 weight=2;
    server controller-03:8000 weight=1 backup;

    keepalive 64;
}

server {
    listen 80;
    server_name asdp.example.com;

    root /opt/asdp;

    location = / {
        try_files /frontend/index.html =404;
    }

    location /css/ {
        alias /opt/asdp/static/css/;
        expires 7d;
    }

    location /js/ {
        alias /opt/asdp/static/js/;
        expires 7d;
    }

    location /api/ {
        proxy_pass http://controller;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        client_max_body_size 50m;
    }
}
```

---

## 6. Agent 通过 Nginx 访问（可选）

如果 Agent 需要通过网络（而非本地）访问 Controller，可以添加 Agent 专用的代理配置。

### 6.1 Agent API 代理配置

```nginx
# Agent 专用的 upstream（可以与前端使用同一组）
upstream controller {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name asdp.example.com;

    root /opt/asdp;

    # 前端静态文件（同上）
    location = / { try_files /frontend/index.html =404; }
    location /css/ { alias /opt/asdp/static/css/; expires 7d; }
    location /js/ { alias /opt/asdp/static/js/; expires 7d; }

    # API 反向代理
    location /api/ {
        proxy_pass http://controller;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 保留 Agent Token
        proxy_pass_request_headers on;

        proxy_connect_timeout 30s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        client_max_body_size 50m;
    }
}
```

### 6.2 Agent 配置

Agent 设置 `CONTROLLER_URL` 指向 Nginx：

```bash
CONTROLLER_URL=https://asdp.example.com
```

> ⚠️ **注意**: 分布式部署场景下，Agent 通常部署在不同网络区域，直接访问 Controller 内网地址更合适。此配置仅适用于 Agent 和 Controller 在同一网络或通过互联网通信的场景。

---

## 7. Controller CORS 配置

当使用 Nginx 反向代理时，Controller 的 CORS 配置需要调整。

### controller/config.py

```python
# 不使用 Nginx 时（直接访问）
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
]

# 使用 Nginx 反向代理时
# 前端和 API 同源，CORS 不是必需的
# 但 Agent 通过互联网访问时需要添加
CORS_ORIGINS = [
    "http://localhost:3000",
    "https://asdp.example.com",  # 添加 Nginx 域名
]
```

或者通过环境变量配置：

```bash
# .env
CORS_ORIGINS='["http://localhost:3000","https://asdp.example.com"]'
```

---

## 8. 日志配置

```nginx
# /etc/nginx/conf.d/asdp.conf

# 自定义日志格式
log_format asdp '$remote_addr - $remote_user [$time_local] '
                '"$request" $status $body_bytes_sent '
                '"$http_referer" "$http_user_agent" '
                '$request_time $upstream_response_time';

server {
    listen 80;
    server_name asdp.example.com;

    access_log /var/log/nginx/asdp_access.log asdp;
    error_log  /var/log/nginx/asdp_error.log warn;

    # ... 其他配置
}
```

### 日志轮转

```bash
# /etc/logrotate.d/nginx-asdp
/var/log/nginx/asdp_*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
    endscript
}
```

---

## 9. 性能优化

### 9.1 Gzip 压缩

```nginx
server {
    # ...

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1024;
}
```

### 9.2 静态文件缓存

```nginx
location /css/ {
    alias /opt/asdp/static/css/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    add_header Vary "Accept-Encoding";
}

location /js/ {
    alias /opt/asdp/static/js/;
    expires 30d;
    add_header Cache-Control "public, immutable";
    add_header Vary "Accept-Encoding";
}
```

### 9.3 Worker 配置

```nginx
# /etc/nginx/nginx.conf

worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    multi_accept on;
    use epoll;
}
```

---

## 10. 安全加固

### 10.1 限制请求速率

```nginx
# /etc/nginx/nginx.conf

http {
    # API 限流
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

    # Agent 心跳限流
    limit_req_zone $binary_remote_addr zone=heartbeat:10m rate=10r/s;
}

server {
    # API 限流
    location /api/ {
        limit_req zone=api burst=200 nodelay;
        # ... proxy_pass ...
    }
}
```

### 10.2 隐藏 Nginx 版本

```nginx
server {
    server_tokens off;
}
```

### 10.3 访问控制

```nginx
# 限制管理 API 访问
location /api/v1/agents/ {
    allow 10.0.0.0/8;      # 内网
    allow 172.16.0.0/12;    # 内网
    deny all;

    proxy_pass http://controller;
    # ...
}
```

---

## 11. 故障排查

### 11.1 检查 Nginx 状态

```bash
sudo systemctl status nginx
sudo nginx -t
```

### 11.2 测试 API 连通性

```bash
# 测试 Nginx 代理
curl -v http://asdp.example.com/api/v1/agents/

# 直接测试 Controller
curl -v http://127.0.0.1:8000/api/v1/agents/
```

### 11.3 常见问题

| 问题 | 原因 | 解决方法 |
|------|------|---------|
| 404 静态文件 | alias 路径错误 | 检查 `alias` 路径是否存在 |
| 502 Bad Gateway | Controller 未启动 | `systemctl status asdp-controller` |
| 504 Gateway Timeout | 响应超时 | 增加 `proxy_read_timeout` |
| CORS 错误 | 域名不在 CORS 白名单 | 更新 `CORS_ORIGINS` |
| 413 Request Entity Too Large | 请求体过大 | 增加 `client_max_body_size` |