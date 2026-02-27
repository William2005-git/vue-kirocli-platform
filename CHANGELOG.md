# Changelog

All notable changes to the KiroCLI Platform project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-02-27

### Added

#### Security Enhancements
- **IP Whitelist Management** - Administrators can now configure IP-based access control via Nginx geo module
  - Enable/disable whitelist globally
  - Add/remove CIDR ranges with notes
  - Automatic validation to prevent admin lockout
  - Dynamic Nginx configuration generation and reload

- **Audit Logging System** - Comprehensive event tracking for security compliance
  - Tracks login/logout, session creation/closure, admin actions, token verification failures
  - Filterable by user, event type, and time range
  - CSV export for compliance reporting
  - Asynchronous logging to avoid blocking main requests

- **Alert System** - Real-time anomaly detection with SNS notifications
  - Session burst detection (5+ sessions in 10 minutes)
  - Login failure monitoring (10+ failures in 5 minutes)
  - Multi-IP login detection (3+ IPs in 60 minutes)
  - Off-hours login alerts (configurable time window and timezone)
  - Configurable cooldown periods to prevent alert spam
  - AWS SNS integration for email/SMS notifications

- **Refresh Token System** - Enhanced session management
  - Long-lived refresh tokens (30 days) with automatic rotation
  - Short-lived access tokens (8 hours) for API security
  - Token blacklist for immediate revocation
  - Automatic cleanup of expired tokens

- **Device Fingerprinting** - Track and manage user devices
  - Browser fingerprint generation using hardware/software characteristics
  - New device login notifications
  - User-managed device list with custom names
  - Prevent deletion of current device

- **Force Logout** - Administrators can remotely terminate user sessions
  - Revokes all refresh tokens
  - Blacklists current access tokens
  - Closes all active Gotty sessions
  - Immediate effect across all devices

- **AWS Secrets Manager Integration** - Centralized secret management
  - Load sensitive configuration from AWS Secrets Manager
  - Automatic SECRET_KEY rotation detection
  - Fallback to environment variables
  - Status API to verify secret sources

#### Terminal Access Improvements
- **Nginx-Proxied Terminal Access** - Enhanced security for Gotty sessions
  - All terminal traffic now routes through Nginx reverse proxy
  - JWT-based authentication via `auth_request` directive
  - Gotty processes bind to `127.0.0.1` (no longer exposed to public)
  - **Gotty uses HTTPS/TLS** - Nginx proxies to Gotty via `https://127.0.0.1:port`
  - Self-signed certificate required (CN=127.0.0.1)
  - Nginx uses `proxy_ssl_verify off` to trust self-signed certificate
  - Dynamic route configuration using Nginx `map` directive
  - Eliminates direct port access (7860-7960 no longer needed in Security Group)
  - Users access terminals via HTTP on port 3000, no certificate warnings

- **Session Token Binding** - Stronger session security
  - Each session URL includes a random token (`/terminal/{token}/`)
  - Backend validates JWT + session ownership before allowing access
  - Prevents session hijacking and unauthorized access

#### UI/UX Improvements
- **Real-time Session Duration** - Live updates without page refresh
  - Dashboard and Sessions pages show accurate elapsed time
  - Updates every second using client-side timer
  - Proper UTC timezone handling for accurate calculations

- **Session Startup Progress** - Visual feedback during terminal launch
  - 5-stage progress indicator (0% → 30% → 60% → 80% → 95% → 100%)
  - Status messages for each stage
  - Automatic polling to detect when session is ready
  - Waits for Nginx configuration update before opening terminal

- **Settings Page Redesign** - Tabbed interface for better organization
  - Personal Info tab (existing content)
  - My Devices tab (manage trusted devices)
  - IP Whitelist tab (admin only)
  - Alert Rules tab (admin only)
  - Audit Logs tab (admin only)

#### Database Schema
- Added 8 new tables for v1.1 features:
  - `ip_whitelist` - IP access control entries
  - `audit_logs` - Security event tracking
  - `alert_rules` - Anomaly detection configuration
  - `alert_events` - Triggered alert history
  - `refresh_tokens` - Long-lived session tokens
  - `blacklisted_tokens` - Revoked access tokens
  - `user_devices` - Device fingerprint registry
  - `system_config` - Key-value configuration store

### Changed

- **Gotty Binding** - Changed from `0.0.0.0` to `127.0.0.1` for security
- **Gotty TLS** - Required for v1.1 (Nginx proxies to Gotty via HTTPS)
  - Certificate path: `/home/ubuntu/kirocli-platform/certs/gotty-cert.pem`
  - Key path: `/home/ubuntu/kirocli-platform/certs/gotty-key.pem`
  - CN must be `127.0.0.1` (matching Gotty bind address)
- **Terminal URL Format** - Changed from `https://<IP>:<PORT>/<TOKEN>/` to `http://<IP>:3000/terminal/<TOKEN>/`
- **JWT Structure** - Added `jti` (JWT ID) claim for blacklist support
- **Session Status** - Allow `starting` status in auth_request to prevent race conditions
- **Nginx Configuration** - Split into modular files:
  - `/etc/nginx/conf.d/kirocli_map.conf` - Token extraction
  - `/etc/nginx/conf.d/gotty_routes.conf` - Token-to-port mapping
  - `/etc/nginx/sites-available/kirocli` - Main site configuration

### Fixed

- **Timezone Handling** - Fixed UTC time display issues
  - Dashboard "启动时间" now shows correct relative time (e.g., "刚刚" instead of "8 小时前")
  - Session duration calculation now uses `dayjs.utc()` for proper timezone conversion
  - Sessions page timestamps display in local timezone
  - All time comparisons use consistent UTC base

