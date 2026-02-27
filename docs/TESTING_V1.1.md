# KiroCLI Platform v1.1 功能验证文档

> 本文档用于系统化验证 v1.1 的所有功能点，确保部署后系统正常运行。

---

## 验证环境准备

### 前置条件

- [ ] EC2 实例已部署 v1.1 代码
- [ ] 后端服务正常运行（`sudo systemctl status kirocli-backend`）
- [ ] Nginx 服务正常运行（`sudo systemctl status nginx`）
- [ ] 前端已构建并部署（`/home/ubuntu/kirocli-platform/frontend/dist` 存在）
- [ ] 数据库已初始化或升级（`init_db.py` 或 `upgrade_db.py`）
- [ ] AWS Secrets Manager 已配置并正常工作
- [ ] EC2 IAM Role 已附加并具有必要权限

### 测试账号

- 管理员账号：通过 AWS IAM Identity Center 分配到 `KiroCLI-Admins` 组
- 普通用户账号：通过 AWS IAM Identity Center 分配到 `KiroCLI-Users` 组

---

## 0. AWS 服务集成验证（v1.1 新增）

### 0.1 Secrets Manager 验证

#### 0.1.1 验证密钥加载

**测试步骤**：
1. SSH 登录到 EC2
2. 执行验证脚本

**验证命令**（在 EC2 上执行）：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate

python -c "
from app.config import settings
from app.services.secrets_manager import secrets_loader

print('=== Secrets Manager Configuration ===')
print(f'Enabled: {settings.SECRETS_MANAGER_ENABLED}')
print(f'Secret Name: {settings.SECRETS_MANAGER_SECRET_NAME}')
print(f'Fallback to ENV: {settings.SECRETS_MANAGER_FALLBACK_TO_ENV}')
print()

print('=== Loading Secrets ===')
try:
    secrets = secrets_loader.load(
        settings.SECRETS_MANAGER_SECRET_NAME,
        fallback_to_env=settings.SECRETS_MANAGER_FALLBACK_TO_ENV
    )
    print(f'Loaded {len(secrets)} secrets')
    print(f'Keys: {list(secrets.keys())}')
    print()
    
    print('=== Configuration Sources ===')
    sources = secrets_loader.get_load_sources()
    for key, source in sources.items():
        print(f'  {key}: {source}')
except Exception as e:
    print(f'ERROR: {e}')
"
```

**预期结果**：
- [ ] Secrets Manager Enabled: True
- [ ] 成功加载 2 个密钥（SECRET_KEY, SAML_IDP_X509_CERT）
- [ ] 配置来源显示 "secrets_manager"
- [ ] 无错误信息

#### 0.1.2 验证密钥轮换检测

**测试步骤**：
1. 检查 system_config 表中的 secret_key_hash
2. 验证轮换检测逻辑

**验证命令**：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate

sqlite3 data.db "SELECT key, value, updated_at FROM system_config WHERE key='secret_key_hash';"
```

**预期结果**：
- [ ] secret_key_hash 记录存在
- [ ] 值为 64 位十六进制字符串（SHA-256 哈希）
- [ ] updated_at 时间戳正确

#### 0.1.3 验证 .env 文件安全性

**测试步骤**：
1. 检查 .env 文件中是否还有敏感数据

**验证命令**：
```bash
cd /home/ubuntu/kirocli-platform/backend

# 检查是否还有敏感数据
grep -E "SECRET_KEY|SAML_IDP_X509_CERT|SAML_SP_PRIVATE_KEY" .env
```

**预期结果**：
- [ ] 无输出（表示没有敏感数据）
- [ ] 或只有 SECRETS_MANAGER 相关配置

---

### 0.2 SNS 告警通知验证（可选）

#### 0.2.1 查看 SNS 配置

**测试步骤**：
1. 使用管理员账号登录平台
2. 进入"设置" → "告警规则"页面
3. 查看 SNS Topic ARN 配置

**预期结果**：
- [ ] 显示 SNS Topic ARN 配置项
- [ ] 可以输入和保存 Topic ARN

**API 验证**：
```bash
# 查看告警配置（需要管理员 TOKEN）
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  http://<YOUR_EC2_IP>:3000/api/v1/admin/alert-rules
```

**预期响应**：
```json
{
  "rules": [...],
  "config": {
    "offhour_start": "22:00",
    "offhour_end": "08:00",
    "offhour_tz": "Asia/Shanghai",
    "cooldown_minutes": 30,
    "sns_topic_arn": ""
  }
}
```

