#!/bin/bash
set -e

# 部署脚本 - 自动同步代码、更新 Nginx 配置、重启服务

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 检查必需的环境变量
if [ -z "$EC2_IP" ]; then
    echo_error "请设置 EC2_IP 环境变量"
    echo "例如: export EC2_IP=69.234.199.116"
    exit 1
fi

if [ -z "$KEY" ]; then
    echo_error "请设置 KEY 环境变量（SSH 密钥路径）"
    echo "例如: export KEY=~/.ssh/your-key.pem"
    exit 1
fi

# 检查 SSH 密钥文件是否存在
if [ ! -f "$KEY" ]; then
    echo_error "SSH 密钥文件不存在: $KEY"
    exit 1
fi

echo_info "开始部署到 $EC2_IP"

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo_info "项目根目录: $PROJECT_ROOT"

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 1. 同步后端代码
echo_info "同步后端代码..."
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i $KEY" \
  backend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/backend/

# 2. 同步前端代码
echo_info "同步前端代码..."
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i $KEY" \
  frontend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/frontend/

# 3. 同步 Nginx 配置
echo_info "同步 Nginx 配置..."
rsync -avz -e "ssh -i $KEY" \
  nginx/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/nginx/

# 4. 在远程服务器上执行部署命令
echo_info "在远程服务器上执行部署..."
ssh -i "$KEY" ubuntu@$EC2_IP << 'ENDSSH'
set -e

echo "[远程] 更新 Nginx 配置..."
# 复制 Nginx 配置文件到系统目录
sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli_map.conf /etc/nginx/conf.d/
sudo cp /home/ubuntu/kirocli-platform/nginx/kirocli /etc/nginx/sites-available/

# 确保 gotty_routes.conf 存在且权限正确
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
sudo chmod 644 /etc/nginx/conf.d/gotty_routes.conf

# 初始化 gotty_routes.conf（如果为空）
if [ ! -s /etc/nginx/conf.d/gotty_routes.conf ]; then
    cat << 'EOF' | sudo tee /etc/nginx/conf.d/gotty_routes.conf > /dev/null
# Token 到 Gotty 端口的映射（由后端动态更新）
map $session_token_var $gotty_backend_port {
    default 0;
}
EOF
    sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
fi

# 检查并自动添加 gotty_routes.conf include（必须在 kirocli_map.conf 之后）
if ! grep -q "gotty_routes.conf" /etc/nginx/nginx.conf; then
    echo "[远程] 自动添加 gotty_routes.conf include 到 nginx.conf..."
    # 在 kirocli_map.conf 之后添加 gotty_routes.conf
    sudo sed -i '/kirocli_map.conf/a\    include /etc/nginx/conf.d/gotty_routes.conf;' /etc/nginx/nginx.conf
    echo "[远程] 已添加 gotty_routes.conf include"
fi

# 测试 Nginx 配置
echo "[远程] 测试 Nginx 配置..."
sudo nginx -t

# 重新加载 Nginx
echo "[远程] 重新加载 Nginx..."
sudo nginx -s reload

# 重启后端服务
echo "[远程] 重启后端服务..."
sudo systemctl restart kirocli-backend

# 等待后端启动
sleep 3

# 检查后端服务状态
echo "[远程] 检查后端服务状态..."
sudo systemctl status kirocli-backend --no-pager -l | head -20

# 构建前端
echo "[远程] 构建前端..."
cd /home/ubuntu/kirocli-platform/frontend
npm run build

echo "[远程] 部署完成！"
ENDSSH

echo_info "部署成功完成！"
echo_info "访问地址: http://$EC2_IP:3000"
