# EC2 部署指南 - v1.1

> 环境：AWS EC2（中国区）Ubuntu 22.04，前后端和 Gotty 均部署在同一台 EC2。
> 
> **v1.1 新增功能**：
> - Nginx 配置文件管理（`nginx/kirocli` 配置文件）
> - 终端 URL 封装（前端通过后端 API 获取终端 URL）
> - 设备指纹采集与上报
> - 增强的安全性和监控功能

---

## v1.1 与 v1.0 的主要变化

### 1. Nginx 配置管理
- **v1.0**：手工在 EC2 上创建 Nginx 配置文件
- **v1.1**：项目中包含 `nginx/kirocli` 配置文件，需要上传到 EC2

### 2. 终端 URL 访问方式
- **v1.0**：前端直接拼接 Gotty URL（`http://IP:PORT/random-url`）
- **v1.1**：前端通过后端 API 获取封装后的终端 URL，后端统一管理 Gotty 路由

### 3. Nginx Gotty 路由配置
- **v1.0**：无特殊配置
- **v1.1**：使用 `map` 指令 + 通用 `location` 块实现动态路由

### 4. 安全组配置
- **v1.0**：需要开放 7860-7960 端口（Gotty 直接暴露）
- **v1.1**：只需开放 3000 端口（Gotty 通过 Nginx 反代，不直接暴露）

### 5. Gotty 绑定地址
- **v1.0**：Gotty 绑定 `0.0.0.0`（允许外部直接访问）
- **v1.1**：Gotty 绑定 `127.0.0.1`（仅本地访问，必须通过 Nginx）

---

## 前置信息

| 项目 | 值 |
|------|-----|
| EC2 公网 IP | `<YOUR_EC2_IP>`（以实际为准） |
| SSH 用户 | `ubuntu` |
| 前端访问端口 | `3000`（Nginx 反代） |
| 后端 FastAPI 端口 | `127.0.0.1:8000`（仅本机） |
| Gotty 主端口 | `7860` |
| Gotty 会话端口范围 | `7861–7960` |

---

## 步骤 1：EC2 安全组配置

**v1.1 重要安全改进**：Gotty 不再直接暴露到公网，所有流量通过 Nginx 反代。

在 AWS 控制台为 EC2 实例的安全组添加以下入站规则：

| 端口 | 协议 | 来源 | 用途 |
|------|------|------|------|
| 22 | TCP | 你的 IP | SSH |
| 3000 | TCP | 0.0.0.0/0 | 前端 + 后端 API + Gotty 终端（统一入口） |

> **安全提升**：
> - v1.1 不再需要开放 7860-7960 端口，减少了攻击面
> - Gotty 绑定 `127.0.0.1`，外部无法直接访问
> - 所有终端访问必须通过 Nginx 反代，可以统一进行访问控制和审计

---

## 步骤 2：连接 EC2

```bash
ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_IP>
```

---

## 步骤 3：安装系统依赖

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget nginx python3 python3-pip python3-venv sqlite3

# 安装 Node.js 20 LTS（使用 nvm，避免 apt 依赖冲突）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
nvm alias default 20
node -v  # 应显示 v20.x.x
```

---

## 步骤 4：安装 Gotty

```bash
wget https://github.com/sorenisanerd/gotty/releases/download/v1.5.0/gotty_v1.5.0_linux_amd64.tar.gz
tar -xzf gotty_v1.5.0_linux_amd64.tar.gz
sudo mv gotty /usr/local/bin/gotty
sudo chmod +x /usr/local/bin/gotty
gotty --version
```

---

## 步骤 5：安装 Kiro CLI

按照 Kiro CLI 官方文档安装，安装完成后确认路径：

```bash
which kiro-cli
# 记录输出路径，例如 /usr/bin/kiro-cli 或 /usr/local/bin/kiro-cli
# 后续 .env 中 KIRO_CLI_PATH 必须填写这个绝对路径

kiro-cli --version
```

> **重要**：必须用绝对路径，不能只写 `kiro-cli`。路径错误会导致 Gotty 启动后终端全黑、connection close。

---

## 步骤 6：创建 Gotty TLS 证书

**v1.1 重要变化**：Gotty 使用 HTTPS/TLS，Nginx 通过 `https://127.0.0.1:port` 反代到 Gotty。

```bash
# 创建证书目录
mkdir -p /home/ubuntu/kirocli-platform/certs

# 生成自签名证书（CN=127.0.0.1，因为 Gotty 绑定到 127.0.0.1）
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /home/ubuntu/kirocli-platform/certs/gotty-key.pem \
  -out /home/ubuntu/kirocli-platform/certs/gotty-cert.pem \
  -days 365 \
  -subj "/CN=127.0.0.1"

# 验证证书
openssl x509 -in /home/ubuntu/kirocli-platform/certs/gotty-cert.pem -text -noout | grep "Subject:"
# 应显示：Subject: CN = 127.0.0.1
```

