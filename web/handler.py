"""
DeQ Web - HTTP Request Handler
Routes incoming HTTP requests to appropriate API handlers.
Includes authentication, security headers, and audit logging.
"""

import json
import re
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any

from config import get_config, save_config, get_config_with_defaults, DATA_DIR
from core.stats import get_local_stats
from core.network import scan_network
from api.devices import (
    get_device_by_id,
    handle_device_status,
    handle_device_stats,
    handle_device_wake,
    handle_device_shutdown,
    handle_docker_action,
    handle_scan_containers,
    handle_ssh_check,
    handle_container_logs
)
from api.files import (
    handle_browse,
    handle_list_files,
    handle_download,
    handle_file_operation,
    handle_upload
)
from api.health import get_health_status
from api.tasks import (
    handle_task_run,
    handle_task_status,
    get_running_tasks,
    calculate_next_run
)
from auth.api_key import validate_request_auth, is_auth_enabled, setup_api_key
from audit.logger import (
    audit_log, access_log, error_log, AuditAction,
    set_request_context, clear_request_context
)
from middleware.security import (
    get_security_headers, get_cors_headers,
    validate_request_size, MAX_REQUEST_SIZE
)


# Version info
VERSION = "0.9.7"

# These will be loaded by main.py and set here
HTML_PAGE = ""
MANIFEST_JSON = ""
ICON_SVG = ""

# Endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    '/api/health',
    '/api/version',
    '/api/auth/setup',  # Initial setup only
}


