# KiroCLI Platform

> A secure, browser-based platform for managing Kiro CLI terminal sessions — powered by AWS IAM Identity Center SSO, with zero credential exposure.

**Current Version: 1.1.0** | [Changelog](CHANGELOG.md) | [v1.1 Deployment Guide](docs/EC2_DEPLOYMENT_V1.1.md)

![SSO Login](image/SSO_signin.png)

---

## What's New in v1.1

v1.1 introduces enterprise-grade security features and operational improvements:

- 🔒 **IP Whitelist** - Restrict access by IP/CIDR ranges with dynamic Nginx configuration
- 📊 **Audit Logging** - Track all security events with CSV export for compliance
- 🚨 **Alert System** - Real-time anomaly detection with AWS SNS notifications
- 🔄 **Refresh Tokens** - Long-lived sessions with automatic rotation and revocation
- 📱 **Device Fingerprinting** - Track and manage trusted devices per user
- 🔌 **Force Logout** - Remotely terminate user sessions across all devices
- 🔐 **Nginx-Proxied Terminals** - Enhanced security with JWT-based auth_request
- 🔑 **AWS Secrets Manager** - Centralized secret management with rotation detection
- ⏱️ **Real-time Duration** - Live session timers with proper timezone handling
- 📈 **Startup Progress** - Visual feedback during terminal launch

See the [full changelog](CHANGELOG.md) for details.

---

## Why KiroCLI Platform?

Managing Kiro CLI across a team is painful. Developers need to handle AWS credentials, manage local installations, and deal with session sprawl. KiroCLI Platform solves this by centralizing access through a secure web interface.

| Challenge | Traditional Approach | KiroCLI Platform |
|-----------|---------------------|------------------|
| Authentication | Distribute AK/SK to every developer | SSO login via AWS IAM Identity Center — no credentials to manage |
| Access control | Manual IAM policy per user | Role-based groups with per-user session quotas |
| Session security | Direct CLI access, no audit trail | Random-token URLs + TLS encryption + session logging |
| Concurrent users | One CLI per machine | Up to 100 concurrent browser-based sessions per instance |
| Credential rotation | Update AK/SK on every machine | Centralized — rotate once in IAM Identity Center |

---

## Key Security Features

- **No AK/SK distribution** — Users authenticate via AWS IAM Identity Center (SAML 2.0). No AWS access keys are ever shared with end users.
- **Random-token terminal URLs** — Each Gotty session gets a 16-character cryptographically random URL token (e.g. `/abcd1234efgh5678/`). Guessing a session URL is computationally infeasible.
- **TLS encryption** — All terminal traffic between the browser and Gotty is encrypted over HTTPS/WSS. No plaintext terminal data on the wire.
- **Session isolation** — Each user gets their own Gotty process. Sessions are fully isolated and automatically cleaned up on idle timeout.
- **JWT-based API auth** — Backend APIs are protected with short-lived JWT tokens (8-hour expiry by default).

---

## Features

### Core Features (v1.0)
- **SSO Authentication** via AWS IAM Identity Center (SAML 2.0)
- **Browser-based Terminal** powered by Gotty + Kiro CLI
- **Session Management** — start, monitor, and close terminal sessions
- **User & Group Management** with role-based access control
- **Concurrent Sessions** — supports up to 100 simultaneous terminal sessions
- **Auto Cleanup** — idle sessions are automatically terminated
- **System Monitoring** dashboard with real-time metrics

### Security Features (v1.1)
- **IP Whitelist** — Restrict access by IP/CIDR ranges (admin-configurable)
- **Audit Logging** — Comprehensive event tracking with CSV export
- **Alert System** — Anomaly detection (session burst, login failures, multi-IP, off-hours)
- **Refresh Tokens** — Long-lived sessions with automatic rotation
- **Device Fingerprinting** — Track and manage trusted devices
- **Force Logout** — Remote session termination by administrators
- **Nginx-Proxied Terminals** — JWT-based authentication for terminal access
- **AWS Secrets Manager** — Centralized secret management

---

## Screenshots

### Session Management

![Session Management](image/session_management.png)

### Browser Terminal

![Web Terminal Session](image/web-session.png)

---

## Architecture