> **说明**：
> - Gotty 绑定到 `127.0.0.1`（仅本地访问），所以证书 CN 必须是 `127.0.0.1`
> - Nginx 使用 `proxy_ssl_verify off` 信任自签名证书
> - 证书有效期 365 天，到期后需要重新生成

---

## 步骤 7：上传代码到 EC2
# 从Git Hub 仓库下载代码文件。
EC2的代码目录为/home/ubuntu/kirocli-platform
---

## 步骤 7：配置 AWS Secrets Manager（v1.1 必需）

**v1.1 重要变化**：敏感配置（SECRET_KEY、SAML 证书等）必须存储在 AWS Secrets Manager 中，不再直接写入 .env 文件。

### 7.1 配置 EC2 IAM Role（推荐方式）

```bash
# 1. 在 AWS 控制台创建 IAM Role
# Role 名称：kirocli-platform-ec2-role
# 信任实体：EC2
# 权限策略：
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws-cn:secretsmanager:cn-northwest-1:<ACCOUNT_ID>:secret:kirocli-platform/production-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "identitystore:DescribeUser",
        "identitystore:ListUsers"
      ],
      "Resource": "*"
    }
  ]
}

# 2. 将 IAM Role 附加到 EC2 实例
# 在 EC2 控制台 → 实例 → 操作 → 安全 → 修改 IAM 角色
```

### 7.2 创建 Secrets Manager 密钥

```bash
# 在本地机器执行（需要配置 AWS CLI）
# 生成随机 SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)

# 从 AWS IAM Identity Center 下载证书并处理
# 1. 下载证书文件（.pem 或 .cer 格式）
# 2. 提取证书内容（去掉 BEGIN/END 行，只保留 base64 内容）
CERT_CONTENT=$(cat your-cert.pem | grep -v "BEGIN CERTIFICATE" | grep -v "END CERTIFICATE" | tr -d '\n')

# 创建密钥
aws secretsmanager create-secret \
  --name kirocli-platform/production \
  --description "KiroCLI Platform v1.1 敏感配置" \
  --secret-string "{\"SECRET_KEY\":\"$SECRET_KEY\",\"SAML_IDP_X509_CERT\":\"$CERT_CONTENT\"}" \
  --region cn-northwest-1

# 验证密钥创建成功
aws secretsmanager get-secret-value \
  --secret-id kirocli-platform/production \
  --region cn-northwest-1 \
  --query 'SecretString' \
  --output text | jq .
```

### 7.3 配置后端环境

```bash
cd /home/ubuntu/kirocli-platform/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

创建 `.env` 文件（**注意：不再包含 SECRET_KEY 和 SAML_IDP_X509_CERT**）：

```bash
nano .env
```

填入以下内容：

```env
APP_NAME=KiroCLI Platform
ENVIRONMENT=production
DEBUG=false

DATABASE_URL=sqlite:////home/ubuntu/kirocli-platform/backend/data.db

SAML_IDP_ENTITY_ID=<从 AWS IAM Identity Center 应用配置页复制>
SAML_IDP_SSO_URL=<从 AWS IAM Identity Center 应用配置页复制>
SAML_SP_ENTITY_ID=http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/callback

IAM_IDENTITY_STORE_ID=<你的 Identity Store ID>
AWS_REGION=cn-northwest-1

GOTTY_PRIMARY_PORT=7860
GOTTY_PORT_START=7861
GOTTY_PORT_END=7960
GOTTY_PATH=/usr/local/bin/gotty
KIRO_CLI_PATH=<kiro-cli 绝对路径，用 which kiro-cli 查看>
GOTTY_REMOTE_MODE=false
GOTTY_REMOTE_HOST=<YOUR_EC2_IP>
GOTTY_CERT_PATH=/home/ubuntu/kirocli-platform/certs/gotty-cert.pem
GOTTY_KEY_PATH=/home/ubuntu/kirocli-platform/certs/gotty-key.pem

CORS_ORIGINS=["http://<YOUR_EC2_IP>:3000","http://localhost:3000"]

LOG_LEVEL=INFO
LOG_FILE=/home/ubuntu/kirocli-platform/logs/backend.log

JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_MINUTES=5

