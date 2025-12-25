# Plan: Modularize DeQ Server into Multi-File Structure

**Overview:** Break the 7,769-line monolithic server.py into a layered architecture with separate modules for API routes, business logic (stats, device management, file operations), infrastructure (HTTP handler, config), and static assets. This will improve maintainability, testability, and development velocity while preserving the zero-dependency philosophy.

## Implementation Steps

### 1. Extract Config Management
Create [config.py](config.py) with:
- `loadConfig()` - Load configuration from JSON file
- `saveConfig()` - Persist configuration changes
- Default settings structure
- Path management for data directory

### 2. Business Logic Layer - `core/` Module
Create core functionality modules:
- **[core/stats.py](core/stats.py)** - Gather local and remote stats, parse /proc, SSH stat gathering
- **[core/device_status.py](core/device_status.py)** - Status caching, thread-safe async refresh, status snapshots
- **[core/docker.py](core/docker.py)** - Container orchestration, docker scanning, start/stop operations
- **[core/network.py](core/network.py)** - Tailscale/ARP network scanning, device discovery

### 3. File Operations Layer - `fileops/` Module
Create file management modules:
- **[fileops/manager.py](fileops/manager.py)** - File operations (copy, move, zip, delete, rename)
- **[fileops/browser.py](fileops/browser.py)** - Folder listing for local and remote systems
- **[fileops/ssh.py](fileops/ssh.py)** - SSH-based remote file operations

### 4. API Routes Layer - `api/` Module
Create API endpoint handlers:
- **[api/__init__.py](api/__init__.py)** - Module initialization
- **[api/devices.py](api/devices.py)** - Device endpoints (status, stats, wake, shutdown, docker)
- **[api/files.py](api/files.py)** - File endpoints (list, browse, upload, download, operations)
- **[api/tasks.py](api/tasks.py)** - Task endpoints (run, status, scheduling)
- **[api/health.py](api/health.py)** - Health check endpoints
- **[api/network.py](api/network.py)** - Network scanning endpoints

