# EC2 部署指南

> 环境：AWS EC2（中国区）Ubuntu 22.04，前后端和 Gotty 均部署在同一台 EC2。

---

## 前置信息

| 项目 | 值 |
|------|-----|
| EC2 公网 IP | `69.234.199.116`（示例，以实际为准） |
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

---

## 步骤 2：连接 EC2

```bash
ssh -i /Users/lilinyi/Downloads/william-website-test.pem \
  ubuntu@ec2-69-234-199-116.cn-northwest-1.compute.amazonaws.com.cn
```

---

## 步骤 3：安装系统依赖

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl wget nginx python3 python3-pip python3-venv

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
# 下载 gotty（根据架构选择）
# x86_64:
wget https://github.com/sorenisanerd/gotty/releases/download/v1.5.0/gotty_v1.5.0_linux_amd64.tar.gz
tar -xzf gotty_v1.5.0_linux_amd64.tar.gz
sudo mv gotty /usr/local/bin/gotty
sudo chmod +x /usr/local/bin/gotty
gotty --version
```

---

## 步骤 5：上传代码到 EC2

在**本地机器**执行（不是 EC2）：

```bash
# 创建远端目录
ssh -i /Users/lilinyi/Downloads/william-website-test.pem \
  ubuntu@ec2-69-234-199-116.cn-northwest-1.compute.amazonaws.com.cn \
  "mkdir -p /home/ubuntu/kirocli-platform/backend /home/ubuntu/kirocli-platform/frontend"

# 上传后端
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i /Users/lilinyi/Downloads/william-website-test.pem" \
  vue-kirocli-platform/backend/ \
  ubuntu@ec2-69-234-199-116.cn-northwest-1.compute.amazonaws.com.cn:/home/ubuntu/kirocli-platform/backend/

# 上传前端
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i /Users/lilinyi/Downloads/william-website-test.pem" \
  vue-kirocli-platform/frontend/ \
  ubuntu@ec2-69-234-199-116.cn-northwest-1.compute.amazonaws.com.cn:/home/ubuntu/kirocli-platform/frontend/
```

---

## 步骤 6：配置后端环境

在 **EC2** 上执行：

```bash
cd /home/ubuntu/kirocli-platform/backend

# 创建 Python 虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 创建 .env 文件（注意：不能有行内注释）
cat > .env << 'EOF'
APP_NAME=KiroCLI Platform
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=请替换为随机32位以上字符串

DATABASE_URL=sqlite:///./data.db

SAML_IDP_ENTITY_ID=https://portal.sso.cn-northwest-1.amazonaws.com.cn/saml/assertion/你的IDP实体ID
SAML_IDP_SSO_URL=https://portal.sso.cn-northwest-1.amazonaws.com.cn/saml/assertion/你的SSO_URL
SAML_IDP_X509_CERT=你的IdP证书内容（去掉BEGIN/END行，只保留base64内容）
SAML_SP_ENTITY_ID=http://69.234.199.116:3000/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=http://69.234.199.116:3000/api/v1/auth/saml/callback

IAM_IDENTITY_STORE_ID=d-xxxxxxxxxx
AWS_REGION=cn-northwest-1

GOTTY_PRIMARY_PORT=7860
GOTTY_PORT_START=7861
GOTTY_PORT_END=7960
GOTTY_CERT_PATH=
GOTTY_KEY_PATH=
GOTTY_PATH=/usr/local/bin/gotty
KIRO_CLI_PATH=kiro-cli
GOTTY_REMOTE_MODE=false
GOTTY_REMOTE_HOST=69.234.199.116

CORS_ORIGINS=["http://69.234.199.116:3000","http://localhost:3000"]

DOMAIN=69.234.199.116

LOG_LEVEL=INFO
LOG_FILE=/var/log/kirocli-platform/backend.log

JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_MINUTES=5
EOF

# 创建日志目录
sudo mkdir -p /var/log/kirocli-platform
sudo chown ubuntu:ubuntu /var/log/kirocli-platform