SECRETS_MANAGER_ENABLED=true
SECRETS_MANAGER_SECRET_NAME=kirocli-platform/production
SECRETS_MANAGER_FALLBACK_TO_ENV=false
```

> **重要说明**：
> - 以上配置不包含 `SECRET_KEY`、`SAML_IDP_X509_CERT`、`SAML_SP_PRIVATE_KEY`，这些敏感数据必须存储在 AWS Secrets Manager 中
> - **v1.1 必须配置 Gotty TLS 证书**：`GOTTY_CERT_PATH` 和 `GOTTY_KEY_PATH`（Nginx 使用 HTTPS 代理到 Gotty）
> - 如果需要配置远程 SSH 模式（`GOTTY_REMOTE_MODE=true`），需要添加：`SSH_HOST`、`SSH_PORT`、`SSH_USER`、`SSH_KEY_PATH`、`SSH_REMOTE_HOME`
> - 如果有生产域名，可以添加：`DOMAIN=your-domain.com`


**配置项说明**：

| 配置项 | 必填 | 说明 | 示例值 |
|--------|------|------|--------|
| `APP_NAME` | 是 | 应用名称 | `KiroCLI Platform` |
| `ENVIRONMENT` | 是 | 运行环境 | `production` / `development` |
| `DEBUG` | 是 | 调试模式 | `false`（生产环境必须为 false） |
| `DATABASE_URL` | 是 | 数据库连接 | `sqlite:////home/ubuntu/kirocli-platform/backend/data.db` |
| `SAML_IDP_ENTITY_ID` | 是 | SAML IDP 实体 ID | 从 IAM Identity Center 获取 |
| `SAML_IDP_SSO_URL` | 是 | SAML SSO 登录 URL | 从 IAM Identity Center 获取 |
| `SAML_SP_ENTITY_ID` | 是 | SAML SP 实体 ID | `http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/metadata` |
| `SAML_SP_ACS_URL` | 是 | SAML 回调 URL | `http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/callback` |
| `IAM_IDENTITY_STORE_ID` | 是 | AWS Identity Store ID | `d-xxxxxxxxxx` |
| `AWS_REGION` | 是 | AWS 区域 | `cn-northwest-1` |
| `GOTTY_PRIMARY_PORT` | 是 | Gotty 主端口 | `7860` |
| `GOTTY_PORT_START` | 是 | Gotty 端口范围起始 | `7861` |
| `GOTTY_PORT_END` | 是 | Gotty 端口范围结束 | `7960` |
| `GOTTY_PATH` | 是 | Gotty 可执行文件路径 | `/usr/local/bin/gotty` |
| `KIRO_CLI_PATH` | 是 | Kiro CLI 绝对路径 | `/usr/bin/kiro-cli` 或 `/usr/local/bin/kiro-cli` |
| `GOTTY_REMOTE_MODE` | 是 | 是否远程部署 Gotty | `false`（本地部署） |
| `GOTTY_REMOTE_HOST` | 是 | Gotty 主机地址 | `<YOUR_EC2_IP>` |
| `SSH_HOST` | 否 | SSH 主机（仅远程模式） | - |
| `SSH_PORT` | 否 | SSH 端口（仅远程模式） | `22` |
| `SSH_USER` | 否 | SSH 用户（仅远程模式） | `ubuntu` |
| `SSH_KEY_PATH` | 否 | SSH 密钥路径（仅远程模式） | - |
| `SSH_REMOTE_HOME` | 否 | 远程主目录（仅远程模式） | `/home/ubuntu` |
| `GOTTY_CERT_PATH` | 是 | Gotty TLS 证书路径 | `/home/ubuntu/kirocli-platform/certs/gotty-cert.pem` |
| `GOTTY_KEY_PATH` | 是 | Gotty TLS 密钥路径 | `/home/ubuntu/kirocli-platform/certs/gotty-key.pem` |
| `CORS_ORIGINS` | 是 | CORS 允许的源 | `["http://<YOUR_EC2_IP>:3000"]` |
| `DOMAIN` | 否 | 生产域名 | - |
| `LOG_LEVEL` | 是 | 日志级别 | `INFO` / `DEBUG` / `WARNING` / `ERROR` |
| `LOG_FILE` | 是 | 日志文件路径 | `/home/ubuntu/kirocli-platform/logs/backend.log` |
| `JWT_ALGORITHM` | 是 | JWT 签名算法 | `HS256` |
| `JWT_EXPIRATION_HOURS` | 是 | JWT 过期时间（小时） | `8` |
| `SESSION_IDLE_TIMEOUT_MINUTES` | 是 | 会话空闲超时（分钟） | `30` |
| `SESSION_CLEANUP_INTERVAL_MINUTES` | 是 | 会话清理间隔（分钟） | `5` |
| `SECRETS_MANAGER_ENABLED` | 是 | 启用 Secrets Manager | `true`（v1.1 必须为 true） |
| `SECRETS_MANAGER_SECRET_NAME` | 是 | Secrets Manager 密钥名称 | `kirocli-platform/production` |
| `SECRETS_MANAGER_FALLBACK_TO_ENV` | 是 | 回退到 .env | `false`（生产环境必须为 false） |

