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

**🚀 New in v1.1**: Automated deployment in 3 simple steps!

```bash
# 1. Connect to EC2
ssh -i /path/to/your-key.pem ubuntu@<YOUR_EC2_IP>

# 2. Download code to ~/kirocli-platform
git clone https://github.com/YOUR_USERNAME/vue-kirocli-platform.git ~/kirocli-platform
cd ~/kirocli-platform

# 3. Run installation script
chmod +x scripts/install.sh
./scripts/install.sh
```

That's it! The script will guide you through the rest.

**What the script does**:
- ✅ Installs all system dependencies (Node.js, Python, Nginx, SQLite)
- ✅ Installs Gotty terminal tool
- ✅ Generates TLS certificates
- ✅ Configures backend environment and database
- ✅ Builds frontend application
- ✅ Configures Nginx and systemd services
- ✅ Starts all services

**Installation time**: ~10-15 minutes

For detailed instructions, see:
- **Quick Start Guide**: [docs/QUICK_START.md](docs/QUICK_START.md) - Step-by-step with troubleshooting
- **Full Deployment Guide**: [docs/EC2_DEPLOYMENT_V1.1.md](docs/EC2_DEPLOYMENT_V1.1.md) - Manual deployment steps
- **Script Documentation**: [scripts/README.md](scripts/README.md) - Installation script details

---

## Post-Installation Configuration

After the installation script completes, configure AWS IAM Identity Center:

### Update SAML Application

In the AWS IAM Identity Center console, update your SAML application:

| Field | Value |
|-------|-------|
| Application ACS URL | `http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/callback` |
| Application SAML audience (Entity ID) | `http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/metadata` |

### Configure Attribute Mappings

| User attribute in the application | Maps to | Format |
|-----------------------------------|---------|--------|
| Subject | `${user:email}` | emailAddress |
| email | `${user:email}` | unspecified |
| groups | `${user:groups}` | unspecified |

> **Important**: Subject must be `${user:email}` with format `emailAddress`. Using `${user:name}` causes a "No access" error.

### Verify Deployment

Open `http://<EC2_PUBLIC_IP>:3000` in your browser and click "SSO Login".

---

## Updating the Application

### From v1.0 to v1.1

See [CHANGELOG.md](CHANGELOG.md#migration-notes) for detailed migration instructions.

Quick steps:
```bash
cd ~/kirocli-platform
git pull origin main

# Run database migration
cd backend
source .venv/bin/activate
python scripts/upgrade_db.py

# Update Nginx configuration
sudo cp nginx/kirocli_map.conf /etc/nginx/conf.d/
sudo cp nginx/kirocli /etc/nginx/sites-available/
sudo touch /etc/nginx/conf.d/gotty_routes.conf
sudo chown $USER:$USER /etc/nginx/conf.d/gotty_routes.conf
sudo nginx -t && sudo systemctl reload nginx

# Rebuild frontend
cd ../frontend
npm install && npm run build

# Restart backend
sudo systemctl restart kirocli-backend
```

### Within v1.1 (patch updates)

```bash
cd ~/kirocli-platform
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
sqlite3 ~/kirocli-platform/backend/data.db \
  "SELECT value FROM system_config WHERE key='sns_topic_arn';"

# Test SNS from backend
cd ~/kirocli-platform/backend
source .venv/bin/activate
python -c "import boto3; sns = boto3.client('sns', region_name='cn-northwest-1'); print(sns.publish(TopicArn='YOUR_ARN', Message='Test'))"
```

### General Issues

#### Terminal shows black screen / "connection close"

```bash
which kiro-cli
sed -i "s|KIRO_CLI_PATH=.*|KIRO_CLI_PATH=$(which kiro-cli)|" \
  ~/kirocli-platform/backend/.env
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
