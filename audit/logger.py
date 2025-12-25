"""
DeQ Audit - Structured Audit Logger
JSON-formatted audit logs for all security-relevant actions.
"""

import json
import os
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from config import DATA_DIR

# Audit log configuration
AUDIT_LOG_DIR = f"{DATA_DIR}/logs"
AUDIT_LOG_FILE = f"{AUDIT_LOG_DIR}/audit.log"
ACCESS_LOG_FILE = f"{AUDIT_LOG_DIR}/access.log"
ERROR_LOG_FILE = f"{AUDIT_LOG_DIR}/error.log"

# Max log file size before rotation (10MB)
MAX_LOG_SIZE = 10 * 1024 * 1024

# Thread-local storage for request context
_request_context = threading.local()


class AuditAction(str, Enum):
    """Audit action categories."""
    # Authentication
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    AUTH_KEY_GENERATED = "auth.key_generated"
    
    # Device actions
    DEVICE_WAKE = "device.wake"
    DEVICE_SHUTDOWN = "device.shutdown"
    DEVICE_REBOOT = "device.reboot"
    DEVICE_STATUS = "device.status"
    
    # Docker actions
    DOCKER_START = "docker.start"
    DOCKER_STOP = "docker.stop"
    DOCKER_RESTART = "docker.restart"
    DOCKER_EXEC = "docker.exec"
    
    # File operations
    FILE_BROWSE = "file.browse"
    FILE_DOWNLOAD = "file.download"
    FILE_UPLOAD = "file.upload"
    FILE_DELETE = "file.delete"
    FILE_COPY = "file.copy"
    FILE_MOVE = "file.move"
    FILE_RENAME = "file.rename"
    FILE_MKDIR = "file.mkdir"
    FILE_ZIP = "file.zip"
    
    # Config changes
    CONFIG_UPDATE = "config.update"
    CONFIG_DEVICE_ADD = "config.device_add"
    CONFIG_DEVICE_REMOVE = "config.device_remove"
    CONFIG_TASK_ADD = "config.task_add"
    CONFIG_TASK_REMOVE = "config.task_remove"
    
    # Task execution
    TASK_RUN = "task.run"
    TASK_COMPLETE = "task.complete"
    TASK_FAILED = "task.failed"
    
    # System
    SERVER_START = "server.start"
    SERVER_STOP = "server.stop"


def ensure_log_dirs() -> None:
    """Create log directories if they don't exist."""
    os.makedirs(AUDIT_LOG_DIR, exist_ok=True)


def get_request_id() -> str:
    """Get the current request ID, or generate a new one."""
    if hasattr(_request_context, 'request_id') and _request_context.request_id:
        return _request_context.request_id
    return str(uuid.uuid4())[:8]


def set_request_context(
    request_id: Optional[str] = None,
    source_ip: Optional[str] = None,
    user: Optional[str] = None
) -> None:
    """Set thread-local request context for audit logging."""
    _request_context.request_id = request_id or str(uuid.uuid4())[:8]
    _request_context.source_ip = source_ip
    _request_context.user = user


def clear_request_context() -> None:
    """Clear thread-local request context."""
    _request_context.request_id = None
    _request_context.source_ip = None
    _request_context.user = None


def _get_context() -> Dict[str, Any]:
    """Get current request context."""
    return {
        "request_id": getattr(_request_context, 'request_id', None),
        "source_ip": getattr(_request_context, 'source_ip', None),
        "user": getattr(_request_context, 'user', 'anonymous')
    }


def _rotate_log_if_needed(log_path: str) -> None:
    """Rotate log file if it exceeds max size."""
    if not os.path.exists(log_path):
        return
    
    try:
        if os.path.getsize(log_path) > MAX_LOG_SIZE:
            # Rotate: rename current to .1, delete old .1
            rotated_path = f"{log_path}.1"
            if os.path.exists(rotated_path):
                os.remove(rotated_path)
            os.rename(log_path, rotated_path)
    except Exception:
        pass  # Don't fail on rotation errors


def _write_log(log_path: str, entry: Dict[str, Any]) -> None:
    """Write a log entry to file."""
    ensure_log_dirs()
    _rotate_log_if_needed(log_path)
    
    try:
        with open(log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception as e:
        # Fallback to stderr if file write fails
        import sys
        print(f"[AUDIT ERROR] Failed to write log: {e}", file=sys.stderr)
        print(f"[AUDIT] {json.dumps(entry)}", file=sys.stderr)


def audit_log(
    action: AuditAction,
    target: Optional[Dict[str, Any]] = None,
    result: str = "success",
    details: Optional[Dict[str, Any]] = None,
    level: str = "INFO"
) -> None:
    """
    Write an audit log entry.
    
    Args:
        action: The action being audited (from AuditAction enum)
        target: Target of the action (device_id, file_path, etc.)
        result: "success" or "failure"
        details: Additional details about the action
        level: Log level (INFO, WARN, ERROR)
    """
    context = _get_context()
    
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "action": action.value if isinstance(action, AuditAction) else str(action),
        "user": context.get("user", "anonymous"),
        "source_ip": context.get("source_ip"),
        "target": target,
        "result": result,
        "request_id": context.get("request_id"),
        "details": details
    }
    
    # Remove None values for cleaner logs
    entry = {k: v for k, v in entry.items() if v is not None}
    
    _write_log(AUDIT_LOG_FILE, entry)


def access_log(
    method: str,
    path: str,
    status: int,
    duration_ms: Optional[float] = None
) -> None:
    """
    Write an access log entry for HTTP requests.
    """
    context = _get_context()
    
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "method": method,
        "path": path,
        "status": status,
        "source_ip": context.get("source_ip"),
        "request_id": context.get("request_id"),
        "duration_ms": duration_ms
    }
    
    entry = {k: v for k, v in entry.items() if v is not None}
    _write_log(ACCESS_LOG_FILE, entry)


def error_log(
    error: str,
    action: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Write an error log entry.
    """
    context = _get_context()
    
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "ERROR",
        "error": error,
        "action": action,
        "source_ip": context.get("source_ip"),
        "request_id": context.get("request_id"),
        "details": details
    }
    
    entry = {k: v for k, v in entry.items() if v is not None}
    _write_log(ERROR_LOG_FILE, entry)