#### 0.2.2 测试 SNS 通知（如果已配置）

**测试步骤**：
1. 在"告警规则"页面配置 SNS Topic ARN
2. 点击"测试 SNS 通知"按钮

**预期结果**：
- [ ] 显示"测试消息已发送"
- [ ] 订阅的邮箱收到测试邮件
- [ ] 邮件主题：`[KiroCLI] SNS 测试通知`

**API 验证**：
```bash
# 发送测试通知（需要管理员 TOKEN）
curl -X POST \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"sns_topic_arn":"arn:aws-cn:sns:cn-northwest-1:<ACCOUNT_ID>:kirocli-platform-alerts"}' \
  http://<YOUR_EC2_IP>:3000/api/v1/admin/alert-rules/test-sns
```

**预期响应**：
```json
{
  "success": true,
  "message": "测试消息已发送"
}
```

#### 0.2.3 验证 IAM 权限

**验证命令**（在 EC2 上执行）：
```bash
# 测试 SNS 发布权限
aws sns publish \
  --topic-arn arn:aws-cn:sns:cn-northwest-1:<ACCOUNT_ID>:kirocli-platform-alerts \
  --subject "Test from EC2" \
  --message "Testing SNS permissions" \
  --region cn-northwest-1
```

**预期结果**：
- [ ] 命令执行成功，返回 MessageId
- [ ] 订阅的邮箱收到测试邮件
- [ ] 无权限错误

---

## 1. 基础功能验证（v1.0 功能）

### 1.1 SAML 登录

**测试步骤**：
1. 访问 `http://<YOUR_EC2_IP>:3000`
2. 点击"SSO 登录"按钮
3. 跳转到 AWS IAM Identity Center 登录页
4. 输入用户名和密码
5. 登录成功后跳转回平台首页

**预期结果**：
- [ ] 成功跳转到 IAM Identity Center
- [ ] 登录后正确跳转回平台
- [ ] 显示用户名和角色信息
- [ ] Cookie 正确设置（检查浏览器开发者工具）

**验证命令**（后端日志）：
```bash
sudo journalctl -u kirocli-backend -n 50 --no-pager | grep -i saml
```

---

### 1.2 会话管理

#### 1.2.1 创建会话

**测试步骤**：
1. 登录后进入"会话管理"页面
2. 点击"创建新会话"按钮
3. 填写会话名称（如 "test-session-001"）
4. 点击"创建"

**预期结果**：
- [ ] 会话创建成功，显示在会话列表中
- [ ] 会话状态为"运行中"
- [ ] 显示会话 ID、创建时间、端口号
- [ ] 后端日志显示 Gotty 进程启动成功

**验证命令**：
```bash
# 检查 Gotty 进程
ps aux | grep gotty

# 检查端口监听
ss -tlnp | grep 786

# 检查 Nginx 路由配置
cat /etc/nginx/conf.d/gotty_routes.conf
```

#### 1.2.2 访问终端

**测试步骤**：
1. 在会话列表中点击"打开终端"按钮
2. 等待终端页面加载
3. 在终端中输入命令（如 `kiro-cli --version`）

**预期结果**：
- [ ] 终端页面正常打开
- [ ] 显示 Kiro CLI 界面
- [ ] 可以正常输入和执行命令
- [ ] 命令输出正确显示
- [ ] WebSocket 连接正常（检查浏览器开发者工具 Network 标签）

**验证 URL 格式**：
- v1.1 格式：`http://<YOUR_EC2_IP>:3000/terminal/{session_token}/{random_url}`
- 不应该是：`http://<YOUR_EC2_IP>:7860/...`（v1.0 格式）

#### 1.2.3 关闭会话

**测试步骤**：
1. 在会话列表中点击"关闭会话"按钮
2. 确认关闭操作

**预期结果**：
- [ ] 会话状态变为"已关闭"
- [ ] Gotty 进程被终止
- [ ] 端口被释放
- [ ] Nginx 路由配置更新（该会话的映射被移除）

**验证命令**：
```bash
# 确认 Gotty 进程已终止
ps aux | grep gotty

# 确认端口已释放
ss -tlnp | grep <PORT>

# 检查 Nginx 配置
cat /etc/nginx/conf.d/gotty_routes.conf
```

---

### 1.3 用户管理（管理员功能）