```
Browser → Nginx (port 3000) → FastAPI Backend (127.0.0.1:8000)
                                      ↓
                    ┌─────────────────┴──────────────────┐
                    │                                     │
                    ▼                                     ▼
            Gotty Sessions                        SQLite Database
       (127.0.0.1:7861–7960, TLS)              (14 tables, v1.1)
       [Nginx auth_request proxy]
                    ↓
                kiro-cli
```

**v1.1 Changes:**
- Gotty now binds to `127.0.0.1` (not `0.0.0.0`) for security
- Terminal access via Nginx reverse proxy with JWT authentication
- No direct public access to Gotty ports (7860-7960 no longer needed in Security Group)
- Dynamic route configuration using Nginx `map` directive

All components run on a single EC2 instance. No external dependencies beyond AWS IAM Identity Center (and optionally AWS SNS + Secrets Manager for v1.1 features).

---

## Prerequisites

- AWS EC2 instance running **Ubuntu 22.04** (recommended: t3.medium or larger)
- AWS IAM Identity Center configured with a SAML application
- Kiro CLI installed on the EC2 instance
- EC2 Security Group inbound rules:

| Port | Protocol | Source | Purpose | Version |
|------|----------|--------|---------|---------|
| 22 | TCP | Your IP | SSH | v1.0+ |
| 3000 | TCP | 0.0.0.0/0 | Web UI (Nginx) | v1.0+ |

**v1.1 Security Improvement:** Ports 7860-7960 are no longer required. Gotty now binds to `127.0.0.1` and is accessed via Nginx proxy on port 3000. You can remove these ports from your Security Group for improved security.

**Optional (v1.1):**
- AWS SNS Topic for alert notifications
- AWS Secrets Manager for centralized secret management

---

## EC2 IAM Role

The EC2 instance needs an IAM Role with the following policy to support v1.1 features:

### Required Permissions

**For IAM Identity Center Sync** (syncing users and groups into the local database):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "IdentityStoreReadOnly",
      "Effect": "Allow",
      "Action": [
        "identitystore:ListUsers",
        "identitystore:ListGroups",
        "identitystore:ListGroupMembershipsForMember",
        "identitystore:DescribeGroup"
      ],
      "Resource": "*"
    }
  ]
}
```

**For AWS Secrets Manager** (optional, v1.1):

```json
{
  "Sid": "SecretsManagerRead",
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue",
    "secretsmanager:DescribeSecret"
  ],
  "Resource": "arn:aws:secretsmanager:*:*:secret:kirocli-platform-*"
}
```

**For SNS Alerts** (optional, v1.1):

```json
{
  "Sid": "SNSPublish",
  "Effect": "Allow",
  "Action": [
    "sns:Publish"
  ],
  "Resource": "arn:aws:sns:*:*:kirocli-alerts"
}
```

> **Note**: If you do not need IAM sync, Secrets Manager, or SNS features, these permissions are optional. Users can still log in via SSO and be created automatically on first login.

**Steps to attach the role:**
1. AWS Console → IAM → Roles → Create role
2. Trusted entity: AWS service → EC2
3. Attach the inline policies above, name it `KiroCLIPlatformPolicy`
4. EC2 Console → select your instance → Actions → Security → Modify IAM role → attach the role

---

## Quick Start

For detailed deployment instructions, see:
- **v1.1 (Latest)**: [docs/EC2_DEPLOYMENT_V1.1.md](docs/EC2_DEPLOYMENT_V1.1.md)
- **v1.0**: Follow the steps below

The steps below provide a quick overview. For production deployments, refer to the full documentation.

---

## Step 1 — Connect to EC2

```bash
ssh -i /path/to/your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

---

## Step 2 — Install System Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget nginx python3 python3-pip python3-venv sqlite3

# Install Node.js 20 LTS via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
nvm alias default 20
node -v  # should show v20.x.x
```

---

## Step 3 — Install Gotty

```bash
wget https://github.com/sorenisanerd/gotty/releases/download/v1.5.0/gotty_v1.5.0_linux_amd64.tar.gz
tar -xzf gotty_v1.5.0_linux_amd64.tar.gz
sudo mv gotty /usr/local/bin/gotty
sudo chmod +x /usr/local/bin/gotty
gotty --version
```

---

## Step 4 — Install Kiro CLI

Follow the official Kiro CLI installation guide, then verify:

```bash
which kiro-cli        # note the full path, e.g. /usr/bin/kiro-cli
kiro-cli --version
```

> **Important**: You must use the absolute path in the `.env` configuration. An incorrect path causes the terminal to show a black screen with "connection close".

---

## Step 5 — Create TLS Certificate for Gotty

**v1.1 Important:** Gotty uses HTTPS/TLS, and Nginx proxies to Gotty via `https://127.0.0.1:port`.

