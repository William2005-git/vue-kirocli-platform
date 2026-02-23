# KiroCLI Platform

A web-based platform for managing Kiro CLI terminal sessions via browser, with AWS IAM Identity Center (SSO) authentication.

## Features

- **SSO Authentication** via AWS IAM Identity Center (SAML 2.0)
- **Browser-based Terminal** powered by Gotty + Kiro CLI
- **Session Management** — start, monitor, and close terminal sessions
- **User & Group Management** with role-based access control
- **System Monitoring** dashboard

## Architecture

```
Browser → Nginx (port 3000) → FastAPI Backend (127.0.0.1:8000)
                                      ↓
                              Gotty (ports 7860–7960) → kiro-cli
```

All components run on a single EC2 instance.

---

## Prerequisites

- AWS EC2 instance running **Ubuntu 22.04** (recommended: t3.medium or larger)
- AWS IAM Identity Center configured with a SAML application
- Kiro CLI installed on the EC2 instance
- EC2 Security Group inbound rules:

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | Your IP | SSH |
| 3000 | TCP | 0.0.0.0/0 | Web UI (Nginx) |
| 7860–7960 | TCP | 0.0.0.0/0 | Gotty terminal sessions |

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

Gotty requires a TLS certificate to serve HTTPS/WSS connections. Generate a self-signed certificate:

```bash
sudo mkdir -p /opt/kirocli-certs

sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -keyout /opt/kirocli-certs/gotty.key \
  -out /opt/kirocli-certs/gotty.crt \
  -subj "/CN=<EC2_PUBLIC_IP>/O=KiroCLI/C=US" \
  -addext "subjectAltName=IP:<EC2_PUBLIC_IP>"

sudo chmod 644 /opt/kirocli-certs/gotty.crt
sudo chmod 640 /opt/kirocli-certs/gotty.key
sudo chown ubuntu:ubuntu /opt/kirocli-certs/gotty.key
```

Verify the certificate was created:

```bash
ls -la /opt/kirocli-certs/
openssl x509 -in /opt/kirocli-certs/gotty.crt -noout -text | grep -E "Subject:|Not After"
```

> **Note on self-signed certificates**: When users first open a Gotty terminal in the browser, they will see a certificate warning. They need to click "Advanced" → "Proceed" once per browser session to trust the certificate. If you have a domain name with a valid CA-signed certificate, use that instead for a seamless experience.

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

Create the `.env` file from the example:

```bash
cp .env.example .env
nano .env
```

Fill in all required values (no inline comments — pydantic-settings does not support them):

```env
APP_NAME=KiroCLI Platform
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate with: openssl rand -hex 32>

DATABASE_URL=sqlite:////home/ubuntu/vue-kirocli-platform/backend/data.db

# AWS IAM Identity Center — copy from your SAML application settings page
SAML_IDP_ENTITY_ID=<IdP Entity ID from IAM Identity Center>
SAML_IDP_SSO_URL=<SSO URL from IAM Identity Center>
SAML_IDP_X509_CERT=<certificate content without BEGIN/END lines>
SAML_SP_ENTITY_ID=http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/metadata
SAML_SP_ACS_URL=http://<EC2_PUBLIC_IP>:3000/api/v1/auth/saml/callback

GOTTY_PRIMARY_PORT=7860
GOTTY_PORT_START=7861
GOTTY_PORT_END=7960
GOTTY_PATH=/usr/local/bin/gotty
KIRO_CLI_PATH=<absolute path from: which kiro-cli>
GOTTY_CERT_PATH=/opt/kirocli-certs/gotty.crt
GOTTY_KEY_PATH=/opt/kirocli-certs/gotty.key
GOTTY_REMOTE_MODE=false
GOTTY_REMOTE_HOST=<EC2_PUBLIC_IP>

CORS_ORIGINS=["http://<EC2_PUBLIC_IP>:3000"]

LOG_LEVEL=INFO
LOG_FILE=/home/ubuntu/vue-kirocli-platform/logs/backend.log

JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=8

SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_MINUTES=5
```

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

```bash
sudo tee /etc/nginx/sites-available/kirocli << 'EOF'
server {
    listen 3000;
    server_name _;

    root /home/ubuntu/vue-kirocli-platform/frontend/dist;
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

Before using the platform, manually verify Gotty can launch kiro-cli with TLS.

**Run as the `ubuntu` user (never with sudo):**

```bash
gotty \
  --address 0.0.0.0 \
  --port 7862 \
  --permit-write \
  --reconnect \
  --random-url \
  --random-url-length 16 \
  --ws-origin ".*" \
  --tls \
  --tls-crt /opt/kirocli-certs/gotty.crt \
  --tls-key /opt/kirocli-certs/gotty.key \
  $(which kiro-cli)
```

The output will show a URL like:
```
HTTP server is listening at: https://0.0.0.0:7862/abcd1234efgh5678/
```

Open `https://<EC2_PUBLIC_IP>:7862/abcd1234efgh5678/` in your browser. Since this is a self-signed certificate, click **"Advanced" → "Proceed to site"** to trust it. You should then see the Kiro CLI terminal. Press `Ctrl+C` to stop.

> **Important**: Users must visit the Gotty HTTPS URL directly once in their browser to trust the self-signed certificate before the embedded terminal in the platform will work.

---

## Step 13 — Verify Full Deployment

```bash
# Check backend service
sudo systemctl status kirocli-backend

# Check backend API
curl http://127.0.0.1:8000/health

# Check Nginx
sudo systemctl status nginx

# Check listening ports
ss -tlnp | grep -E '3000|8000'
```

Open `http://<EC2_PUBLIC_IP>:3000` in your browser. You should see the login page. Click "SSO Login" to authenticate via AWS IAM Identity Center.

---

## Updating the Application

```bash
cd /home/ubuntu/vue-kirocli-platform

# Pull latest code
git pull origin main

# Restart backend
sudo systemctl restart kirocli-backend

# Rebuild frontend
cd frontend && npm install && npm run build
```

---

## Troubleshooting

### Terminal shows black screen / "connection close"

The most common cause is an incorrect `KIRO_CLI_PATH`.

```bash
# Find the correct path
which kiro-cli

# Fix .env and restart
sed -i "s|KIRO_CLI_PATH=.*|KIRO_CLI_PATH=$(which kiro-cli)|" \
  /home/ubuntu/vue-kirocli-platform/backend/.env
sudo systemctl restart kirocli-backend
```

Other causes: Security Group not open for ports 7860–7960, or kiro-cli not authenticated (run `kiro-cli` manually to complete login first).

### Frontend build killed (OOM)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
npm run build
```

### Nginx 500 error

```bash
sudo tail -20 /var/log/nginx/error.log
chmod 755 /home/ubuntu
chmod -R 755 /home/ubuntu/vue-kirocli-platform/frontend/dist
sudo systemctl restart nginx
```

### Backend service fails to start

```bash
sudo journalctl -u kirocli-backend -n 50 --no-pager
```

### SAML `invalid_response`

Verify that `SAML_SP_ACS_URL` in `.env` exactly matches the Application ACS URL in IAM Identity Center (protocol, IP, port, path). A common mistake is a duplicated `https:` prefix in `SAML_IDP_SSO_URL`.

### SAML redirect loop (302 loop)

Verify `SAML_SP_ACS_URL` and `SAML_SP_ENTITY_ID` use the EC2 public IP with port 3000, not localhost or port 8000.

### SAML "No access" error

In IAM Identity Center Attribute mappings, set Subject to `${user:email}` with format `emailAddress`. Do not use `${user:name}`.

---

## License

MIT