### 5. HTTP Handler & Web Layer
Create [web/handler.py](web/handler.py) with:
- HTTP request handler class (BaseHTTPRequestHandler subclass)
- Route dispatcher mapping `/api/*` endpoints to api/ modules
- Static file serving (/, /manifest.json, /icon.svg, /fonts/*)
- Request validation and error handling

### 6. Static Assets
Extract embedded HTML/CSS/JS into `static/` directory:
- **[static/index.html](static/index.html)** - Main HTML shell
- **[static/style.css](static/style.css)** - All embedded CSS
- **[static/app.js](static/app.js)** - All embedded JavaScript

Web handler will load these at startup or runtime.

### 7. Entry Point
Create [main.py](main.py) as the primary entry point:
- Parse CLI arguments
- Load configuration from config.py
- Initialize device status cache
- Initialize task scheduler
- Start HTTP server with web/handler.py
- Handle graceful shutdown

### 8. Utilities (Optional)
Create [utils/](utils/) module for shared functions:
- **[utils/validators.py](utils/validators.py)** - Input validation (container names, device IDs, paths)
- **[utils/ssh_utils.py](utils/ssh_utils.py)** - SSH connection pooling, command execution helpers
- **[utils/subprocess_utils.py](utils/subprocess_utils.py)** - Safe subprocess execution wrappers

## Proposed Directory Structure

```
deq/
├── main.py                          # Entry point
├── config.py                        # Configuration management
├── api/
│   ├── __init__.py
│   ├── devices.py                   # Device API endpoints
│   ├── files.py                     # File operations endpoints
│   ├── tasks.py                     # Task management endpoints
│   ├── health.py                    # Health check endpoints
│   └── network.py                   # Network scanning endpoints
├── core/
│   ├── __init__.py
│   ├── stats.py                     # Local + remote stat gathering
│   ├── device_status.py             # Status caching, async refresh
│   ├── docker.py                    # Container orchestration
│   └── network.py                   # Network scanning (discovery)
├── fileops/
│   ├── __init__.py
│   ├── manager.py                   # File operations (copy/move/zip/delete)
│   ├── browser.py                   # Folder browsing
│   └── ssh.py                       # SSH file operations
├── web/
│   ├── __init__.py
│   └── handler.py                   # HTTP request handler
├── utils/
│   ├── __init__.py
│   ├── validators.py                # Input validation
│   ├── ssh_utils.py                 # SSH helpers
│   └── subprocess_utils.py           # Subprocess helpers
├── static/
│   ├── index.html                   # Main HTML (extracted from embedded)
│   ├── style.css                    # CSS (extracted from embedded)
│   ├── app.js                       # JavaScript (extracted from embedded)
│   ├── icon.svg                     # App icon
│   └── fonts/                       # Font files (extract from embedded)
├── install.sh                       # Existing installer
├── server.py                        # DEPRECATED: Old monolithic file (keep for reference during migration)
├── LICENSE                          # Existing license
└── README.md                        # Existing README
```

## Key Design Principles

1. **Zero External Dependencies** - Maintain stdlib-only approach; no pip packages required
2. **Backwards Compatible Data Format** - Keep JSON config format, `/opt/deq` data directory unchanged
3. **Layered Architecture** - Clear separation: HTTP → API → Business Logic → System Interaction
4. **Stateless APIs** - API endpoints should be stateless where possible; state managed in config/cache
5. **SSH-Based Remote Access** - No agents required; continue using SSH for remote operations
6. **HTML in Static Files** - Enables proper editor syntax highlighting and version control
7. **Hot-Reload Friendly** - Config changes reload without server restart where possible
8. **Testing Ready** - Each module independently importable for unit testing

## Migration Strategy

### Phase 1: Setup
- Create new directory structure
- Copy [main.py](main.py) and [config.py](config.py) from server.py
- Create `__init__.py` files in all subdirectories

### Phase 2: Core Extraction
- Extract stats gathering → [core/stats.py](core/stats.py)
- Extract device cache → [core/device_status.py](core/device_status.py)
- Extract docker logic → [core/docker.py](core/docker.py)
- Extract network scanning → [core/network.py](core/network.py)

### Phase 3: File Ops Extraction
- Extract file operations → [fileops/manager.py](fileops/manager.py)
- Extract folder browsing → [fileops/browser.py](fileops/browser.py)
- Extract SSH file ops → [fileops/ssh.py](fileops/ssh.py)

### Phase 4: API Layer Creation
- Create route handlers in `api/` modules
- Import business logic from `core/` and `fileops/`
- Implement endpoint functions that accept parsed requests

### Phase 5: Web Handler
- Create [web/handler.py](web/handler.py)
- Implement route dispatcher
- Wire up `api/` modules to routes

### Phase 6: Static Assets
- Extract HTML/CSS/JS from HTML_PAGE variable
- Create [static/](static/) files
- Update handler to serve from disk (or embed at build time)

### Phase 7: Entry Point
- Finalize [main.py](main.py)
- Test all imports and initialization
- Verify backward compatibility

### Phase 8: Testing & Cleanup
- Test with existing config files
- Verify all endpoints work identically
- Consider keeping server.py as reference or deprecating it

## Open Questions for Refinement

1. **Static Asset Serving Strategy:**
   - Option A: Load from disk at startup (more flexible, requires file system)
   - Option B: Read at runtime with caching (slower but more dynamic)
   - Option C: Keep embedded in Python as fallback for single-file deployment
   
2. **Module Initialization:**
   - Should each module have its own `__init__()` function called at startup?
   - Should there be a central initialization orchestrator in main.py?
   - How to handle inter-module dependencies (e.g., api/ needs core/ and fileops/)?

3. **Backwards Compatibility:**
   - Should `/opt/deq` directory structure remain identical?
   - Can we create migration scripts for existing installations?
   - Do we need to support running old server.py and new modular version side-by-side?

4. **Error Handling:**
   - Should each module have its own exception types?
   - Common error handling in web/handler.py or per-endpoint?
   - How to log errors across modules?

5. **Configuration Reload:**
   - Should config changes trigger hot-reload without server restart?
   - How to notify all modules of config changes?
   - What's the atomic unit of config (per-device, per-task, global)?

6. **Testing Approach:**
   - Should we create a `tests/` directory with unit tests?
   - Mock strategy for SSH, docker, system commands?
   - Integration tests that test full request → response cycle?

7. **Deployment & Packaging:**
   - Should this support the existing single-file `install.sh` pattern?
   - Need a `requirements.txt` (even if empty)?
   - How to package for distribution (tar.gz, zip, docker)?

8. **State Persistence:**
   - Where should task history, execution logs be stored?
   - Should status cache be persisted across restarts?
   - Database vs JSON files vs in-memory only?

## Benefits of Modularization

| Benefit | Impact |
|---------|--------|
| **Maintainability** | Easier to locate and fix bugs; clearer code organization |
| **Testability** | Individual modules can be unit tested in isolation |
| **Scalability** | New features can be added to specific modules without touching others |
| **Collaboration** | Multiple developers can work on different modules simultaneously |
| **Readability** | Smaller files (~200-400 lines each) vs 7,700 lines in one file |
| **Debugging** | Clearer call stack; easier to trace execution flow |
| **Versioning** | Separate HTML/CSS/JS files enable proper version control diffs |
| **IDE Support** | Better autocomplete, go-to-definition, refactoring tools |
| **Deployment Options** | Can potentially create different deployment targets (containerized, serverless, etc.) |

## Risk Mitigation

- **Testing:** Create comprehensive integration tests before removing server.py
- **Version Control:** Use git branches; keep server.py in repo as reference during transition
- **Documentation:** Document module dependencies and API contracts
- **Rollback Plan:** Ensure config format compatibility so old server.py can still run old configs
- **Gradual Rollout:** Test modular version thoroughly before making it the default