# 初始化数据库
python scripts/init_db.py
```

---

## 步骤 7：配置后端 systemd 服务

```bash
sudo tee /etc/systemd/system/kirocli-backend.service << 'EOF'
[Unit]
Description=KiroCLI Platform Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/kirocli-platform/backend
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

## 步骤 8：构建前端

```bash
cd /home/ubuntu/kirocli-platform/frontend

# 安装依赖
npm install

# 构建（如果内存不足，先增加 swap）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 执行构建
npm run build
# 构建产物在 dist/ 目录
```

---

## 步骤 9：配置 Nginx

```bash
sudo tee /etc/nginx/sites-available/kirocli << 'EOF'
server {
    listen 3000;
    server_name _;

    # 前端静态文件
    root /home/ubuntu/kirocli-platform/frontend/dist;
    index index.html;

    # 前端路由（Vue Router history 模式）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反代
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 支持（Gotty 终端）
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
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## 步骤 10：更新 AWS IAM Identity Center 配置

在 AWS IAM Identity Center 控制台，找到你的 SAML 应用，更新以下两个字段：

| 字段 | 值 |
|------|-----|
| Application ACS URL | `http://69.234.199.116:3000/api/v1/auth/saml/callback` |
| Application SAML audience（Entity ID） | `http://69.234.199.116:3000/api/v1/auth/saml/metadata` |

> 注意：IP 和端口必须与 `.env` 中的 `SAML_SP_ACS_URL` 和 `SAML_SP_ENTITY_ID` 完全一致。

---

## 步骤 11：安装 Kiro CLI（以 ubuntu 用户运行）

```bash
# 以 ubuntu 用户安装 kiro-cli（不要用 sudo）
# 参考 Kiro 官方安装文档，安装后验证：
kiro-cli --version

# 确认认证 token 存在
ls ~/.config/kiro/  # 或对应的配置目录
```

> Gotty 必须以 ubuntu 用户启动（不能用 sudo），否则找不到 kiro-cli 的认证 token。

---

## 步骤 12：验证部署

```bash
# 1. 检查后端服务状态
sudo systemctl status kirocli-backend

# 2. 检查后端 API 是否正常
curl http://127.0.0.1:8000/api/v1/health

# 3. 检查 Nginx 状态
sudo systemctl status nginx

# 4. 检查端口监听
ss -tlnp | grep -E '3000|8000|7860'
```

浏览器访问 `http://69.234.199.116:3000`，应显示登录页面。

点击 "SSO 登录" 按钮，应跳转到 AWS IAM Identity Center 登录页。

---

## 常见问题

### 前端构建被 OOM Killer 杀掉

```bash
# 增加 swap 空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# 再次执行 npm run build
```

### 后端服务启动失败

```bash
# 查看详细日志
sudo journalctl -u kirocli-backend -n 50 --no-pager
# 或查看应用日志
tail -f /var/log/kirocli-platform/backend.log
```

### SAML "Resource not found" 错误

确认 AWS IAM Identity Center 中配置的 ACS URL 和 Entity ID 与 `.env` 中的值完全一致，且使用 EC2 公网 IP + 3000 端口（不能用 localhost）。

### Gotty 启动后无法访问

确认安全组已开放 7860-7960 端口，且 Gotty 以 ubuntu 用户启动（非 root）。

---

## 代码更新流程

每次本地修改代码后，重新上传并重启服务：

```bash
# 本地执行：上传后端
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i /Users/lilinyi/Downloads/william-website-test.pem" \
  vue-kirocli-platform/backend/ \
  ubuntu@ec2-69-234-199-116.cn-northwest-1.compute.amazonaws.com.cn:/home/ubuntu/kirocli-platform/backend/

# EC2 上重启后端
sudo systemctl restart kirocli-backend

# 本地执行：上传前端源码
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i /Users/lilinyi/Downloads/william-website-test.pem" \
  vue-kirocli-platform/frontend/ \
  ubuntu@ec2-69-234-199-116.cn-northwest-1.compute.amazonaws.com.cn:/home/ubuntu/kirocli-platform/frontend/

# EC2 上重新构建前端
cd /home/ubuntu/kirocli-platform/frontend && npm run build
```