**测试步骤**：
1. 使用管理员账号登录
2. 进入"用户管理"页面
3. 查看用户列表

**预期结果**：
- [ ] 显示所有用户列表
- [ ] 显示用户角色、状态、邮箱
- [ ] 可以查看用户详情
- [ ] 可以修改用户权限

---

### 1.4 监控面板

**测试步骤**：
1. 进入"监控"页面
2. 查看系统指标

**预期结果**：
- [ ] 显示活跃会话数
- [ ] 显示在线用户数
- [ ] 显示系统资源使用情况
- [ ] 图表正常渲染

---

## 2. v1.1 新增功能验证

### 2.1 终端 URL 封装

#### 2.1.1 URL 格式验证

**测试步骤**：
1. 创建一个新会话
2. 点击"打开终端"
3. 检查浏览器地址栏的 URL

**预期结果**：
- [ ] URL 格式为：`http://<YOUR_EC2_IP>:3000/terminal/{session_token}/{random_url}`
- [ ] 不包含端口号（7860-7960）
- [ ] session_token 是会话的唯一标识

**API 验证**：
```bash
# 获取终端 URL（需要替换 TOKEN 和 SESSION_ID）
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://<YOUR_EC2_IP>:3000/api/v1/sessions/<SESSION_ID>/terminal-url
```

**预期响应**：
```json
{
  "terminal_url": "http://<YOUR_EC2_IP>:3000/terminal/{session_token}/{random_url}"
}
```

#### 2.1.2 直接访问 Gotty 端口验证（应该失败）

**测试步骤**：
1. 尝试直接访问 Gotty 端口：`http://<YOUR_EC2_IP>:7860/...`

**预期结果**：
- [ ] 连接超时或拒绝连接（安全组未开放端口）
- [ ] 无法绕过平台直接访问终端

**验证命令**（在本地机器执行）：
```bash
# 应该超时或拒绝连接
curl -m 5 http://<YOUR_EC2_IP>:7860/
```

#### 2.1.3 Nginx 反代验证

**测试步骤**：
1. 在 EC2 上检查 Nginx 配置
2. 验证 map 指令配置

**验证命令**（在 EC2 上执行）：
```bash
# 检查 kirocli_map.conf
cat /etc/nginx/conf.d/kirocli_map.conf

# 检查 gotty_routes.conf
cat /etc/nginx/conf.d/gotty_routes.conf

# 测试 Nginx 配置
sudo nginx -t
```

**预期结果**：
- [ ] `kirocli_map.conf` 包含 token 提取逻辑
- [ ] `gotty_routes.conf` 包含 token→port 映射
- [ ] Nginx 配置测试通过

---

### 2.2 设备指纹采集

#### 2.2.1 设备指纹生成

**测试步骤**：
1. 打开浏览器开发者工具（F12）
2. 切换到 Console 标签
3. 登录平台
4. 查看 localStorage

**预期结果**：
- [ ] localStorage 中存在 `device_fingerprint` 键
- [ ] 值为 32 位十六进制字符串
- [ ] 同一浏览器多次登录，指纹保持不变

**验证命令**（浏览器 Console）：
```javascript
localStorage.getItem('device_fingerprint')
```

#### 2.2.2 设备信息上报

**测试步骤**：
1. 登录成功后
2. 检查浏览器开发者工具 Network 标签
3. 查找 `/api/v1/users/me/device` 请求

**预期结果**：
- [ ] 登录后自动发送设备信息上报请求
- [ ] 请求方法为 POST
- [ ] 请求体包含 `device_fingerprint`、`user_agent`、`ip_address`
- [ ] 响应状态码为 200

**API 验证**：
```bash
# 查看用户设备列表（需要替换 TOKEN）
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://<YOUR_EC2_IP>:3000/api/v1/users/me/devices
```

**预期响应**：
```json
[
  {
    "id": 1,
    "device_fingerprint": "abc123...",
    "user_agent": "Mozilla/5.0...",
    "ip_address": "1.2.3.4",
    "last_seen_at": "2026-02-27T10:00:00Z",
    "is_trusted": true
  }
]
```

#### 2.2.3 数据库验证

