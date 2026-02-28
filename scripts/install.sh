#!/bin/bash
set -e

# KiroCLI Platform v1.1 自动化部署脚本
# 用途：在 EC2 Ubuntu 22.04 上一键部署 KiroCLI Platform

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo_step() {
    echo -e "\n${BLUE}==== $1 ====${NC}\n"
}

# 检查是否以 root 运行
if [ "$EUID" -eq 0 ]; then
    echo_error "请不要使用 root 或 sudo 运行此脚本"
    echo_info "正确用法: ./install.sh"
    exit 1
fi

# 欢迎信息
clear
echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        KiroCLI Platform v1.1 自动化部署脚本               ║
║                                                           ║
║  此脚本将自动完成以下任务：                                ║
║  • 安装系统依赖（Node.js, Python, Nginx 等）              ║
║  • 安装 Gotty 终端工具                                    ║
║  • 生成 TLS 证书                                          ║
║  • 配置后端环境                                           ║
║  • 构建前端                                               ║
║  • 配置 Nginx                                             ║
║  • 配置 systemd 服务                                      ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# 确认继续
read -p "是否继续安装？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo_info "安装已取消"
    exit 0
fi

# 获取 EC2 公网 IP 或域名
echo_step "步骤 1: 获取访问地址信息"

# 尝试自动获取公网 IP
EC2_IP=$(curl -s --connect-timeout 3 https://api.ipify.org 2>/dev/null || echo "")

if [ -z "$EC2_IP" ]; then
    echo_warn "无法自动获取公网 IP"
fi

# 询问用户访问方式
echo ""
echo_info "请选择访问方式："
echo_info "  1. 使用 IP 地址访问（EIP 或公网 IP）"
echo_info "  2. 使用域名访问（ALB 或自定义域名）"
echo_info "  3. 跳过（稍后手动配置）"
echo ""
read -p "请选择 (1/2/3): " -n 1 -r ACCESS_TYPE
echo ""

case $ACCESS_TYPE in
    1)
        if [ -n "$EC2_IP" ]; then
            echo_info "检测到公网 IP: $EC2_IP"
            read -p "是否使用此 IP？(y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                read -p "请输入 IP 地址: " EC2_IP
            fi
        else
            read -p "请输入 IP 地址: " EC2_IP
        fi
        ACCESS_URL="http://$EC2_IP:3000"
        ;;
    2)
        read -p "请输入域名（例如: kirocli.example.com）: " DOMAIN
        ACCESS_URL="http://$DOMAIN:3000"
        EC2_IP="$DOMAIN"
        ;;
    3)
        echo_info "跳过访问地址配置"
        ACCESS_URL="http://YOUR_IP_OR_DOMAIN:3000"
        EC2_IP="YOUR_IP_OR_DOMAIN"
        echo_warn "请稍后手动修改 backend/.env 文件中的 SAML 配置"
        ;;
    *)
        echo_error "无效的选择"
        exit 1
        ;;
esac

echo_info "访问地址: $ACCESS_URL"

# 设置安装目录（脚本所在目录的父目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"
echo_info "项目目录: $INSTALL_DIR"

# 验证项目结构
if [ ! -d "$INSTALL_DIR/backend" ] || [ ! -d "$INSTALL_DIR/frontend" ] || [ ! -d "$INSTALL_DIR/nginx" ]; then
    echo_error "项目目录结构不完整"
    echo_info "请确保以下目录存在："
    echo_info "  - $INSTALL_DIR/backend"
    echo_info "  - $INSTALL_DIR/frontend"
    echo_info "  - $INSTALL_DIR/nginx"
    exit 1
fi

# 步骤 2: 更新系统并安装依赖
echo_step "步骤 2: 安装系统依赖"
echo_info "更新系统包..."
sudo apt update && sudo apt upgrade -y

echo_info "安装基础工具..."
sudo apt install -y git curl wget nginx python3 python3-pip python3-venv sqlite3

# 步骤 3: 安装 Node.js
echo_step "步骤 3: 安装 Node.js 21"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    echo_info "检测到已安装 Node.js: $NODE_VERSION"
    read -p "是否重新安装 Node.js 21？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_NODE=true
    else
        INSTALL_NODE=false
    fi
else
    INSTALL_NODE=true
fi

if [ "$INSTALL_NODE" = true ]; then
    echo_info "安装 nvm..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    
    # 加载 nvm
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    echo_info "安装 Node.js 21..."
    nvm install 21
    nvm use 21
    nvm alias default 21
    
    NODE_VERSION=$(node -v)
    echo_info "Node.js 安装完成: $NODE_VERSION"
fi

