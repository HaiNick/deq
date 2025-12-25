# DeQ Roadmap & Security Hardening Tracker

> **Last Updated:** 2025-12-25  
> **Status:** Phase 1 In Progress

---

## Priority Legend

| Priority | Label | Description |
|----------|-------|-------------|
| 🔴 | Critical | Security foundation - must complete first |
| 🟠 | High | Core product value |
| 🟡 | Medium | Important enhancements |
| 🟢 | Low | Nice-to-have / bigger projects |

---

## 🔒 SECURITY (Highest Leverage First)

### 1. Authentication & Authorization 🔴

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [x] | **Minimum: API Key auth** | 🔴 Critical | `X-API-Key` header, configurable, rotatable |
| [ ] | Session-based login with short-lived tokens | 🟠 High | Especially important for mobile app |
| [ ] | Users + roles (admin/viewer) | 🟡 Medium | RBAC system |
| [ ] | Per-device permissions | 🟡 Medium | Granular access control |
| [ ] | Rate limit login attempts | 🟢 Low | Brute-force protection |

**Implementation Notes:**
- ✅ API keys stored hashed (SHA-256)
- ✅ `auth/api_key.py` - key generation, validation, secure comparison
- Token expiry: 15-60 minutes for sessions (TODO)
- Consider JWT for stateless auth

---

### 2. Transport Security (TLS) 🔴

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Support HTTPS | 🔴 Critical | Required for file transfers & credentials |
| [ ] | Self-signed cert generation | 🟠 High | Quick bootstrap option |
| [ ] | Let's Encrypt integration | 🟡 Medium | Better UX for public-facing |
| [ ] | HTTP → HTTPS redirect | 🟠 High | Auto-redirect when TLS enabled |

**Implementation Notes:**
- Use `ssl` module with `http.server`
- Cert storage: `/opt/deq/certs/`
- Config option: `tls.enabled`, `tls.cert_path`, `tls.key_path`

---

### 3. Input Hardening 🔴

> ⚠️ **This is where most RCE bugs come from**

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [x] | **Path traversal protection** | 🔴 Critical | `realpath()`, enforce allowed roots, reject `../` escapes |
| [x] | **Eliminate `shell=True`** | 🔴 Critical | Pass argv lists only |
| [x] | **Command injection prevention** | 🔴 Critical | Strict allowlists for commands |
| [x] | Sanitize device/container IDs | 🔴 Critical | Only known-safe characters: `[a-zA-Z0-9_-]` |
| [x] | Request size limits | 🟠 High | Prevent memory exhaustion on large POSTs |
| [ ] | Validate all JSON schema | 🟠 High | Reject malformed requests early |

**Current State Audit:**
- [x] Audit `subprocess.run()` calls in `utils/subprocess_utils.py`
- [x] Audit `core/docker.py` - check `is_valid_container_name()`
- [x] Audit `fileops/` for path validation
- [ ] Audit `server.py` legacy code

**Allowed Path Roots:**
```python
ALLOWED_ROOTS = [
    "/home",
    "/mnt",
    "/opt/deq/uploads",
    # Add per-device allowed paths in config
]
```

---

### 4. Audit Logging 🔴

> **Non-negotiable once auth is implemented**

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [x] | Log all device actions | 🔴 Critical | wake, shutdown, reboot |
| [x] | Log all file operations | 🔴 Critical | upload, download, delete, move |
| [x] | Log config changes | 🔴 Critical | Any settings modification |
| [x] | Log Docker actions | 🔴 Critical | start, stop, restart, exec |
| [x] | Log authentication events | 🔴 Critical | Login success/failure, token refresh |
| [x] | Include required fields | 🔴 Critical | timestamp, user, source IP, target, result |
| [x] | Log rotation | 🟠 High | Size/time-based rotation |
| [ ] | Retention policy | 🟠 High | Configurable retention period |

**Log Format (JSON structured):**
```json
{
  "timestamp": "2025-12-25T10:30:00Z",
  "level": "INFO",
  "action": "device.shutdown",
  "user": "admin",
  "source_ip": "192.168.1.100",
  "target": {"device_id": "nas-01", "device_name": "TrueNAS"},
  "result": "success",
  "request_id": "uuid-here"
}
```