**验证命令**（在 EC2 上执行）：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
sqlite3 data.db "SELECT * FROM user_devices LIMIT 5;"
```

**预期结果**：
- [ ] `user_devices` 表存在
- [ ] 包含用户的设备记录
- [ ] 字段包括：id, user_id, device_fingerprint, user_agent, ip_address, last_seen_at

---

### 2.3 IP 白名单功能

#### 2.3.1 查看 IP 白名单状态

**测试步骤**：
1. 使用管理员账号登录
2. 进入"设置"页面
3. 查看"IP 白名单"部分

**预期结果**：
- [ ] 显示 IP 白名单启用状态（默认为禁用）
- [ ] 显示当前 IP 地址
- [ ] 显示白名单条目列表（如果已配置）

**API 验证**：
```bash
# 查看 IP 白名单配置（需要管理员 TOKEN）
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  http://<YOUR_EC2_IP>:3000/api/v1/admin/ip-whitelist
```

#### 2.3.2 获取当前 IP

**测试步骤**：
1. 在"IP 白名单"部分点击"获取我的 IP"按钮

**预期结果**：
- [ ] 显示当前请求的 IP 地址
- [ ] IP 地址格式正确

**API 验证**：
```bash
curl -H "Authorization: Bearer <ADMIN_TOKEN>" \
  http://<YOUR_EC2_IP>:3000/api/v1/admin/ip-whitelist/my-ip
```

#### 2.3.3 配置 IP 白名单

**测试步骤**：
1. 启用 IP 白名单
2. 添加当前 IP 到白名单
3. 保存配置

**预期结果**：
- [ ] 配置保存成功
- [ ] Nginx 配置文件更新（`/etc/nginx/conf.d/ip_whitelist.conf`）
- [ ] Nginx 自动重载

**验证命令**（在 EC2 上执行）：
```bash
# 检查 IP 白名单配置
cat /etc/nginx/conf.d/ip_whitelist.conf

# 检查系统配置
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
sqlite3 data.db "SELECT * FROM system_config WHERE key='ip_whitelist_enabled';"
```

#### 2.3.4 IP 白名单访问控制验证

**测试步骤**：
1. 启用 IP 白名单，只添加一个测试 IP（不是你的 IP）
2. 尝试访问平台

**预期结果**：
- [ ] 访问被拒绝，返回 403 Forbidden
- [ ] 无法访问前端页面
- [ ] 无法访问 API 接口

**恢复步骤**：
```bash
# 在 EC2 上手动禁用 IP 白名单
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
sqlite3 data.db "UPDATE system_config SET value='false' WHERE key='ip_whitelist_enabled';"

# 重新生成 Nginx 配置
python -c "
from app.services.ip_whitelist_service import IPWhitelistService
from app.core.database import SessionLocal
db = SessionLocal()
service = IPWhitelistService(db)
service.update_nginx_config()
db.close()
"
```

---

### 2.4 审计日志

#### 2.4.1 审计日志记录

**测试步骤**：
1. 执行一些操作（登录、创建会话、修改设置等）
2. 检查审计日志

**验证命令**（在 EC2 上执行）：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
sqlite3 data.db "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 10;"
```

**预期结果**：
- [ ] `audit_logs` 表存在
- [ ] 记录了用户操作
- [ ] 包含字段：user_id, action, resource_type, resource_id, ip_address, user_agent, created_at

#### 2.4.2 审计日志查询（如果前端已实现）

**测试步骤**：
1. 使用管理员账号登录
2. 进入"审计日志"页面（如果存在）
3. 查看日志列表

**预期结果**：
- [ ] 显示审计日志列表
- [ ] 可以按时间、用户、操作类型筛选
- [ ] 显示详细的操作信息

---

### 2.5 告警规则

#### 2.5.1 查看默认告警规则