**安全注意事项**：
- ❌ 不要在 .env 中配置 `SECRET_KEY`（必须从 Secrets Manager 加载）
- ❌ 不要在 .env 中配置 `SAML_IDP_X509_CERT`（必须从 Secrets Manager 加载）
- ❌ 不要在 .env 中配置 `SAML_SP_PRIVATE_KEY`（如需使用，必须从 Secrets Manager 加载）
- ✅ 生产环境必须设置 `SECRETS_MANAGER_ENABLED=true`
- ✅ 生产环境必须设置 `SECRETS_MANAGER_FALLBACK_TO_ENV=false`
- ✅ 生产环境必须设置 `DEBUG=false`

```bash
# 创建日志目录
mkdir -p /home/ubuntu/kirocli-platform/logs

# 初始化数据库（v1.1 全新部署）
python scripts/init_db.py
```

### 7.4 验证 Secrets Manager 配置

```bash
# 测试后端能否正常加载密钥
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate

python -c "
from app.config import settings
from app.services.secrets_manager import secrets_loader

print('Secrets Manager Enabled:', settings.SECRETS_MANAGER_ENABLED)
print('Secret Name:', settings.SECRETS_MANAGER_SECRET_NAME)

# 尝试加载密钥
secrets = secrets_loader.load(settings.SECRETS_MANAGER_SECRET_NAME, fallback_to_env=False)
print('Loaded secrets:', list(secrets.keys()))
print('SECRET_KEY loaded:', 'SECRET_KEY' in secrets)
print('SAML_IDP_X509_CERT loaded:', 'SAML_IDP_X509_CERT' in secrets)
"
```

**预期输出**：
```
Secrets Manager Enabled: True
Secret Name: kirocli-platform/production
Loaded secrets: ['SECRET_KEY', 'SAML_IDP_X509_CERT']
SECRET_KEY loaded: True
SAML_IDP_X509_CERT loaded: True
```

**如果失败**：
- 检查 EC2 IAM Role 是否正确附加
- 检查 IAM Role 权限策略是否包含 Secrets Manager 访问权限
- 检查密钥名称是否正确（`kirocli-platform/production`）
- 检查 AWS_REGION 配置是否正确

---

## 步骤 8：配置 AWS SNS 告警通知（可选）

**用途**：异常行为告警通知（登录失败、多IP登录、会话创建频率异常等）

### 8.1 创建 SNS Topic

```bash
# 在本地机器执行
aws sns create-topic \
  --name kirocli-platform-alerts \
  --region cn-northwest-1

# 记录返回的 Topic ARN
# 示例：arn:aws-cn:sns:cn-northwest-1:123456789012:kirocli-platform-alerts
```

### 8.2 订阅告警通知

```bash
# 订阅邮箱
aws sns subscribe \
  --topic-arn arn:aws-cn:sns:cn-northwest-1:<ACCOUNT_ID>:kirocli-platform-alerts \
  --protocol email \
  --notification-endpoint admin@example.com \
  --region cn-northwest-1

# 确认订阅（检查邮箱并点击确认链接）
```

### 8.3 配置 IAM 权限

在 EC2 IAM Role 的权限策略中添加 SNS 发布权限：

```json
{
  "Effect": "Allow",
  "Action": [
    "sns:Publish"
  ],
  "Resource": "arn:aws-cn:sns:cn-northwest-1:<ACCOUNT_ID>:kirocli-platform-alerts"
}
```

### 8.4 在平台中配置 SNS Topic ARN

部署完成后：
1. 使用管理员账号登录平台
2. 进入"设置" → "告警规则"页面
3. 配置 SNS Topic ARN：`arn:aws-cn:sns:cn-northwest-1:<ACCOUNT_ID>:kirocli-platform-alerts`
4. 点击"测试 SNS 通知"按钮验证配置
5. 保存配置

---

## 步骤 9：配置后端 systemd 服务

```bash
sudo tee /etc/systemd/system/kirocli-backend.service << 'EOF'
[Unit]
Description=KiroCLI Platform Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/kirocli-platform/backend
Environment=HOME=/home/ubuntu
Environment=USER=ubuntu
Environment=PATH=/home/ubuntu/kirocli-platform/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/ubuntu/kirocli-platform/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable kirocli-backend
sudo systemctl start kirocli-backend
sudo systemctl status kirocli-backend
```