**File Locations:**
- Audit log: `/opt/deq/logs/audit.log`
- Access log: `/opt/deq/logs/access.log`
- Error log: `/opt/deq/logs/error.log`

---

### 5. Secrets Management 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Support environment variables for secrets | 🟠 High | `DEQ_API_KEY`, `DEQ_DB_KEY` |
| [ ] | Separate secrets file | 🟠 High | `/opt/deq/secrets.json` with `chmod 600` |
| [ ] | Encrypt sensitive config fields | 🟡 Medium | AES encryption for stored secrets |
| [ ] | Never store API keys in plaintext JSON | 🟠 High | Hash or encrypt at rest |

**Environment Variables:**
```bash
DEQ_API_KEY=<hashed-key>
DEQ_TLS_CERT=/path/to/cert
DEQ_TLS_KEY=/path/to/key
DEQ_SECRET_KEY=<encryption-key>
```

---

### 6. Web Hardening 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | CSRF protection | 🟠 High | If using cookies/sessions |
| [x] | CORS defaults (deny by default) | 🟠 High | Whitelist allowed origins |
| [x] | Security headers | 🟠 High | CSP, X-Content-Type-Options, X-Frame-Options |
| [ ] | Cookie security flags | 🟠 High | `HttpOnly`, `Secure`, `SameSite=Strict` |

**Headers to Add:**
```python
headers = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
```

---

## ✨ FEATURES

### A) Device Management 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Device groups/tags | 🟠 High | Servers, Media, IoT, etc. |
| [ ] | Device templates | 🟡 Medium | Pre-fill SSH/docker settings |
| [ ] | Bulk operations | 🟡 Medium | Wake/reboot/shutdown multiple devices |
| [ ] | Dependency chains | 🟢 Low | Wake NAS → start Plex → wait healthy |

**Config Schema Addition:**
```json
{
  "devices": [{
    "id": "nas-01",
    "groups": ["storage", "critical"],
    "template": "synology-nas",
    "dependencies": ["router-01"]
  }]
}
```

---

### B) Monitoring & Alerts 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [x] | **ntfy.sh integration** | 🟠 High | Push notifications |
| [ ] | Gotify support | 🟡 Medium | Self-hosted alternative |
| [ ] | Pushover support | 🟡 Medium | Popular mobile option |
| [ ] | Email notifications | 🟡 Medium | SMTP integration |
| [x] | Webhook support | 🟠 High | Discord, Slack, generic |
| [x] | Alert: device offline | 🟠 High | Configurable threshold |
| [x] | Alert: container stopped | 🟠 High | Unexpected stop detection |
| [ ] | Alert: disk full | 🟡 Medium | Configurable threshold % |
| [ ] | Alert: temperature high | 🟡 Medium | Hardware monitoring |
| [ ] | Alert: SMART warnings | 🟢 Low | Disk health |
| [ ] | HTTP health checks | 🟠 High | Status code + body match |
| [ ] | Port checks | 🟠 High | TCP port availability |
| [ ] | Custom health scripts | 🟡 Medium | User-defined checks |
| [ ] | Auto-restart via SSH | 🟢 Low | On health check failure |

---

### C) Real-time Updates 🟡

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | WebSocket support | 🟡 Medium | Live device/container status |
| [ ] | Server-Sent Events (SSE) | 🟡 Medium | Simpler alternative |
| [ ] | File transfer progress | 🟡 Medium | Real-time upload/download % |
| [ ] | Polling endpoint fallback | 🟢 Low | For simpler clients |

---

### D) Metrics History & Graphs 🟡

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | SQLite metrics storage | 🟡 Medium | CPU, RAM, disk over time |
| [ ] | Dashboard: 24h view | 🟡 Medium | Recent history |
| [ ] | Dashboard: 7d view | 🟡 Medium | Week view |
| [ ] | Dashboard: 30d view | 🟢 Low | Month view |
| [ ] | Prometheus export | 🟢 Low | `/metrics` endpoint |
| [ ] | InfluxDB integration | 🟢 Low | Time-series DB |

