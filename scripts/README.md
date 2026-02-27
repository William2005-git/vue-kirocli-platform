# 部署脚本使用说明

## 快速部署

### 1. 设置环境变量

```bash
export EC2_IP=69.234.199.116
export KEY=~/.ssh/your-key.pem
```

### 2. 执行部署脚本

```bash
cd vue-kirocli-platform
./scripts/deploy.sh
```

## 部署脚本功能

`deploy.sh` 会自动执行以下操作：

1. **同步后端代码** - 排除 `.venv`、`__pycache__`、`*.pyc`、`data.db`
2. **同步前端代码** - 排除 `node_modules`、`dist`
3. **同步 Nginx 配置** - 包括 `kirocli_map.conf` 和 `kirocli` 站点配置
4. **更新 Nginx 配置** - 复制配置文件到系统目录
5. **测试 Nginx 配置** - 执行 `nginx -t`
6. **重新加载 Nginx** - 应用新配置
7. **重启后端服务** - 重启 `kirocli-backend` systemd 服务
8. **构建前端** - 执行 `npm run build`

## 手动部署步骤

如果需要手动部署，可以参考以下步骤：

### 同步代码

```bash
# 后端
rsync -avz --exclude '.venv' --exclude '__pycache__' --exclude '*.pyc' --exclude 'data.db' \
  -e "ssh -i $KEY" \
  backend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/backend/

# 前端
rsync -avz --exclude 'node_modules' --exclude 'dist' \
  -e "ssh -i $KEY" \
  frontend/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/frontend/

# Nginx 配置
rsync -avz -e "ssh -i $KEY" \
  nginx/ \
  ubuntu@$EC2_IP:/home/ubuntu/kirocli-platform/nginx/
```

### 在 EC2 上执行

```bash
ssh -i $KEY ubuntu@$EC2_IP

# 更新 Nginx 配置
sudo cp ~/kirocli-platform/nginx/kirocli_map.conf /etc/nginx/conf.d/
sudo cp ~/kirocli-platform/nginx/kirocli /etc/nginx/sites-available/

# 确保 gotty_routes.conf 权限正确
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf

# 测试并重载 Nginx
sudo nginx -t
sudo nginx -s reload

# 重启后端
sudo systemctl restart kirocli-backend

# 构建前端
cd ~/kirocli-platform/frontend
npm run build
```

## 故障排查

### Nginx 配置测试失败

```bash
# 查看详细错误
sudo nginx -t

# 检查配置文件语法
sudo nginx -T | less
```

### 后端服务启动失败

```bash
# 查看服务状态
sudo systemctl status kirocli-backend

# 查看日志
sudo journalctl -u kirocli-backend -n 50 --no-pager
```

### 前端构建失败

```bash
# 检查 Node.js 版本
node --version

# 重新安装依赖
cd ~/kirocli-platform/frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

## 配置文件说明

### nginx/kirocli_map.conf

从请求 URI 中提取 session token 的 map 配置。

### nginx/kirocli

主站点配置文件，包含：
- 前端静态文件服务
- API 反向代理
- WebSocket 支持
- 终端代理（通过 token→port 映射）

### /etc/nginx/conf.d/gotty_routes.conf

由后端动态生成的 token→port 映射配置，不需要手动维护。