---

## 步骤 10：构建前端

```bash
cd /home/ubuntu/kirocli-platform/frontend

# 内存不足（< 2GB）时先加 swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

npm install
npm run build
# 构建成功会显示 ✓ built in xx.xxs
```

---

## 步骤 11：配置 Nginx（v1.1 重要变化）

**v1.1 变化**：使用项目中的 `nginx/kirocli` 配置文件，包含 Gotty 动态路由配置。

### 10.1 部署 Nginx 配置文件

**重要**：v1.1 的 Nginx 配置使用了 `include` 指令引用动态生成的配置文件，需要先创建这些文件。

```bash
# 1. 复制静态配置文件到 Nginx 目录
sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli_map.conf /etc/nginx/conf.d/
sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli /etc/nginx/sites-available/kirocli

# 2. 创建动态配置文件（由后端自动维护）
# 这些文件必须存在，否则 nginx -t 会报错
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo touch /etc/nginx/conf.d/ip_whitelist.conf

# 3. 设置正确的权限（允许 ubuntu 用户写入）
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/ip_whitelist.conf

# 4. 写入初始内容（避免空文件导致 Nginx 启动失败）
cat | sudo tee /etc/nginx/conf.d/gotty_routes.conf > /dev/null << 'EOF'
# 由 KiroCLI Platform 自动生成，请勿手动修改
# Token 到 Gotty 端口的映射
map $session_token_var $gotty_backend_port {
    default 0;
}
EOF

cat | sudo tee /etc/nginx/conf.d/ip_whitelist.conf > /dev/null << 'EOF'
# 由 KiroCLI Platform 自动生成，请勿手动修改
# IP 白名单检查
map $remote_addr $ip_allowed {
    default 1;
}
EOF

# 5. 创建软链接
sudo ln -sf /etc/nginx/sites-available/kirocli /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 6. 修复前端 dist 目录权限（避免 Nginx 500）
chmod 755 /home/ubuntu
chmod -R 755 /home/ubuntu/kirocli-platform/frontend/dist

# 7. 测试配置
sudo nginx -t

# 8. 重启 Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

**配置文件说明**：
- `kirocli_map.conf` - 从 URI 提取 session token（静态配置）
- `gotty_routes.conf` - token→port 映射（后端动态生成）
- `ip_whitelist.conf` - IP 白名单检查（后端动态生成）
- `kirocli` - 主站点配置（静态配置）

### 10.2 Nginx 配置说明

v1.1 的 `nginx/kirocli` 配置文件包含以下关键特性：

1. **Gotty 动态路由映射**：
   ```nginx
   map $request_uri $gotty_backend {
       ~^/terminal/(?<session_id>[^/]+)/(?<random_url>.+)$ "http://127.0.0.1:$gotty_port_map_$session_id/$random_url";
   }
   ```

2. **通用终端 location 块**：
   ```nginx
   location ~ ^/terminal/[^/]+/ {
       proxy_pass $gotty_backend;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       # ... 其他 WebSocket 配置
   }
   ```

3. **端口映射配置**：
   - 后端通过 API 动态更新 Nginx 配置
   - 每个会话 ID 映射到对应的 Gotty 端口
   - 无需为每个会话创建独立的 location 块

---

## 步骤 12：配置 AWS IAM Identity Center

在 AWS IAM Identity Center 控制台，找到你的 SAML 应用，更新：

| 字段 | 值 |
|------|-----|
| Application ACS URL | `http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/callback` |
| Application SAML audience（Entity ID） | `http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/metadata` |

Attribute mappings 配置：

| User attribute in the application | Maps to | Format |
|---|---|---|
| Subject | `${user:email}` | emailAddress |
| email | `${user:email}` | unspecified |
| groups | `${user:groups}` | unspecified |

> **注意**：Subject 必须用 `${user:email}`，用 `${user:name}` 会报 "No access" 错误。

分配用户/组后，确认用户已在 IAM Identity Center 中设置了主邮箱。

---

## 步骤 13：手工验证 Gotty + Kiro CLI

在通过平台启动会话之前，先手工验证 Gotty 能否正常加载 kiro-cli。

**必须以 ubuntu 用户执行（不能用 sudo）：**

```bash
# 1. 确认 kiro-cli 可用且已登录
kiro-cli --version

# 2. 手工启动 Gotty（使用 TLS 和随机 URL）
gotty \
  --address 127.0.0.1 \
  --port 7862 \
  --permit-write \
  --reconnect \
  --random-url \
  --random-url-length 16 \
  --ws-origin ".*" \
  --tls \
  --tls-crt /home/ubuntu/kirocli-platform/certs/gotty-cert.pem \
  --tls-key /home/ubuntu/kirocli-platform/certs/gotty-key.pem \
  $(which kiro-cli)