**验证命令**（在 EC2 上执行）：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
sqlite3 data.db "SELECT * FROM alert_rules;"
```

**预期结果**：
- [ ] `alert_rules` 表存在
- [ ] 包含 4 条默认规则：
  - session_burst（会话创建频率异常）
  - login_failure（登录失败次数异常）
  - multi_ip_login（多IP登录异常）
  - offhour_login（非工作时间登录）

#### 2.5.2 告警触发测试（可选）

**测试步骤**：
1. 快速创建多个会话（触发 session_burst）
2. 检查告警事件

**验证命令**：
```bash
sqlite3 data.db "SELECT * FROM alert_events ORDER BY created_at DESC LIMIT 5;"
```

**预期结果**：
- [ ] `alert_events` 表存在
- [ ] 记录了告警事件
- [ ] 包含字段：rule_id, user_id, severity, message, metadata, created_at

---

### 2.6 Token 管理

#### 2.6.1 Refresh Token

**测试步骤**：
1. 登录后检查浏览器 Cookie
2. 等待 Access Token 过期（或手动删除）
3. 刷新页面

**预期结果**：
- [ ] Cookie 中存在 `refresh_token`
- [ ] Access Token 过期后自动刷新
- [ ] 无需重新登录

**验证命令**（在 EC2 上执行）：
```bash
sqlite3 data.db "SELECT * FROM refresh_tokens WHERE revoked=0 LIMIT 5;"
```

#### 2.6.2 Token 黑名单

**测试步骤**：
1. 登录后
2. 点击"退出登录"
3. 尝试使用旧 Token 访问 API

**预期结果**：
- [ ] 退出登录后 Token 被加入黑名单
- [ ] 使用旧 Token 访问 API 返回 401 Unauthorized

**验证命令**：
```bash
sqlite3 data.db "SELECT * FROM blacklisted_tokens LIMIT 5;"
```

---

### 2.7 系统配置

#### 2.7.1 查看系统配置

**验证命令**（在 EC2 上执行）：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate
sqlite3 data.db "SELECT * FROM system_config;"
```

**预期结果**：
- [ ] `system_config` 表存在
- [ ] 包含默认配置项：
  - ip_whitelist_enabled
  - alert_offhour_start
  - alert_offhour_end
  - alert_offhour_tz
  - alert_cooldown_minutes
  - sns_topic_arn
  - secret_key_hash

---

## 3. 安全性验证

### 3.1 Gotty 端口隔离

**测试步骤**：
1. 在本地机器尝试直接访问 Gotty 端口

**验证命令**（在本地机器执行）：
```bash
# 应该超时或拒绝连接
curl -m 5 http://<YOUR_EC2_IP>:7860/
curl -m 5 http://<YOUR_EC2_IP>:7861/
curl -m 5 http://<YOUR_EC2_IP>:7960/
```

**预期结果**：
- [ ] 所有请求超时或被拒绝
- [ ] 无法绕过平台直接访问 Gotty

### 3.2 Gotty 绑定地址验证

**验证命令**（在 EC2 上执行）：
```bash
# 检查 Gotty 进程监听地址
ss -tlnp | grep gotty
```

**预期结果**：
- [ ] Gotty 只监听 `127.0.0.1`，不监听 `0.0.0.0`
- [ ] 输出类似：`127.0.0.1:7860`

### 3.3 终端访问权限验证

**测试步骤**：
1. 创建一个会话（用户 A）
2. 复制终端 URL
3. 使用另一个用户（用户 B）尝试访问该 URL

**预期结果**：
- [ ] 用户 B 无法访问用户 A 的终端
- [ ] 返回 401 或 403 错误
- [ ] 被重定向到登录页

---

## 4. 性能验证

### 4.1 并发会话测试

**测试步骤**：
1. 创建多个会话（5-10 个）
2. 同时打开多个终端
3. 在每个终端中执行命令

**预期结果**：
- [ ] 所有会话正常创建
- [ ] 所有终端可以同时使用
- [ ] 命令执行无明显延迟
- [ ] 系统资源使用正常

**验证命令**（在 EC2 上执行）：
```bash
# 检查 Gotty 进程数
ps aux | grep gotty | wc -l

# 检查系统资源
top -bn1 | head -20
```

### 4.2 Nginx 配置重载性能

**测试步骤**：
1. 快速创建和关闭多个会话
2. 观察 Nginx 重载频率

**验证命令**：
```bash
# 检查 Nginx 错误日志
sudo tail -50 /var/log/nginx/error.log

# 检查 Nginx 访问日志
sudo tail -50 /var/log/nginx/access.log
```

**预期结果**：
- [ ] Nginx 重载成功，无错误
- [ ] 重载不影响现有连接
- [ ] 配置文件格式正确

---

## 5. 数据库验证

### 5.1 表结构验证

**验证命令**（在 EC2 上执行）：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate

# 列出所有表
sqlite3 data.db ".tables"

# 查看表结构
sqlite3 data.db ".schema user_devices"
sqlite3 data.db ".schema audit_logs"
sqlite3 data.db ".schema alert_rules"
sqlite3 data.db ".schema alert_events"
sqlite3 data.db ".schema refresh_tokens"
sqlite3 data.db ".schema blacklisted_tokens"
sqlite3 data.db ".schema ip_whitelist"
sqlite3 data.db ".schema system_config"
```

**预期结果**：
- [ ] 所有 v1.1 新增表都存在
- [ ] 表结构符合设计文档
- [ ] 外键关系正确

### 5.2 数据完整性验证

**验证命令**：
```bash
# 检查用户数据
sqlite3 data.db "SELECT COUNT(*) FROM users;"