```bash
# Create certificate directory
mkdir -p /home/ubuntu/kirocli-platform/certs

# Generate self-signed certificate (CN=127.0.0.1, since Gotty binds to 127.0.0.1)
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /home/ubuntu/kirocli-platform/certs/gotty-key.pem \
  -out /home/ubuntu/kirocli-platform/certs/gotty-cert.pem \
  -days 365 \
  -subj "/CN=127.0.0.1"

# Verify certificate
openssl x509 -in /home/ubuntu/kirocli-platform/certs/gotty-cert.pem -text -noout | grep "Subject:"
# Should show: Subject: CN = 127.0.0.1
```

> **Note:**
> - Gotty binds to `127.0.0.1` (localhost only), so the certificate CN must be `127.0.0.1`
> - Nginx uses `proxy_ssl_verify off` to trust the self-signed certificate
> - Certificate is valid for 365 days; regenerate when expired

---

## Step 6 — Clone the Repository

```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/vue-kirocli-platform.git
cd vue-kirocli-platform
```

---

## Step 7 — Configure Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create the `.env` file:

```bash
cp .env.example .env
nano .env
```

**v1.1 Important:** Sensitive values (SECRET_KEY, SAML_IDP_X509_CERT) should be stored in AWS Secrets Manager, not in `.env`. See [v1.1 Deployment Guide](docs/EC2_DEPLOYMENT_V1.1.md#步骤-7配置-aws-secrets-manager) for details.

Fill in all required values (no inline comments):

```env
APP_NAME=KiroCLI Platform
ENVIRONMENT=production
DEBUG=false

DATABASE_URL=sqlite:////home/ubuntu/vue-kirocli-platform/backend/data.db

SAML_IDP_ENTITY_ID=<IdP Entity ID from IAM Identity Center>
SAML_IDP_SSO_URL=<SSO URL from IAM Identity Center>
SAML_SP_ENTITY_ID=http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/callback

IAM_IDENTITY_STORE_ID=<your Identity Store ID>
AWS_REGION=cn-northwest-1

GOTTY_PRIMARY_PORT=7860
GOTTY_PORT_START=7861
GOTTY_PORT_END=7960
GOTTY_PATH=/usr/local/bin/gotty
KIRO_CLI_PATH=<absolute path from: which kiro-cli>
GOTTY_CERT_PATH=/home/ubuntu/kirocli-platform/certs/gotty-cert.pem
GOTTY_KEY_PATH=/home/ubuntu/kirocli-platform/certs/gotty-key.pem
GOTTY_REMOTE_MODE=false
GOTTY_REMOTE_HOST=<EC2_PUBLIC_IP>

CORS_ORIGINS=["http://<EC2_PUBLIC_IP>:3000"]

LOG_LEVEL=INFO
LOG_FILE=/home/ubuntu/vue-kirocli-platform/logs/backend.log

JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_MINUTES=5

SECRETS_MANAGER_ENABLED=true
SECRETS_MANAGER_SECRET_NAME=kirocli-platform/production
SECRETS_MANAGER_FALLBACK_TO_ENV=false
```

> **v1.1 Security Notes:**
> - Do NOT include `SECRET_KEY` in `.env` (load from Secrets Manager)
> - Do NOT include `SAML_IDP_X509_CERT` in `.env` (load from Secrets Manager)
> - Set `SECRETS_MANAGER_ENABLED=true` for production
> - Set `SECRETS_MANAGER_FALLBACK_TO_ENV=false` for production
> - Gotty TLS certificates are still required (`GOTTY_CERT_PATH`, `GOTTY_KEY_PATH`)
> - Gotty binds to `127.0.0.1` and is accessed via Nginx HTTPS proxy

Initialize the database:

```bash
mkdir -p /home/ubuntu/vue-kirocli-platform/logs
python scripts/init_db.py
```

---

## Step 8 — Configure Backend systemd Service

```bash
sudo tee /etc/systemd/system/kirocli-backend.service << 'EOF'
[Unit]
Description=KiroCLI Platform Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/vue-kirocli-platform/backend
Environment=HOME=/home/ubuntu
Environment=USER=ubuntu
Environment=PATH=/home/ubuntu/vue-kirocli-platform/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/ubuntu/vue-kirocli-platform/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
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

## Step 9 — Build Frontend

```bash
cd /home/ubuntu/vue-kirocli-platform/frontend

# If EC2 has less than 2GB RAM, add swap first
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

npm install
npm run build
# Success: ✓ built in xx.xxs
```

---

## Step 10 — Configure Nginx

**v1.1 Important Changes:** Nginx configuration now includes dynamic route management for Gotty sessions.

```bash
# Create required dynamic configuration files (v1.1)
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo touch /etc/nginx/conf.d/ip_whitelist.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/ip_whitelist.conf

# Write initial content to prevent Nginx errors
cat | sudo tee /etc/nginx/conf.d/gotty_routes.conf > /dev/null << 'EOF'
# Auto-generated by KiroCLI Platform - do not edit manually
map $session_token_var $gotty_backend_port {
    default 0;
}
EOF

cat | sudo tee /etc/nginx/conf.d/ip_whitelist.conf > /dev/null << 'EOF'
# Auto-generated by KiroCLI Platform - do not edit manually
map $remote_addr $ip_allowed {
    default 1;
}
EOF

# Create map configuration for token extraction (v1.1)
sudo tee /etc/nginx/conf.d/kirocli_map.conf << 'EOF'
# Extract session token from URI
map $request_uri $session_token_var {
    ~^/terminal/(?<token>[^/]+) $token;
    default "";
}
EOF

# Create main site configuration
sudo tee /etc/nginx/sites-available/kirocli << 'EOF'
server {
    listen 3000;
    server_name _;

    root /home/ubuntu/vue-kirocli-platform/frontend/dist;
    index index.html;

    # Static files
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Gotty terminal proxy (v1.1 - dynamic routing)
    location ~ ^/terminal/([^/]+)(/.*)?$ {
        # Check if port mapping exists
        if ($gotty_backend_port = 0) {
            return 404;
        }

        # URL rewrite: /terminal/{token}/ → /{token}/
        rewrite ^/terminal/(.*)$ /$1 break;

        # Proxy to Gotty (HTTPS with self-signed cert)
        proxy_pass https://127.0.0.1:$gotty_backend_port;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host 127.0.0.1:$gotty_backend_port;
        proxy_read_timeout 3600s;
        
        # SSL configuration for Gotty self-signed cert
        proxy_ssl_verify off;
        proxy_ssl_server_name on;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/kirocli /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Fix permissions to avoid Nginx 500 errors
chmod 755 /home/ubuntu
chmod -R 755 /home/ubuntu/vue-kirocli-platform/frontend/dist

sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## Step 11 — Configure AWS IAM Identity Center

In the AWS IAM Identity Center console, update your SAML application:

| Field | Value |
|-------|-------|
| Application ACS URL | `http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/callback` |
| Application SAML audience (Entity ID) | `http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/metadata` |

Attribute mappings:

| User attribute in the application | Maps to | Format |
|-----------------------------------|---------|--------|
| Subject | `${user:email}` | emailAddress |
| email | `${user:email}` | unspecified |
| groups | `${user:groups}` | unspecified |

> **Note**: Subject must be `${user:email}`. Using `${user:name}` causes a "No access" error.

---

## Step 12 — Verify Gotty + Kiro CLI

Run as the `ubuntu` user (never with sudo):

```bash
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

**v1.1 Important Changes:**
- Gotty binds to `127.0.0.1` (not `0.0.0.0`), so it's only accessible locally
- **Gotty uses HTTPS/TLS** for secure WebSocket connections
- Nginx proxies to Gotty via `https://127.0.0.1:port` using `proxy_ssl_verify off`
- Self-signed certificate (CN=127.0.0.1) is required

Test locally on EC2:
```bash
# This should work (local HTTPS access)
curl -k https://127.0.0.1:7862/<token>/

# This will NOT work from your browser (blocked by Security Group)
# https://<EC2_IP>:7862/<token>/
```

Terminal access must go through Nginx: `http://<EC2_PUBLIC_IP>:3000/terminal/<token>/`

Press `Ctrl+C` to stop the test.

> **v1.1 Benefit:** Users no longer need to trust Gotty's self-signed certificate in their browser. Nginx handles the internal HTTPS connection to Gotty, while users access terminals via standard HTTP on port 3000.

---

## Step 13 — Verify Full Deployment

```bash
sudo systemctl status kirocli-backend
curl http://127.0.0.1:8000/api/v1/health
sudo systemctl status nginx
ss -tlnp | grep -E '3000|8000'
```

Open `http://<EC2_PUBLIC_IP>:3000` in your browser. Click "SSO Login" to authenticate via AWS IAM Identity Center.

---

## Updating the Application

### From v1.0 to v1.1

See [CHANGELOG.md](CHANGELOG.md#migration-notes) for detailed migration instructions.

Quick steps:
```bash
cd /home/ubuntu/vue-kirocli-platform
git pull origin main

# Run database migration
cd backend
source .venv/bin/activate
python scripts/upgrade_db.py

# Update Nginx configuration
sudo cp nginx/kirocli_map.conf /etc/nginx/conf.d/
sudo cp nginx/kirocli /etc/nginx/sites-available/
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
sudo nginx -t && sudo systemctl reload nginx

# Rebuild frontend
cd ../frontend
npm install && npm run build

# Restart backend
sudo systemctl restart kirocli-backend
```

### Within v1.1 (patch updates)

```bash
cd /home/ubuntu/vue-kirocli-platform
git pull origin main
sudo systemctl restart kirocli-backend
cd frontend && npm install && npm run build
```

---

## Troubleshooting

### v1.1 Specific Issues

#### Terminal shows "404 Not Found" after upgrade

The terminal URL format changed in v1.1. Old sessions need to be closed and restarted.

```bash
# Check if Nginx config is correct
sudo nginx -t
cat /etc/nginx/conf.d/gotty_routes.conf

# Restart backend to regenerate routes
sudo systemctl restart kirocli-backend
```

#### IP Whitelist not working

```bash
# Verify Nginx geo module is loaded
nginx -V 2>&1 | grep http_geo_module

# Check whitelist config
cat /etc/nginx/conf.d/ip_whitelist.conf

# Test from allowed IP
curl -I http://<EC2_IP>:3000
```

#### SNS alerts not sending

```bash
# Verify IAM role has SNS:Publish permission
aws sts get-caller-identity

# Check SNS topic ARN in database
sqlite3 /home/ubuntu/vue-kirocli-platform/backend/data.db \
  "SELECT value FROM system_config WHERE key='sns_topic_arn';"

# Test SNS from backend
cd /home/ubuntu/vue-kirocli-platform/backend
source .venv/bin/activate
python -c "import boto3; sns = boto3.client('sns', region_name='cn-northwest-1'); print(sns.publish(TopicArn='YOUR_ARN', Message='Test'))"
```

### General Issues

#### Terminal shows black screen / "connection close"

```bash
which kiro-cli
sed -i "s|KIRO_CLI_PATH=.*|KIRO_CLI_PATH=$(which kiro-cli)|" \
  /home/ubuntu/vue-kirocli-platform/backend/.env
sudo systemctl restart kirocli-backend
```

Other causes:
- Kiro CLI not authenticated (run `kiro-cli` manually to complete login first)
- Nginx configuration error (check `sudo nginx -t`)
- **v1.1:** Gotty routes not configured (check `/etc/nginx/conf.d/gotty_routes.conf`)

### Terminal URL 404 error (v1.1)

```bash
# Check Nginx configuration
sudo nginx -t
cat /etc/nginx/conf.d/gotty_routes.conf

# Check Nginx error log
sudo tail -50 /var/log/nginx/error.log

# Restart backend to regenerate routes
sudo systemctl restart kirocli-backend
```

### Backend fails to start (disk full)

```bash
df -h /
sudo apt clean
sudo journalctl --vacuum-time=3d
```

### Frontend build killed (OOM)

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
npm run build
```

### Nginx 500 error

```bash
chmod 755 /home/ubuntu
chmod -R 755 /home/ubuntu/vue-kirocli-platform/frontend/dist
sudo systemctl restart nginx
```

### SAML `invalid_response`

Verify `SAML_SP_ACS_URL` in `.env` exactly matches the Application ACS URL in IAM Identity Center. A common mistake is a duplicated `https:` prefix in `SAML_IDP_SSO_URL`.

### SAML "No access" error

Set Subject mapping to `${user:email}` with format `emailAddress`. Do not use `${user:name}`.

---

## License

MIT