```

启动后会输出类似：
```
HTTP server is listening at: https://127.0.0.1:7862/abcd1234efgh5678/
```

**v1.1 重要变化**：
- Gotty 使用 HTTPS/TLS（`--tls` 参数）
- Gotty 绑定 `127.0.0.1`（仅本地访问），不再绑定 `0.0.0.0`
- 安全组不开放 7860-7960 端口，外部无法直接访问 Gotty
- 所有终端访问必须通过 Nginx 反代：`http://<YOUR_EC2_IP>:3000/terminal/...`

**测试方式**：
```bash
# 在 EC2 本地测试（可以访问，但需要忽略证书警告）
curl -k https://127.0.0.1:7862/abcd1234efgh5678/

# 通过 Nginx 反代访问（推荐方式）
# 注意：需要先在后端创建会话并配置 Nginx 路由
curl http://127.0.0.1:3000/terminal/test-session/abcd1234efgh5678/
```

验证完成后按 `Ctrl+C` 停止。

---

## 步骤 14：验证完整部署

```bash
# 检查后端服务
sudo systemctl status kirocli-backend

# 检查后端 API
curl http://127.0.0.1:8000/health

# 检查 Nginx
sudo systemctl status nginx

# 检查端口监听
ss -tlnp | grep -E '3000|8000'
```

浏览器访问 `http://<YOUR_EC2_IP>:3000`，应显示登录页面，点击 SSO 登录后跳转到 AWS IAM Identity Center。

---

## 步骤 15：清理 .env 中的敏感数据（生产环境必需）

**重要安全步骤**：验证 Secrets Manager 配置正常后，必须从 .env 文件中移除敏感数据。

### 15.1 验证 Secrets Manager 正常工作

```bash
# 1. 确认平台可以正常登录和使用
# 2. 检查后端日志，确认没有 Secrets Manager 相关错误
sudo journalctl -u kirocli-backend -n 100 | grep -i "secret"

# 3. 验证密钥加载成功
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
python -c "
from app.services.secrets_manager import secrets_loader
sources = secrets_loader.get_load_sources()
print('Configuration sources:')
for key, source in sources.items():
    print(f'  {key}: {source}')
"
```

**预期输出**：
```
Configuration sources:
  SECRET_KEY: secrets_manager
  SAML_IDP_X509_CERT: secrets_manager
```

### 15.2 备份当前 .env 文件

```bash
cd /home/ubuntu/kirocli-platform/backend
cp .env .env.backup
```

### 15.3 从 .env 中移除敏感数据

**注意**：以下敏感数据应该已经不在 .env 中（因为我们在步骤 7 中就没有添加），但为了确保安全，请再次确认：

```bash
# 检查 .env 中是否还有敏感数据
grep -E "SECRET_KEY|SAML_IDP_X509_CERT|SAML_SP_PRIVATE_KEY" .env

# 如果有输出，说明还有敏感数据，需要手动删除
nano .env
# 删除以下行（如果存在）：
# SECRET_KEY=...
# SAML_IDP_X509_CERT=...
# SAML_SP_PRIVATE_KEY=...
```

### 15.4 验证清理后系统仍正常运行

```bash
# 重启后端服务
sudo systemctl restart kirocli-backend

# 等待 5 秒
sleep 5

# 检查服务状态
sudo systemctl status kirocli-backend

# 检查日志
sudo journalctl -u kirocli-backend -n 50 --no-pager

# 测试登录
curl -I http://127.0.0.1:8000/api/v1/health
```

**预期结果**：
- 服务正常启动
- 日志显示 "Loaded X secrets from Secrets Manager"
- 健康检查返回 200 OK
- 可以正常登录平台

### 15.5 安全检查清单

- [ ] Secrets Manager 配置正确，密钥加载成功
- [ ] .env 文件中不包含 SECRET_KEY
- [ ] .env 文件中不包含 SAML_IDP_X509_CERT
- [ ] .env 文件中不包含 SAML_SP_PRIVATE_KEY
- [ ] 后端服务正常运行
- [ ] 平台可以正常登录和使用
- [ ] 已备份原始 .env 文件（.env.backup）

**如果出现问题**：
```bash
# 恢复备份
cp .env.backup .env
sudo systemctl restart kirocli-backend

# 重新检查 Secrets Manager 配置
```

---

## 代码更新流程（v1.1）

**v1.1 变化**：需要同步更新 Nginx 配置文件。