- **SNS Region Detection** - Extract AWS region from SNS Topic ARN
  - Fixes "You must specify a region" error when testing SNS alerts
  - Automatically parses region from ARN format: `arn:aws-cn:sns:cn-northwest-1:...`
  - Falls back to `AWS_REGION` environment variable if ARN parsing fails

- **Session Alert Context** - Include `client_ip` and `username` in session creation alerts
  - Fixes missing context data in alert notifications
  - Properly passes user information from API endpoint to alert service

### Security

- **Reduced Attack Surface** - Gotty no longer directly accessible from internet
- **Enhanced Authentication** - Multi-layer verification (JWT + session token + user ownership)
- **Audit Trail** - All security-relevant events are logged with IP and user agent
- **Anomaly Detection** - Automated alerts for suspicious activity patterns
- **Token Revocation** - Immediate session termination capability for compromised accounts

### Documentation

- Added `docs/EC2_DEPLOYMENT_V1.1.md` - Comprehensive v1.1 deployment guide
- Added `docs/TESTING_V1.1.md` - Testing procedures for new features
- Added `scripts/deploy.sh` - Automated deployment script
- Added `scripts/README.md` - Deployment script documentation
- Updated `.env.example` - Added all v1.1 configuration options

### Migration Notes

**From v1.0 to v1.1:**

1. **Database Migration** - Run upgrade script to add new tables:
   ```bash
   cd backend
   source .venv/bin/activate
   python scripts/upgrade_db.py
   ```

2. **Environment Variables** - Add new required variables to `.env`:
   - `AWS_REGION` (optional, for SNS)
   - `SECRETS_MANAGER_SECRET_NAME` (optional, for AWS Secrets Manager)
   - `SECRETS_MANAGER_FALLBACK_TO_ENV` (optional, default: true)

3. **Nginx Configuration** - Update Nginx config files:
   ```bash
   # Backup existing config
   sudo cp /etc/nginx/sites-available/kirocli /etc/nginx/sites-available/kirocli.v1.0.bak
   
   # Deploy new config files
   sudo cp nginx/kirocli_map.conf /etc/nginx/conf.d/
   sudo cp nginx/kirocli /etc/nginx/sites-available/
   
   # Create empty gotty_routes.conf (will be populated by backend)
   sudo touch /etc/nginx/conf.d/gotty_routes.conf
   sudo chown ubuntu:ubuntu /etc/nginx/conf.d/gotty_routes.conf
   
   # Test and reload
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. **Security Group** - Ports 7860-7960 are no longer needed (can be removed for security)

5. **Frontend Rebuild** - Required for new UI features:
   ```bash
   cd frontend
   npm install
   npm run build
   sudo systemctl reload nginx
   ```

6. **Backend Restart** - Required for new API endpoints:
   ```bash
   sudo systemctl restart kirocli-backend
   ```

### Breaking Changes

- **Terminal URL Format** - Old direct Gotty URLs (`https://<IP>:<PORT>/<TOKEN>/`) no longer work
  - Users must access terminals through Nginx proxy (`http://<IP>:3000/terminal/<TOKEN>/`)
  - Existing session URLs will break after upgrade (users need to start new sessions)

- **Gotty Certificate** - Still required, but certificate subject changed
  - v1.0: Certificate for `<EC2_PUBLIC_IP>` (public access)
  - v1.1: Certificate for `127.0.0.1` (local access only)
  - Users no longer see certificate warnings in browser

### Known Issues

- **Nginx Reload Timing** - 2-second delay between session creation and Nginx config update
  - Frontend compensates with progress indicator and polling
  - Future versions may use dynamic upstream resolution to eliminate reload

- **Device Fingerprint Accuracy** - Browser fingerprints can change with updates
  - Users may see "new device" notifications after browser updates
  - Fingerprint is best-effort, not cryptographically secure

---

## [1.0.0] - 2026-01-15

### Added
- Initial release of KiroCLI Platform
- AWS IAM Identity Center (SAML 2.0) authentication
- Browser-based terminal sessions via Gotty
- User and group management with role-based access control
- Session management (start, monitor, close)
- Concurrent session limits and daily quotas
- Auto cleanup of idle sessions
- System monitoring dashboard
- SQLite database with 6 core tables
- FastAPI backend with JWT authentication
- Vue 3 + Ant Design Vue frontend
- Nginx reverse proxy for API and static files
- Gotty TLS encryption for terminal traffic
- Session isolation (one Gotty process per user session)

### Security
- No AWS access key distribution (SSO-only authentication)
- Random 16-character session tokens
- TLS encryption for all terminal traffic
- JWT-based API authentication (8-hour expiry)
- Session isolation and automatic cleanup

---

## Version Comparison

| Feature | v1.0 | v1.1 |
|---------|------|------|
| SSO Authentication | ✅ | ✅ |
| Browser Terminal | ✅ | ✅ |
| Session Management | ✅ | ✅ |
| User/Group Management | ✅ | ✅ |
| IP Whitelist | ❌ | ✅ |
| Audit Logging | ❌ | ✅ |
| Alert System | ❌ | ✅ |
| Refresh Tokens | ❌ | ✅ |
| Device Fingerprinting | ❌ | ✅ |
| Force Logout | ❌ | ✅ |
| Nginx-Proxied Terminals | ❌ | ✅ |
| AWS Secrets Manager | ❌ | ✅ |
| Real-time Duration | ❌ | ✅ |
| Startup Progress | ❌ | ✅ |
| Direct Gotty Access | ✅ | ❌ (security) |
| Public Gotty Ports | Required | Not Required |

---

[1.1.0]: https://github.com/YOUR_USERNAME/vue-kirocli-platform/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/YOUR_USERNAME/vue-kirocli-platform/releases/tag/v1.0.0