# 步骤 4: 安装 Gotty
echo_step "步骤 4: 安装 Gotty"
if command -v gotty &> /dev/null; then
    GOTTY_VERSION=$(gotty --version 2>&1 || echo "unknown")
    echo_info "检测到已安装 Gotty: $GOTTY_VERSION"
    read -p "是否重新安装 Gotty？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_GOTTY=true
    else
        INSTALL_GOTTY=false
    fi
else
    INSTALL_GOTTY=true
fi

if [ "$INSTALL_GOTTY" = true ]; then
    echo_info "下载 Gotty v1.6.0..."
    cd /tmp
    wget -q https://github.com/sorenisanerd/gotty/releases/download/v1.6.0/gotty_v1.6.0_linux_amd64.tar.gz
    tar -xzf gotty_v1.6.0_linux_amd64.tar.gz
    sudo mv gotty /usr/local/bin/gotty
    sudo chmod +x /usr/local/bin/gotty
    rm gotty_v1.6.0_linux_amd64.tar.gz
    
    GOTTY_VERSION=$(gotty --version 2>&1 || echo "unknown")
    echo_info "Gotty 安装完成: $GOTTY_VERSION"
fi

# 步骤 5: 检查 Kiro CLI
echo_step "步骤 5: 检查 Kiro CLI"
if command -v kiro-cli &> /dev/null; then
    KIRO_CLI_PATH=$(which kiro-cli)
    KIRO_CLI_VERSION=$(kiro-cli --version 2>&1 || echo "unknown")
    echo_info "检测到 Kiro CLI: $KIRO_CLI_PATH"
    echo_info "版本: $KIRO_CLI_VERSION"
else
    echo_error "未检测到 Kiro CLI"
    echo_info "请先安装 Kiro CLI，然后重新运行此脚本"
    echo_info "安装文档: https://docs.kiro.ai/installation"
    exit 1
fi

# 步骤 6: 生成 TLS 证书
echo_step "步骤 6: 生成 Gotty TLS 证书"
CERT_DIR="$INSTALL_DIR/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/gotty-cert.pem" ] && [ -f "$CERT_DIR/gotty-key.pem" ]; then
    echo_info "检测到已存在的证书"
    read -p "是否重新生成证书？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        GENERATE_CERT=true
    else
        GENERATE_CERT=false
    fi
else
    GENERATE_CERT=true
fi

if [ "$GENERATE_CERT" = true ]; then
    echo_info "生成自签名证书（CN=127.0.0.1）..."
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout "$CERT_DIR/gotty-key.pem" \
        -out "$CERT_DIR/gotty-cert.pem" \
        -days 365 \
        -subj "/CN=127.0.0.1" 2>/dev/null
    
    echo_info "证书生成完成"
    openssl x509 -in "$CERT_DIR/gotty-cert.pem" -text -noout | grep "Subject:"
fi

# 步骤 7: 配置后端
echo_step "步骤 7: 配置后端环境"
cd "$INSTALL_DIR/backend"

echo_info "创建 Python 虚拟环境..."
python3 -m venv .venv

echo_info "安装 Python 依赖..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 步骤 8: 配置环境变量
echo_step "步骤 8: 配置环境变量"
if [ -f "$INSTALL_DIR/backend/.env" ]; then
    echo_warn "检测到已存在的 .env 文件"
    read -p "是否重新配置？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CONFIGURE_ENV=true
    else
        CONFIGURE_ENV=false
    fi
else
    CONFIGURE_ENV=true
fi

if [ "$CONFIGURE_ENV" = true ]; then
    echo_info "请提供以下配置信息："
    
    read -p "SAML IDP Entity ID: " SAML_IDP_ENTITY_ID
    read -p "SAML IDP SSO URL: " SAML_IDP_SSO_URL
    read -p "IAM Identity Store ID: " IAM_IDENTITY_STORE_ID
    read -p "AWS Region (默认: cn-northwest-1): " AWS_REGION
    AWS_REGION=${AWS_REGION:-cn-northwest-1}
    
    read -p "是否启用 AWS Secrets Manager？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        SECRETS_MANAGER_ENABLED=true
        read -p "Secrets Manager Secret Name (默认: kirocli-platform/production): " SECRET_NAME
        SECRET_NAME=${SECRET_NAME:-kirocli-platform/production}
    else
        SECRETS_MANAGER_ENABLED=false
        echo_warn "未启用 Secrets Manager，需要手动在 .env 中配置 SECRET_KEY"
    fi
    
    # 生成 .env 文件
    cat > "$INSTALL_DIR/backend/.env" << EOF
APP_NAME=KiroCLI Platform
ENVIRONMENT=production
DEBUG=false

DATABASE_URL=sqlite:///$INSTALL_DIR/backend/data.db

SAML_IDP_ENTITY_ID=$SAML_IDP_ENTITY_ID
SAML_IDP_SSO_URL=$SAML_IDP_SSO_URL
SAML_SP_ENTITY_ID=http://$EC2_IP:3000/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=http://$EC2_IP:3000/api/v1/auth/saml/callback

