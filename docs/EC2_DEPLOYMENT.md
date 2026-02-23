# EC2 部署指南

> 环境：AWS EC2（中国区）Ubuntu 22.04，前后端和 Gotty 均部署在同一台 EC2。

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

在 AWS 控制台为 EC2 实例的安全组添加以下入站规则：

| 端口 | 协议 | 来源 | 用途 |
|------|------|------|------|
| 22 | TCP | 你的 IP | SSH |
| 3000 | TCP | 0.0.0.0/0 | 前端（Nginx） |
| 7860-7960 | TCP | 0.0.0.0/0 | Gotty 终端 |

> 建议将 7860-7960 的来源限制为公司/团队 IP 段，减少暴露面。

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

## 步骤 6：上传代码到 EC2

在**本地机器**执行：

```bash
EC2_IP=<YOUR_EC2_IP>
KEY=/path/to/your-key.pem

# 创建远端目录
ssh -i $KEY ubuntu@$EC2_IP \
  "mkdir -p /home/ubuntu/kirocli-platform/backend /home/ubuntu/kirocli-platform/frontend"

# 上传后端
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/backend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/backend/

# 上传前端
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/frontend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/frontend/
```

---

## 步骤 7：配置后端环境

```bash
cd /home/ubuntu/kirocli-platform/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

创建 `.env` 文件（**注意：不能有行内注释，pydantic-settings 不支持**）：

```bash
nano .env
```

填入以下内容，替换 `<>` 中的占位符：

```env
APP_NAME=KiroCLI Platform
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<随机32位以上字符串，可用 openssl rand -hex 32 生成>

DATABASE_URL=sqlite:////home/ubuntu/kirocli-platform/backend/data.db

SAML_IDP_ENTITY_ID=<从 AWS IAM Identity Center 应用配置页复制>
SAML_IDP_SSO_URL=<从 AWS IAM Identity Center 应用配置页复制，注意不要有重复的 https:>
SAML_IDP_X509_CERT=<从 AWS IAM Identity Center 下载的证书内容，去掉 BEGIN/END 行>
SAML_SP_ENTITY_ID=http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=http://<YOUR_EC2_IP>:3000/api/v1/auth/saml/callback

GOTTY_PRIMARY_PORT=7860
GOTTY_PORT_START=7861
GOTTY_PORT_END=7960
GOTTY_PATH=/usr/local/bin/gotty
KIRO_CLI_PATH=<kiro-cli 绝对路径，用 which kiro-cli 查看，例如 /usr/bin/kiro-cli>
GOTTY_REMOTE_MODE=false
GOTTY_REMOTE_HOST=<YOUR_EC2_IP>

CORS_ORIGINS=["http://<YOUR_EC2_IP>:3000","http://localhost:3000"]

LOG_LEVEL=INFO
LOG_FILE=/home/ubuntu/kirocli-platform/logs/backend.log

JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_MINUTES=5
```

```bash
# 创建日志目录
mkdir -p /home/ubuntu/kirocli-platform/logs

# 初始化数据库
python scripts/init_db.py
```

---

## 步骤 8：配置后端 systemd 服务

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

## 步骤 9：构建前端

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

## 步骤 10：配置 Nginx

```bash
sudo tee /etc/nginx/sites-available/kirocli << 'EOF'
server {
    listen 3000;
    server_name _;

    root /home/ubuntu/kirocli-platform/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/kirocli /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 修复前端 dist 目录权限（避免 Nginx 500）
chmod 755 /home/ubuntu
chmod -R 755 /home/ubuntu/kirocli-platform/frontend/dist

sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 步骤 11：配置 AWS IAM Identity Center

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

## 步骤 12：手工验证 Gotty + Kiro CLI

在通过平台启动会话之前，先手工验证 Gotty 能否正常加载 kiro-cli。

**必须以 ubuntu 用户执行（不能用 sudo）：**

```bash
# 1. 确认 kiro-cli 可用且已登录
kiro-cli --version

# 2. 手工启动 Gotty（使用随机 URL）
gotty \
  --address 0.0.0.0 \
  --port 7862 \
  --permit-write \
  --reconnect \
  --random-url \
  --random-url-length 16 \
  --ws-origin ".*" \
  $(which kiro-cli)
```

启动后会输出类似：
```
HTTP server is listening at: http://0.0.0.0:7862/abcd1234efgh5678/
```

用浏览器访问 `http://<YOUR_EC2_IP>:7862/abcd1234efgh5678/`，应显示 Kiro CLI 终端界面。

验证完成后按 `Ctrl+C` 停止。

---

## 步骤 13：验证完整部署

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

## 代码更新流程

```bash
EC2_IP=<YOUR_EC2_IP>
KEY=/path/to/your-key.pem

# 1. 上传后端代码
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/backend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/backend/

# 2. 重启后端
ssh -i $KEY ubuntu@$EC2_IP "sudo systemctl restart kirocli-backend"

# 3. 上传前端源码
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i $KEY" \
  vue-kirocli-platform/frontend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/frontend/

# 4. 重新构建前端
ssh -i $KEY ubuntu@$EC2_IP "cd /home/ubuntu/kirocli-platform/frontend && npm run build"
```

---

## 常见问题排查

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
- 安全组未开放 7860-7960 端口
- kiro-cli 未登录认证（先手工运行 `kiro-cli` 完成登录）

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
