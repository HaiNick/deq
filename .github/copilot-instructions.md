# DeQ Copilot Instructions

## Project Overview

DeQ is a **bare-metal homelab dashboard** with zero external Python dependencies. It runs as a systemd service (not in Docker) providing device management, file operations, container control, and scheduled tasks. The Android companion app connects via HTTP API.

## Architecture

### Layered Structure
```
main.py              → Entry point: CLI args, server startup, scheduler init
config.py            → Config loading/saving, paths (/opt/deq/), defaults
web/handler.py       → HTTP routing (BaseHTTPRequestHandler), static serving
api/                 → REST endpoints (devices, files, tasks, health, network)
core/                → Business logic (stats, docker, device status cache)
fileops/             → File operations (local + remote via SSH)
utils/               → Subprocess wrappers, validators, SSH helpers
auth/                → API key authentication (api_key.py)
audit/               → Structured JSON audit logging (logger.py)
middleware/          → Security headers, CORS, request validation
static/              → HTML/CSS/JS (index.html is the SPA frontend)
```

### Key Patterns

**Zero Dependencies**: Uses only Python stdlib. HTTP via `http.server`, subprocess for system calls, threading for async status refresh.

**Dual-Mode Operations**: All device/file operations work locally (via `os`/subprocess) OR remotely (via SSH). Check `device.get('is_host')` to branch:
```python
if device.get('is_host'):
    # Local: os.path, subprocess.run(["docker", ...])
else:
    # Remote: SSH commands via subprocess.run(["ssh", ...])
```

**Thread-Safe Status Cache** ([core/device_status.py](core/device_status.py)): Device status is cached with `_cache_lock`. Use `refresh_device_status_async()` to update without blocking.

**Config as Global State**: `config.py` maintains `_config` dict loaded from `/opt/deq/config.json`. Call `get_config()` to read, `save_config(cfg)` to persist.

## API Conventions

- All endpoints return `{"success": bool, ...}` JSON
- Device operations: `/api/device/{id}/status|stats|wake|shutdown|docker`
- File operations: `/api/device/{id}/browse|files|upload|download`
- Tasks: `/api/tasks/{id}/run|status`

Route handling is in [web/handler.py](web/handler.py#L91) - `do_GET()`/`do_POST()` methods.

## Authentication

API key authentication is implemented in `auth/api_key.py`:
- Generate key: `GET /api/auth/setup` (first time only)
- Include header: `X-API-Key: deq_<token>` on all API requests
- Keys stored as SHA-256 hashes in config
- Auth can be enabled/disabled via `config.auth.enabled`

## Audit Logging

All security-relevant actions are logged in JSON format to `/opt/deq/logs/`:
- `audit.log` - Device actions, file ops, docker commands, auth events
- `access.log` - HTTP request log with timing
- `error.log` - Error details

Use `audit_log(AuditAction.X, target={...}, result="success")` from `audit/logger.py`.

## SSH Remote Operations

Remote device access requires configured SSH key auth. Pattern used throughout:
```python
subprocess.run(
    ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
     "-p", str(port), f"{user}@{ip}", cmd],
    capture_output=True, text=True, timeout=timeout
)
```

Use `utils/subprocess_utils.py` helpers: `run_ssh_command()`, `check_ssh_access()`.

## Important Files

| File | Purpose |
|------|---------|
| [server.py](server.py) | Legacy monolith (7700+ lines) - reference during migration |
| [static/index.html](static/index.html) | Single-page app frontend |
| [core/docker.py](core/docker.py) | Container start/stop, `is_valid_container_name()` for security |
| [fileops/manager.py](fileops/manager.py) | File copy/move/delete between local/remote devices |
| [api/tasks.py](api/tasks.py) | Task scheduling with `calculate_next_run()` logic |
| [auth/api_key.py](auth/api_key.py) | API key generation, hashing, validation |
| [audit/logger.py](audit/logger.py) | Structured audit logging with rotation |
| [utils/validators.py](utils/validators.py) | Path validation, allowed roots, input sanitization |

## Development Commands

```bash
# Run locally (default port 7654, server.py uses 5050)
python main.py --port 5050

# Production runs as systemd service from /opt/deq
sudo systemctl status deq
```

## Security Considerations

- **VPN-only access assumed** - never expose to public internet
- **Runs as root** for system control (shutdown, docker socket, /proc)
- **API Key Required**: Enable auth in production (`config.auth.enabled = true`)
- **Path Validation**: Use `validate_path_secure()` from validators - enforces allowed roots
- **No shell=True**: All subprocess calls use argument lists, never shell=True
- Validate container names with `is_valid_container_name()` before execution
- All actions are audit logged with source IP, user, and timestamps

## Code Style

- Type hints on function signatures
- Docstrings for public functions
- Return dicts with `{"success": True/False, ...}` pattern
- Handle exceptions within functions, return error dicts not raise

## Migration Note

The codebase is mid-migration from monolithic `server.py` to modular structure. See [.github/prompts/plan-modularizeDeqServer.prompt.md](.github/prompts/plan-modularizeDeqServer.prompt.md) for the migration plan. When making changes:
- Prefer the modular files (`main.py`, `api/`, `core/`) over `server.py`
- `server.py` still contains embedded HTML/JS that may be used as fallback