```bash
EC2_IP=<YOUR_EC2_IP>
KEY=/path/to/your-key.pem

# 1. 上传后端代码
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/backend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/backend/

# 2. 上传前端源码
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/frontend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/frontend/

# 3. 上传 Nginx 配置（v1.1 新增）
rsync -avz \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/nginx/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/nginx/

# 4. 更新 Nginx 配置并重启
ssh -i $KEY ubuntu@$EC2_IP << 'ENDSSH'
sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli /etc/nginx/sites-available/kirocli
sudo nginx -t && sudo systemctl reload nginx
ENDSSH

# 5. 重启后端
ssh -i $KEY ubuntu@$EC2_IP "sudo systemctl restart kirocli-backend"

# 6. 重新构建前端
ssh -i $KEY ubuntu@$EC2_IP "cd /home/ubuntu/kirocli-platform/frontend && npm run build"
```

---

## v1.1 新功能说明

### 1. 终端 URL 封装

**问题背景**：
- v1.0 中前端直接拼接 Gotty URL，暴露了内部端口和随机 URL
- 用户可以直接访问 Gotty 端口，绕过平台权限控制

**v1.1 解决方案**：
- 前端通过 `/api/v1/sessions/{session_id}/terminal-url` 获取封装后的 URL
- 后端返回格式：`http://<DOMAIN>:3000/terminal/{session_id}/{random_url}`
- Nginx 通过 map 指令动态路由到对应的 Gotty 端口
- 用户无法直接访问 Gotty 端口（安全组已关闭）

### 2. 设备指纹采集

**实现方式**：
- 前端使用 `device-fingerprint.ts` 工具生成设备指纹
- 登录成功后通过 `/api/v1/users/me/device` 上报设备信息
- 后端存储设备指纹，用于异常登录检测和审计

### 3. Nginx 动态路由

**技术实现**：
- 使用 `map` 指令将会话 ID 映射到 Gotty 端口
- 通用 `location ~ ^/terminal/[^/]+/` 块处理所有终端请求
- 后端通过 API 动态更新 Nginx 配置中的端口映射

**优势**：
- 无需为每个会话创建独立的 location 块
- 配置文件更简洁，易于维护
- 支持动态添加/删除会话路由

---

## 常见问题排查

### Nginx 配置测试失败 - include 文件不存在（v1.1 特有）

**错误信息**：
```
nginx: [emerg] open() "/etc/nginx/conf.d/gotty_routes.conf" failed (2: No such file or directory)
```

**原因**：v1.1 的 Nginx 配置使用了 `include` 指令引用动态生成的配置文件，但这些文件不存在。

**解决方法**：
```bash
# 1. 创建必需的配置文件
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo touch /etc/nginx/conf.d/ip_whitelist.conf

# 2. 设置权限
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/ip_whitelist.conf

# 3. 写入初始内容
cat | sudo tee /etc/nginx/conf.d/gotty_routes.conf > /dev/null << 'EOF'
# 由 KiroCLI Platform 自动生成，请勿手动修改
map $session_token_var $gotty_backend_port {
    default 0;
}
EOF

cat | sudo tee /etc/nginx/conf.d/ip_whitelist.conf > /dev/null << 'EOF'
# 由 KiroCLI Platform 自动生成，请勿手动修改
map $remote_addr $ip_allowed {
    default 1;
}
EOF

# 4. 测试配置
sudo nginx -t
```

### Gotty 终端全黑 / connection close

最常见原因是 `KIRO_CLI_PATH` 配置错误。

```bash
# 1. 确认 kiro-cli 实际路径
which kiro-cli

# 2. 检查 .env 中的配置是否与上面一致
grep KIRO_CLI_PATH ~/kirocli-platform/backend/.env

# 3. 如果不一致，修正并重启
sed -i "s|KIRO_CLI_PATH=.*|KIRO_CLI_PATH=$(which kiro-cli)|" ~/kirocli-platform/backend/.env
sudo systemctl restart kirocli-backend
```

其他原因：
- kiro-cli 未登录认证（先手工运行 `kiro-cli` 完成登录）
- Nginx 配置错误（检查 `sudo nginx -t`）

### 终端 URL 404 错误（v1.1 特有）

```bash
# 1. 检查 Nginx 配置是否正确部署
sudo nginx -t
cat /etc/nginx/sites-available/kirocli | grep -A 5 "map \$request_uri"

# 2. 检查 Nginx 错误日志
sudo tail -50 /var/log/nginx/error.log

# 3. 确认后端返回的 terminal_url 格式正确
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://127.0.0.1:8000/api/v1/sessions/<SESSION_ID>/terminal-url
```