**Schema (SQLite):**
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    device_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    cpu_percent REAL,
    memory_percent REAL,
    disk_percent REAL,
    temperature REAL
);
CREATE INDEX idx_metrics_device_time ON metrics(device_id, timestamp);
```

---

### E) Enhanced Docker Support 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [x] | **Container logs view** | 🟠 High | Tail logs with limit |
| [ ] | Exec shell into container | 🟡 Medium | Admin-only, heavily audited |
| [ ] | Docker Compose stack support | 🟠 High | up/down/restart stacks |
| [ ] | Show resource limits | 🟡 Medium | Memory/CPU constraints |
| [ ] | Show restart counts | 🟡 Medium | Container stability info |
| [ ] | Show health status | 🟠 High | Healthcheck results |
| [ ] | Image update notifications | 🟢 Low | Watchtower-style awareness |

**Security for Exec:**
- Admin role required
- Explicit allowlist mode option
- Full command logging
- Session recording (optional)

---

### F) Backups 🟡

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Backup verification | 🟡 Medium | Checksum validation |
| [ ] | Restore workflow | 🟡 Medium | UI for restore operations |
| [ ] | Incremental backup stats | 🟡 Medium | Track what changed |
| [ ] | S3/B2 targets | 🟢 Low | Cloud backup destinations |
| [ ] | rclone integration | 🟢 Low | Multi-cloud support |

---

### G) Tasks & Automation 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Conditional tasks | 🟠 High | Run only if device online, container running |
| [ ] | Task chains with failure handling | 🟠 High | Continue/abort on failure |
| [ ] | Cron expressions | 🟡 Medium | More flexible scheduling |
| [ ] | Task history | 🟠 High | Last N runs + logs |
| [ ] | Task templates | 🟡 Medium | Reusable task definitions |

**Task Schema Enhancement:**
```json
{
  "tasks": [{
    "id": "backup-nas",
    "conditions": {
      "device_online": "nas-01",
      "container_running": "backup-agent"
    },
    "on_failure": "notify",
    "schedule": "0 2 * * *"
  }]
}
```

---

### H) Terminal/Console Access 🟢

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Web SSH terminal | 🟢 Low | xterm.js integration |
| [ ] | Command history | 🟢 Low | Per-user history |
| [ ] | Command allowlist mode | 🟢 Low | Restrict to safe commands |
| [ ] | Session recording | 🟢 Low | Audit trail for terminal |

**⚠️ Security Requirements:**
- Admin-only access
- Explicit device allowlist
- Full session logging
- Rate limiting

---

## 🏗️ ARCHITECTURE / ENGINEERING

### 1. Backend Store Migration 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | SQLite for history | 🟠 High | Metrics, logs, sessions |
| [ ] | SQLite for task runs | 🟠 High | Execution history |
| [ ] | SQLite for audit logs | 🟠 High | Structured audit trail |
| [ ] | Keep JSON for static config | 🟡 Medium | Devices, settings |
| [ ] | Migration script | 🟠 High | Existing data → SQLite |

**Database Location:** `/opt/deq/deq.db`

---

### 2. API Hygiene 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | API versioning `/api/v1/` | 🟠 High | Future-proof endpoints |
| [ ] | OpenAPI/Swagger spec | 🟡 Medium | Auto-generated docs |
| [ ] | Pagination for file listings | 🟠 High | Handle large directories |
| [ ] | Stable error schema | 🟠 High | Consistent error format |

**Error Schema:**
```json
{
  "success": false,
  "error": {
    "code": "DEVICE_OFFLINE",
    "message": "Device nas-01 is not reachable",
    "details": {}
  },
  "request_id": "uuid-here"
}
```

---

### 3. Observability 🟠

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Structured JSON logs | 🟠 High | Machine-parseable |
| [ ] | Request IDs | 🟠 High | Trace requests end-to-end |
| [ ] | Health endpoint enhanced | 🟠 High | Uptime, version, last errors |
| [ ] | Dependency checks | 🟡 Medium | SSH, Docker, DB status |

**Health Endpoint Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "last_error": null,
  "dependencies": {
    "database": "ok",
    "docker": "ok"
  }
}
```