IAM_IDENTITY_STORE_ID=$IAM_IDENTITY_STORE_ID
AWS_REGION=$AWS_REGION

GOTTY_PRIMARY_PORT=7860
GOTTY_PORT_START=7861
GOTTY_PORT_END=7960
GOTTY_PATH=/usr/local/bin/gotty
KIRO_CLI_PATH=$KIRO_CLI_PATH
GOTTY_REMOTE_MODE=false
GOTTY_REMOTE_HOST=$EC2_IP
GOTTY_CERT_PATH=$CERT_DIR/gotty-cert.pem
GOTTY_KEY_PATH=$CERT_DIR/gotty-key.pem

CORS_ORIGINS=["http://$EC2_IP:3000"]

LOG_LEVEL=INFO
LOG_FILE=$INSTALL_DIR/logs/backend.log

JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_MINUTES=5

SECRETS_MANAGER_ENABLED=$SECRETS_MANAGER_ENABLED
EOF

    if [ "$SECRETS_MANAGER_ENABLED" = true ]; then
        cat >> "$INSTALL_DIR/backend/.env" << EOF
SECRETS_MANAGER_SECRET_NAME=$SECRET_NAME
SECRETS_MANAGER_FALLBACK_TO_ENV=false
EOF
    else
        # 生成随机 SECRET_KEY
        SECRET_KEY=$(openssl rand -hex 32)
        cat >> "$INSTALL_DIR/backend/.env" << EOF
SECRET_KEY=$SECRET_KEY
SECRETS_MANAGER_FALLBACK_TO_ENV=true
EOF
    fi
    
    echo_info ".env 文件已生成: $INSTALL_DIR/backend/.env"
fi

# 步骤 9: 初始化数据库
echo_step "步骤 9: 初始化数据库"
mkdir -p "$INSTALL_DIR/logs"
cd "$INSTALL_DIR/backend"
source .venv/bin/activate

if [ -f "$INSTALL_DIR/backend/data.db" ]; then
    echo_warn "检测到已存在的数据库文件"
    read -p "是否重新初始化数据库？(警告：将删除所有数据) (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f "$INSTALL_DIR/backend/data.db"
        python scripts/init_db.py
        echo_info "数据库初始化完成"
    else
        echo_info "跳过数据库初始化"
    fi
else
    python scripts/init_db.py
    echo_info "数据库初始化完成"
fi

# 步骤 10: 配置 systemd 服务
echo_step "步骤 10: 配置 systemd 服务"
echo_info "创建 kirocli-backend.service..."

# 获取当前用户名（不硬编码 ubuntu）
CURRENT_USER=$(whoami)

sudo tee /etc/systemd/system/kirocli-backend.service > /dev/null << EOF
[Unit]
Description=KiroCLI Platform Backend
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR/backend
Environment=HOME=$HOME
Environment=USER=$CURRENT_USER
Environment=PATH=$INSTALL_DIR/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$INSTALL_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable kirocli-backend
echo_info "systemd 服务配置完成"

# 步骤 11: 构建前端
echo_step "步骤 11: 构建前端"
cd "$INSTALL_DIR/frontend"

# 检查内存，如果小于 2GB 则添加 swap
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -lt 2000 ]; then
    echo_warn "检测到内存不足 2GB，创建 swap 文件..."
    if [ ! -f /swapfile ]; then
        sudo fallocate -l 2G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo_info "Swap 文件创建完成"
    fi
fi

echo_info "安装前端依赖..."
npm install

echo_info "构建前端..."
npm run build

echo_info "前端构建完成"

# 步骤 12: 配置 Nginx
echo_step "步骤 12: 配置 Nginx"

# 检查 Nginx 配置文件是否存在
if [ ! -f "$INSTALL_DIR/nginx/kirocli_map.conf" ] || [ ! -f "$INSTALL_DIR/nginx/kirocli" ]; then
    echo_error "Nginx 配置文件不存在"
    echo_info "请确保以下文件存在："
    echo_info "  - $INSTALL_DIR/nginx/kirocli_map.conf"
    echo_info "  - $INSTALL_DIR/nginx/kirocli"
    exit 1
fi

# 创建动态配置文件
echo_info "创建 Nginx 动态配置文件..."
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo touch /etc/nginx/conf.d/ip_whitelist.conf

# 获取当前用户名
CURRENT_USER=$(whoami)
sudo chown $CURRENT_USER:$CURRENT_USER /etc/nginx/conf.d/gotty_routes.conf
sudo chown $CURRENT_USER:$CURRENT_USER /etc/nginx/conf.d/ip_whitelist.conf

# 初始化 gotty_routes.conf
cat | sudo tee /etc/nginx/conf.d/gotty_routes.conf > /dev/null << 'EOF'
# Auto-generated by KiroCLI Platform - do not edit manually
map $session_token_var $gotty_backend_port {
    default 0;
}
EOF