# 检查会话数据
sqlite3 data.db "SELECT COUNT(*) FROM sessions;"

# 检查设备数据
sqlite3 data.db "SELECT COUNT(*) FROM user_devices;"

# 检查审计日志
sqlite3 data.db "SELECT COUNT(*) FROM audit_logs;"
```

**预期结果**：
- [ ] 数据记录数合理
- [ ] 无孤立记录（外键约束正常）

---

## 6. 日志验证

### 6.1 后端日志

**验证命令**（在 EC2 上执行）：
```bash
# 查看后端服务日志
sudo journalctl -u kirocli-backend -n 100 --no-pager

# 查看应用日志
tail -100 /home/ubuntu/kirocli-platform/logs/backend.log
```

**预期结果**：
- [ ] 日志正常输出
- [ ] 无严重错误（ERROR 级别）
- [ ] 关键操作有日志记录

### 6.2 Nginx 日志

**验证命令**：
```bash
# 查看 Nginx 访问日志
sudo tail -100 /var/log/nginx/access.log

# 查看 Nginx 错误日志
sudo tail -100 /var/log/nginx/error.log
```

**预期结果**：
- [ ] 访问日志记录正常
- [ ] 无配置错误
- [ ] 无 502/504 错误

---

## 7. 升级验证（从 v1.0 升级）

### 7.1 数据迁移验证

**验证步骤**：
1. 检查 v1.0 数据是否保留
2. 检查 v1.1 新表是否创建

**验证命令**：
```bash
cd /home/ubuntu/kirocli-platform/backend
source .venv/bin/activate

# 检查 v1.0 表
sqlite3 data.db "SELECT COUNT(*) FROM users;"
sqlite3 data.db "SELECT COUNT(*) FROM sessions;"

# 检查 v1.1 新表
sqlite3 data.db ".tables" | grep -E "user_devices|audit_logs|alert_rules"
```

**预期结果**：
- [ ] v1.0 数据完整保留
- [ ] v1.1 新表已创建
- [ ] 默认数据已写入

### 7.2 配置文件验证

**验证命令**：
```bash
# 检查 Nginx 配置
ls -la /etc/nginx/conf.d/ | grep -E "kirocli_map|gotty_routes|ip_whitelist"

# 检查配置内容
cat /etc/nginx/conf.d/kirocli_map.conf
cat /etc/nginx/conf.d/gotty_routes.conf
cat /etc/nginx/conf.d/ip_whitelist.conf
```

**预期结果**：
- [ ] 所有配置文件存在
- [ ] 配置格式正确
- [ ] 权限设置正确（ubuntu:ubuntu）

---

## 验证清单总结

### 必须通过的验证项

**AWS 服务集成**：
- [ ] Secrets Manager 正常加载密钥
- [ ] SECRET_KEY 和 SAML_IDP_X509_CERT 从 Secrets Manager 加载
- [ ] .env 文件中不包含敏感数据
- [ ] secret_key_hash 正确记录在数据库中

**基础功能**：
- [ ] SAML 登录正常
- [ ] 会话创建和访问正常
- [ ] 终端 URL 格式正确（v1.1 格式）
- [ ] 无法直接访问 Gotty 端口（安全性）

**v1.1 新功能**：
- [ ] 设备指纹正常采集和上报
- [ ] 所有 v1.1 新表已创建
- [ ] Nginx 配置文件完整且正确
- [ ] 后端和 Nginx 服务正常运行

### 可选验证项

- [ ] SNS 告警通知配置和测试（如果需要使用）
- [ ] IP 白名单功能（如果需要使用）
- [ ] 告警规则触发（需要特定场景）
- [ ] 并发性能测试（根据实际需求）

---

## 故障排查参考

如果验证过程中遇到问题，请参考：
- `EC2_DEPLOYMENT_V1.1.md` - 部署文档
- 后端日志：`sudo journalctl -u kirocli-backend -n 100`
- Nginx 日志：`sudo tail -100 /var/log/nginx/error.log`
- 数据库检查：`sqlite3 data.db ".tables"`

---

## 验证完成标准

当以上所有"必须通过的验证项"都打勾后，v1.1 部署验证完成，系统可以投入使用。