### 前端构建被 OOM Killer 杀掉

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
npm run build
```

### Nginx 500 错误

```bash
sudo tail -20 /var/log/nginx/error.log
# 通常是权限问题
chmod 755 /home/ubuntu
chmod -R 755 /home/ubuntu/kirocli-platform/frontend/dist
sudo systemctl restart nginx
```

### 后端服务启动失败

```bash
sudo journalctl -u kirocli-backend -n 50 --no-pager
```

### SAML invalid_response

检查 `.env` 中 `SAML_SP_ACS_URL` 与 AWS 控制台 Application ACS URL 是否完全一致（协议、IP、端口、路径）。

常见错误：`SAML_IDP_SSO_URL` 写成 `https:https://...`（多了一个 `https:`），需要修正。

### SAML 登录后循环跳转（302 无限循环）

cookie 未正确设置。确认 `saml_callback` 是在 `RedirectResponse` 对象上调用 `set_cookie`，而不是在 `response` 参数上。

### SAML "No access" 错误

IAM Identity Center Attribute mappings 中 Subject 必须配置为 `${user:email}`（Format: emailAddress），不能用 `${user:name}`。

---

## 数据库初始化说明

v1.1 提供了两个数据库脚本：

### 1. init_db.py - 全新部署
适用于全新安装 v1.1，数据库文件不存在或为空。

```bash
python scripts/init_db.py
```

**功能**：
- 创建所有表（v1.0 基础表 + v1.1 新增表）
- 写入默认数据（管理员用户、组角色映射、告警规则、系统配置）
- v1.1 新增表包括：
  - `ip_whitelist` - IP 白名单
  - `audit_logs` - 审计日志
  - `alert_rules` / `alert_events` - 告警规则和事件
  - `refresh_tokens` / `blacklisted_tokens` - Token 管理
  - `user_devices` - 设备指纹
  - `system_config` - 系统配置

### 2. upgrade_db.py - 从 v1.0 升级
适用于已有 v1.0 运行中的数据库，升级到 v1.1。

```bash
python scripts/upgrade_db.py
```

**功能**：
- 检测 v1.0 数据库是否存在
- 新增 v1.1 的 8 张表（幂等操作，已存在的表跳过）
- 写入 v1.1 预置数据（告警规则、系统配置默认值）
- **不修改、不删除任何 v1.0 现有表和数据**

---

## v1.1 升级指南（从 v1.0 升级）

如果你已经部署了 v1.0，按以下步骤升级到 v1.1：

1. **备份数据库**：
   ```bash
   cp /home/ubuntu/kirocli-platform/backend/data.db /home/ubuntu/kirocli-platform/backend/data.db.backup
   ```

2. **上传新代码**（参考"代码更新流程"章节）

3. **运行数据库升级脚本**：
   ```bash
   cd /home/ubuntu/kirocli-platform/backend
   source .venv/bin/activate
   python scripts/upgrade_db.py
   ```

4. **更新安全组**：
   - 移除 7860-7960 端口的入站规则
   - 保留 3000 端口

5. **部署 Nginx 配置**：
   ```bash
   # 复制静态配置文件
   sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli_map.conf /etc/nginx/conf.d/
   sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli /etc/nginx/sites-available/kirocli
   
   # 创建动态配置文件（必须存在，否则 nginx -t 会报错）
   sudo touch /etc/nginx/conf.d/gotty_routes.conf
   sudo touch /etc/nginx/conf.d/ip_whitelist.conf
   sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
   sudo chown ubuntu:ubuntu /etc/nginx/conf.d/ip_whitelist.conf
   
   # 写入初始内容
   cat | sudo tee /etc/nginx/conf.d/gotty_routes.conf > /dev/null << 'EOF'
# 由 KiroCLI Platform 自动生成，请勿手动修改
map $session_token_var $gotty_backend_port {
    default 0;
}
EOF
   
   cat | sudo tee /etc/nginx/conf.d/ip_whitelist.conf > /dev/null << 'EOF'
# 由 KiroCLI Platform 自动生成，请勿手动修改
map $remote_addr $ip_allowed {
    default 1;
}
EOF
   
   # 测试并重载
   sudo nginx -t && sudo systemctl reload nginx
   ```

6. **重启服务**：
   ```bash
   sudo systemctl restart kirocli-backend
   ```

7. **验证升级**：
   - 登录平台，创建新会话
   - 检查终端 URL 格式是否为 `/terminal/{session_id}/{random_url}`
   - 确认无法直接访问 Gotty 端口（应该被安全组阻止）
   - 检查新功能：设备指纹、审计日志、告警规则等