# 初始化 ip_whitelist.conf
cat | sudo tee /etc/nginx/conf.d/ip_whitelist.conf > /dev/null << 'EOF'
# Auto-generated by KiroCLI Platform - do not edit manually
map $remote_addr $ip_allowed {
    default 1;
}
EOF

# 复制 Nginx 配置文件
echo_info "复制 Nginx 配置文件..."
sudo cp "$INSTALL_DIR/nginx/kirocli_map.conf" /etc/nginx/conf.d/
sudo cp "$INSTALL_DIR/nginx/kirocli" /etc/nginx/sites-available/

# 启用站点
sudo ln -sf /etc/nginx/sites-available/kirocli /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 修复权限
chmod 755 $HOME
chmod -R 755 "$INSTALL_DIR/frontend/dist"

# 测试 Nginx 配置
echo_info "测试 Nginx 配置..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo_info "Nginx 配置测试通过"
    sudo systemctl restart nginx
    sudo systemctl enable nginx
    echo_info "Nginx 已重启"
else
    echo_error "Nginx 配置测试失败，请检查配置文件"
    exit 1
fi

# 步骤 13: 启动后端服务
echo_step "步骤 13: 启动后端服务"
sudo systemctl start kirocli-backend

# 等待服务启动
echo_info "等待后端服务启动..."
sleep 5

# 检查服务状态
if sudo systemctl is-active --quiet kirocli-backend; then
    echo_info "后端服务启动成功"
else
    echo_error "后端服务启动失败"
    echo_info "查看日志: sudo journalctl -u kirocli-backend -n 50"
    exit 1
fi

# 步骤 14: 验证部署
echo_step "步骤 14: 验证部署"
echo_info "检查后端健康状态..."

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo_warn "jq 未安装，跳过 JSON 解析"
    HEALTH_CHECK=$(curl -s http://127.0.0.1:8000/api/v1/health || echo "error")
    echo_info "健康检查响应: $HEALTH_CHECK"
else
    HEALTH_CHECK=$(curl -s http://127.0.0.1:8000/api/v1/health | jq -r '.data.status' 2>/dev/null || echo "error")
    
    if [ "$HEALTH_CHECK" = "healthy" ]; then
        echo_info "后端健康检查通过"
    else
        echo_warn "后端健康检查失败，请手动检查"
    fi
fi

# 完成
echo_step "部署完成！"
echo -e "${GREEN}"
cat << EOF
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              🎉 部署成功完成！                             ║
║                                                           ║
║  访问地址: $ACCESS_URL                                     ║
║                                                           ║
║  后续步骤：                                                ║
║                                                           ║
║  1. 配置 AWS Secrets Manager（必需）                       ║
║     在 AWS 控制台创建 Secret：                             ║
║     - Secret 名称: kirocli-platform/production            ║
║     - Secret 内容（JSON 格式）：                           ║
║       {                                                   ║
║         "SECRET_KEY": "<随机生成的密钥>",                  ║
║         "SAML_IDP_X509_CERT": "<IAM Identity Center 证书>" ║
║       }                                                   ║
║     - 确保 EC2 IAM Role 有以下权限：                       ║
║       secretsmanager:GetSecretValue                       ║
║       secretsmanager:DescribeSecret                       ║
║                                                           ║
║  2. 在 AWS IAM Identity Center 中配置 SAML 应用            ║
║     - Application ACS URL:                                ║
║       http://$EC2_IP:3000/api/v1/auth/saml/callback      ║
║     - Application SAML audience:                          ║
║       http://$EC2_IP:3000/api/v1/auth/saml/metadata      ║
║                                                           ║
║  3. 配置 SAML 属性映射：                                   ║
║     - Subject: \${user:email} (emailAddress)              ║
║     - email: \${user:email} (unspecified)                 ║
║     - groups: \${user:groups} (unspecified)               ║
║                                                           ║
║  4. 如果选择了"跳过"访问地址配置：                          ║
║     - 请手动编辑 backend/.env 文件                         ║
║     - 更新 SAML_SP_ENTITY_ID 和 SAML_SP_ACS_URL           ║
║     - 重启后端: sudo systemctl restart kirocli-backend    ║
║                                                           ║
║  5. 重启后端服务以加载 Secrets Manager 配置                ║
║     sudo systemctl restart kirocli-backend                ║
║                                                           ║
║  常用命令：                                                ║
║  - 查看后端日志: sudo journalctl -u kirocli-backend -f    ║
║  - 重启后端: sudo systemctl restart kirocli-backend       ║
║  - 查看 Nginx 日志: sudo tail -f /var/log/nginx/error.log ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo_info "安装日志已保存到: /tmp/kirocli-install.log"