def set_static_content(html: str, manifest: str, icon: str) -> None:
    """Set static content loaded from files."""
    global HTML_PAGE, MANIFEST_JSON, ICON_SVG
    HTML_PAGE = html
    MANIFEST_JSON = manifest
    ICON_SVG = icon


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for DeQ dashboard."""
    
    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {args[0]}")
    
    def _setup_request_context(self) -> str:
        """Set up request context for logging. Returns request ID."""
        request_id = str(uuid.uuid4())[:8]
        # Get client IP (handle X-Forwarded-For if behind proxy)
        client_ip = self.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if not client_ip:
            client_ip = self.client_address[0] if self.client_address else 'unknown'
        set_request_context(request_id=request_id, source_ip=client_ip)
        return request_id
    
    def _check_auth(self, path: str) -> tuple[bool, str]:
        """
        Check authentication for the request.
        Returns (is_authorized, error_message).
        """
        # Public endpoints don't require auth
        if path in PUBLIC_ENDPOINTS:
            return True, ""
        
        # Static assets don't require auth
        if path in ('/', '/manifest.json', '/icon.svg') or path.startswith('/fonts/'):
            return True, ""
        
        # Check API authentication
        if path.startswith('/api/'):
            headers = {k: v for k, v in self.headers.items()}
            is_valid, error = validate_request_auth(headers)
            if not is_valid:
                audit_log(AuditAction.AUTH_FAILURE, result="failure", details={"error": error, "path": path})
                return False, error
        
        return True, ""
    
    def _add_security_headers(self) -> None:
        """Add security headers to the response."""
        for header, value in get_security_headers().items():
            self.send_header(header, value)
    
    def _add_cors_headers(self) -> None:
        """Add CORS headers to the response."""
        origin = self.headers.get('Origin')
        for header, value in get_cors_headers(origin).items():
            self.send_header(header, value)
    
    def send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """Send JSON response with security headers."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self._add_security_headers()
        self._add_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_html(self, html: str) -> None:
        """Send HTML response with security headers."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(html.encode())
    
    def send_file(self, content, content_type: str, cache: bool = True) -> None:
        """Send file content with optional caching."""
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self._add_security_headers()
        if cache:
            self.send_header('Cache-Control', 'public, max-age=31536000')
        self.end_headers()
        if isinstance(content, str):
            self.wfile.write(content.encode())
        else:
            self.wfile.write(content)

    def send_error_json(self, status: int, error: str) -> None:
        """Send a JSON error response."""
        self.send_json({"success": False, "error": error}, status)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._add_cors_headers()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests."""
        start_time = time.time()
        request_id = self._setup_request_context()
        
        try:
            path = urlparse(self.path).path
            query = parse_qs(urlparse(self.path).query)
            
            # Check authentication
            is_auth, auth_error = self._check_auth(path)
            if not is_auth:
                self.send_error_json(401, auth_error)
                access_log("GET", path, 401, (time.time() - start_time) * 1000)
                return
            
            # Main page
            if path == '/' or path == '':
                config = get_config()
                needs_onboarding = (
                    not config.get('onboarding_done') and 
                    len(config.get('devices', [])) <= 1
                )
                html = HTML_PAGE.replace(
                    '__NEEDS_ONBOARDING__', 
                    'true' if needs_onboarding else 'false'
                )
                self.send_html(html)
                access_log("GET", path, 200, (time.time() - start_time) * 1000)
                return
            
            # Static assets
            if path == '/manifest.json':
                self.send_file(MANIFEST_JSON, 'application/manifest+json')
                access_log("GET", path, 200, (time.time() - start_time) * 1000)
                return
            
            if path == '/icon.svg':
                self.send_file(ICON_SVG, 'image/svg+xml')
                access_log("GET", path, 200, (time.time() - start_time) * 1000)
                return

            if path.startswith('/fonts/'):
                self._handle_font_request(path)
                access_log("GET", path, 200, (time.time() - start_time) * 1000)
                return
            
            # API routes
            if path.startswith('/api/'):
                self._handle_api_get(path, query)
                access_log("GET", path, 200, (time.time() - start_time) * 1000)
                return

            # 404 for everything else
            self.send_response(404)
            self._add_security_headers()
            self.end_headers()
            access_log("GET", path, 404, (time.time() - start_time) * 1000)
            
        except Exception as e:
            error_log(str(e), action="GET", details={"path": self.path})
            self.send_error_json(500, "Internal server error")
            access_log("GET", self.path, 500, (time.time() - start_time) * 1000)
        finally:
            clear_request_context()

    def _handle_font_request(self, path: str) -> None:
        """Handle font file requests."""
        font_name = path.split('/')[-1]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        font_paths = [
            os.path.join(script_dir, '..', 'fonts', font_name),
            f"{DATA_DIR}/fonts/{font_name}"
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                with open(font_path, 'rb') as f:
                    self.send_file(f.read(), 'font/woff2')
                return
        self.send_response(404)
        self.end_headers()

    def _handle_api_get(self, path: str, query: dict) -> None:
        """Route API GET requests."""
        api_path = path[5:].split('?')[0]
        
        # Config endpoint
        if api_path == 'config':
            self.send_json({
                "success": True, 
                "config": get_config_with_defaults(),
                "running_tasks": get_running_tasks(),
                "auth_enabled": is_auth_enabled()
            })
            return
        
        # Host stats
        if api_path == 'stats/host':
            self.send_json({"success": True, "stats": get_local_stats()})
            return

        # Health status
        if api_path == 'health':
            self.send_json(get_health_status())
            return

        # Version info
        if api_path == 'version':
            self.send_json({"version": VERSION, "name": "DeQ"})
            return

        # Auth setup (generate new API key)
        if api_path == 'auth/setup':
            # Only allow if auth is not yet configured
            config = get_config()
            if config.get('auth', {}).get('api_key_hash'):
                self.send_json({"success": False, "error": "Auth already configured"}, 400)
                return
            result = setup_api_key()
            # Store the hash in config
            if 'auth' not in config:
                config['auth'] = {}
            config['auth']['api_key_hash'] = result['api_key_hash']
            config['auth']['enabled'] = True
            save_config(config)
            audit_log(AuditAction.AUTH_KEY_GENERATED, result="success")
            self.send_json({"success": True, "api_key": result['api_key'], "message": result['message']})
            return

        # Network scan
        if api_path == 'network/scan':
            self.send_json(scan_network())
            return

        # Device endpoints
        if api_path.startswith('device/'):
            self._handle_device_api(api_path, query)
            return

        # Task status
        if api_path.startswith('task/') and api_path.endswith('/status'):
            task_id = api_path.split('/')[1]
            self.send_json(handle_task_status(task_id))
            return

        # Notification settings (GET)
        if api_path == 'notifications/settings':
            from api.notifications import handle_get_notification_settings
            self.send_json(handle_get_notification_settings())
            return

        # Not found
        self.send_json({"success": False, "error": "Not found"}, 404)

    def _handle_device_api(self, api_path: str, query: dict) -> None:
        """Route device-related API requests."""
        parts = api_path.split('/')
        if len(parts) < 3:
            self.send_json({"success": False, "error": "Invalid path"}, 400)
            return
            
        dev_id = parts[1]
        action = parts[2]
        
        # Verify device exists
        device = get_device_by_id(dev_id)
        if not device:
            self.send_json({"success": False, "error": "Device not found"}, 404)
            return
        
        # Route to appropriate handler with audit logging
        if action == 'status':
            result = handle_device_status(dev_id)
            audit_log(AuditAction.DEVICE_STATUS, target={"device_id": dev_id})
            self.send_json(result)
        elif action == 'stats':
            self.send_json(handle_device_stats(dev_id))
        elif action == 'wake':
            result = handle_device_wake(dev_id)
            audit_log(AuditAction.DEVICE_WAKE, target={"device_id": dev_id}, 
                     result="success" if result.get("success") else "failure")
            self.send_json(result)
        elif action == 'shutdown':
            result = handle_device_shutdown(dev_id)
            audit_log(AuditAction.DEVICE_SHUTDOWN, target={"device_id": dev_id},
                     result="success" if result.get("success") else "failure")
            self.send_json(result)
        elif action == 'scan-containers':
            self.send_json(handle_scan_containers(dev_id))
        elif action == 'ssh-check':
            self.send_json(handle_ssh_check(dev_id))
        elif action == 'browse':
            browse_path = query.get('path', ['/'])[0]
            result = handle_browse(dev_id, browse_path)
            audit_log(AuditAction.FILE_BROWSE, target={"device_id": dev_id, "path": browse_path})
            self.send_json(result)
        elif action == 'files':
            file_path = query.get('path', ['/'])[0]
            self.send_json(handle_list_files(dev_id, file_path))
        elif action == 'download':
            file_path = query.get('path', [''])[0]
            content, filename, error = handle_download(dev_id, file_path)
            if error:
                self.send_json({"success": False, "error": error}, 400)
            else:
                audit_log(AuditAction.FILE_DOWNLOAD, target={"device_id": dev_id, "path": file_path})
                self._send_file_download(content, filename)
        elif action == 'docker' and len(parts) >= 5:
            container_name = parts[3]
            docker_action = parts[4]
            
            # Handle logs separately (supports query params)
            if docker_action == 'logs':
                lines = int(query.get('lines', ['100'])[0])
                since = query.get('since', [None])[0]
                result = handle_container_logs(dev_id, container_name, lines, since)
                self.send_json(result)
                return
            
            result = handle_docker_action(dev_id, container_name, docker_action)
            # Map docker action to audit action
            docker_audit_map = {
                'start': AuditAction.DOCKER_START,
                'stop': AuditAction.DOCKER_STOP,
                'restart': AuditAction.DOCKER_RESTART,
            }
            if docker_action in docker_audit_map:
                audit_log(docker_audit_map[docker_action], 
                         target={"device_id": dev_id, "container": container_name},
                         result="success" if result.get("success") else "failure")
            self.send_json(result)
        else:
            self.send_json({"success": False, "error": "Unknown action"}, 400)

    def _send_file_download(self, content: bytes, filename: str) -> None:
        """Send file as download attachment."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.send_header('Content-Length', len(content))
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        """Handle POST requests."""
        start_time = time.time()
        request_id = self._setup_request_context()
        
        try:
            path = urlparse(self.path).path
            
            # Check authentication
            is_auth, auth_error = self._check_auth(path)
            if not is_auth:
                self.send_error_json(401, auth_error)
                access_log("POST", path, 401, (time.time() - start_time) * 1000)
                return
            
            # Validate request size
            content_length = int(self.headers.get('Content-Length', 0))
            is_valid_size, size_error = validate_request_size(content_length)
            if not is_valid_size:
                self.send_error_json(413, size_error)
                access_log("POST", path, 413, (time.time() - start_time) * 1000)
                return

            # Config update
            if path == '/api/config':
                self._handle_config_update()
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            # Onboarding complete
            if path == '/api/onboarding/complete':
                config = get_config()
                config['onboarding_done'] = True
                save_config(config)
                self.send_json({"success": True})
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            # Task execution
            if path.startswith('/api/task/') and path.endswith('/run'):
                task_id = path.split('/')[3]
                result = handle_task_run(task_id)
                audit_log(AuditAction.TASK_RUN, target={"task_id": task_id},
                         result="success" if result.get("success") else "failure")
                self.send_json(result)
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            # File operations
            if path.startswith('/api/device/') and path.endswith('/files'):
                self._handle_file_operation(path)
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            # File upload
            if path.startswith('/api/device/') and '/upload' in path:
                self._handle_file_upload(path)
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            # Notification settings update
            if path == '/api/notifications/settings':
                length = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(length))
                from api.notifications import handle_update_notification_settings
                result = handle_update_notification_settings(data)
                audit_log(AuditAction.CONFIG_UPDATE, target={"section": "notifications"}, 
                         result="success" if result.get("success") else "failure")
                self.send_json(result)
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            # Test notification
            if path == '/api/notifications/test':
                length = int(self.headers.get('Content-Length', 0))
                data = json.loads(self.rfile.read(length)) if length > 0 else {}
                from api.notifications import handle_test_notification
                result = handle_test_notification(data)
                self.send_json(result)
                access_log("POST", path, 200, (time.time() - start_time) * 1000)
                return

            self.send_json({"success": False, "error": "Not found"}, 404)
            access_log("POST", path, 404, (time.time() - start_time) * 1000)
            
        except Exception as e:
            error_log(str(e), action="POST", details={"path": self.path})
            self.send_error_json(500, "Internal server error")
            access_log("POST", self.path, 500, (time.time() - start_time) * 1000)
        finally:
            clear_request_context()

    def _handle_config_update(self) -> None:
        """Handle config POST request."""
        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length))
        
        # Update next_run for all enabled tasks
        for task in data.get('tasks', []):
            if task.get('enabled', True):
                task['next_run'] = calculate_next_run(task)
        
        save_config(data)
        audit_log(AuditAction.CONFIG_UPDATE, result="success")
        self.send_json({"success": True})

    def _handle_file_operation(self, path: str) -> None:
        """Handle file operation POST request."""
        parts = path.split('/')
        dev_id = parts[3]
        
        device = get_device_by_id(dev_id)
        if not device:
            self.send_json({"success": False, "error": "Device not found"}, 404)
            return

        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length))
        
        operation = data.get('operation')
        paths = data.get('paths', [])
        dest_device_id = data.get('dest_device')
        dest_path = data.get('dest_path')
        new_name = data.get('new_name')

        result = handle_file_operation(
            dev_id,
            operation,
            paths,
            dest_device_id=dest_device_id,
            dest_path=dest_path,
            new_name=new_name
        )
        
        # Audit log for file operations
        operation_audit_map = {
            'delete': AuditAction.FILE_DELETE,
            'copy': AuditAction.FILE_COPY,
            'move': AuditAction.FILE_MOVE,
            'rename': AuditAction.FILE_RENAME,
            'mkdir': AuditAction.FILE_MKDIR,
            'zip': AuditAction.FILE_ZIP,
        }
        if operation in operation_audit_map:
            audit_log(operation_audit_map[operation],
                     target={"device_id": dev_id, "paths": paths, "dest_path": dest_path},
                     result="success" if result.get("success") else "failure")
        
        self.send_json(result)

    def _handle_file_upload(self, path: str) -> None:
        """Handle file upload POST request."""
        parts = path.split('/')
        dev_id = parts[3]
        
        device = get_device_by_id(dev_id)
        if not device:
            self.send_json({"success": False, "error": "Device not found"}, 404)
            return

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        dest_path = query.get('path', ['/'])[0]

        # Parse multipart form data
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_json({"success": False, "error": "Expected multipart/form-data"}, 400)
            return

        # Extract boundary
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part[9:].strip('"')
                break

        if not boundary:
            self.send_json({"success": False, "error": "No boundary in multipart"}, 400)
            return

        # Parse multipart body
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        files = self._parse_multipart(body, boundary)
        
        result = handle_upload(dev_id, dest_path, files)
        
        # Audit log for uploads
        filenames = [f[0] for f in files]
        audit_log(AuditAction.FILE_UPLOAD,
                 target={"device_id": dev_id, "path": dest_path, "files": filenames},
                 result="success" if result.get("success") else "failure")
        
        self.send_json(result)

    def _parse_multipart(self, body: bytes, boundary: str) -> list:
        """Parse multipart form data and extract files."""
        boundary_bytes = ('--' + boundary).encode()
        parts = body.split(boundary_bytes)
        files = []

        for part in parts:
            if b'Content-Disposition: form-data;' not in part:
                continue
            if b'filename="' not in part:
                continue

            # Extract filename and content
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
            header = part[:header_end].decode('utf-8', errors='ignore')
            content = part[header_end + 4:]

            # Remove trailing \r\n--
            if content.endswith(b'\r\n'):
                content = content[:-2]
            if content.endswith(b'--'):
                content = content[:-2]
            if content.endswith(b'\r\n'):
                content = content[:-2]

            # Get filename from header
            match = re.search(r'filename="([^"]+)"', header)
            if not match:
                continue
            filename = match.group(1)
            files.append((filename, content))

        return files