---

### 4. Performance & Reliability 🟡

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | SSH connection reuse | 🟡 Medium | ControlMaster pooling |
| [ ] | Cache hot endpoints | 🟡 Medium | Device stats TTL ~5s |
| [ ] | Async polling | 🟡 Medium | asyncio or thread pool |
| [ ] | Graceful shutdown | 🟠 High | Finish running tasks |

---

### 5. Extensibility 🟢

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | Plugin/hook system | 🟢 Low | Event-driven architecture |
| [ ] | Custom device types | 🟢 Low | Plugin for new device protocols |
| [ ] | Integration hooks | 🟢 Low | Pre/post action hooks |

---

## 📱 UX / MOBILE

| Status | Item | Priority | Notes |
|--------|------|----------|-------|
| [ ] | PWA offline cache | 🟡 Medium | Last-known device status |
| [ ] | Biometric unlock | 🟡 Medium | Token in secure keystore |
| [ ] | Widgets/quick actions endpoint | 🟡 Medium | Optimized for widgets |
| [ ] | Dark/light theme auto-switch | 🟢 Low | System preference detection |

---

## 📅 PRIORITY ROADMAP

### Phase 1: Security Foundation 🔴
> **Timeline: Immediate** - ✅ MOSTLY COMPLETE

1. [x] API key auth + `X-API-Key` header validation
2. [x] Audit logging (all actions)
3. [x] Remove all `shell=True` / command injection risks
4. [x] Strong path validation + allowed roots
5. [x] Request size limits + basic rate limiting

### Phase 2: Core Product Value 🟠
> **Timeline: After Phase 1**

6. [ ] Notifications (ntfy.sh/webhooks) + health checks
7. [ ] Docker logs + compose stack actions
8. [ ] Task history + conditional task chains
9. [ ] SQLite backend for history/metrics

### Phase 3: Enhanced Features 🟡
> **Timeline: After Phase 2**

10. [ ] Full multi-user RBAC + per-device permissions
11. [ ] WebSocket real-time updates
12. [ ] Metrics graphs over time
13. [ ] TLS/HTTPS support

### Phase 4: Advanced 🟢
> **Timeline: Future**

14. [ ] Plugin system
15. [ ] Web SSH terminal
16. [ ] Prometheus/InfluxDB export

---

## 📝 Implementation Notes

### File Structure for New Features

```
deq/
├── auth/                     # ✅ IMPLEMENTED
│   ├── __init__.py
│   └── api_key.py            # API key generation, validation, secure comparison
├── audit/                    # ✅ IMPLEMENTED
│   ├── __init__.py
│   └── logger.py             # Structured JSON audit logging with rotation
├── middleware/               # ✅ IMPLEMENTED
│   ├── __init__.py
│   └── security.py           # Security headers, CORS, request validation
├── notifications/            # TODO
│   ├── __init__.py
│   ├── ntfy.py               # ntfy.sh integration
│   └── webhook.py            # Generic webhooks
├── db/                       # TODO
│   ├── __init__.py
│   ├── schema.py             # SQLite schema
│   └── migrations.py         # Schema migrations
```

### Breaking Changes to Track

- [ ] `/api/` → `/api/v1/` migration
- [ ] Config schema changes for auth
- [ ] New required headers for authenticated endpoints

---

## 🔗 Related Documents

- [Migration Plan](prompts/plan-modularizeDeqServer.prompt.md)
- [Copilot Instructions](copilot-instructions.md)

---

## 📊 Progress Tracking

| Category | Total | Done | Progress |
|----------|-------|------|----------|
| Security | 25 | 15 | 60% |
| Features | 45 | 0 | 0% |
| Architecture | 15 | 0 | 0% |
| UX/Mobile | 4 | 0 | 0% |
| **Total** | **89** | **15** | **17%** |

---

*Update this document as items are completed. Use git commits to track progress over time.*
