"""
DeQ Utils - Input Validators
Validation functions for user input to prevent injection and ensure data integrity.
"""

import os
import re
from typing import Optional, List, Tuple

# === ALLOWED PATH ROOTS ===
# Paths outside these roots are rejected for security
# Can be extended via config for per-device allowed paths
DEFAULT_ALLOWED_ROOTS = [
    "/home",
    "/mnt",
    "/opt/deq/uploads",
    "/media",
    "/srv",
    "/var/log",
    "/tmp",
    "/root",
]


def is_valid_container_name(name: str) -> bool:
    """
    Validate docker container name to prevent shell injection.
    Container names must:
    - Be 1-128 characters
    - Start with alphanumeric
    - Contain only alphanumeric, underscore, period, or hyphen
    """
    if not name or len(name) > 128:
        return False
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$', name))


def is_valid_device_id(device_id: str) -> bool:
    """
    Validate device ID format.
    Should be a UUID or simple alphanumeric identifier.
    """
    if not device_id or len(device_id) > 64:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', device_id))


def is_valid_path(path: str, allowed_roots: Optional[List[str]] = None) -> bool:
    """
    Validate file/folder path with strict traversal protection.
    
    Args:
        path: The path to validate
        allowed_roots: List of allowed root directories (uses DEFAULT_ALLOWED_ROOTS if None)
        
    Returns:
        True if path is valid and within allowed roots
    """
    if not path:
        return False
    
    # Check for null bytes (can bypass string termination)
    if '\x00' in path:
        return False
    
    # Must be absolute path
    if not path.startswith('/'):
        return False
    
    # Normalize and resolve the path
    try:
        # os.path.normpath collapses ../ sequences
        normalized = os.path.normpath(path)
    except Exception:
        return False
    
    # Check for traversal attempts after normalization
    # Path should still start with / and not escape intended directory
    if not normalized.startswith('/'):
        return False
    
    # Use provided roots or defaults
    roots = allowed_roots if allowed_roots is not None else DEFAULT_ALLOWED_ROOTS
    
    # Allow root directory access for browsing
    if normalized == '/':
        return True
    
    # Check if path is within any allowed root
    for root in roots:
        norm_root = os.path.normpath(root)
        if normalized == norm_root or normalized.startswith(norm_root + '/'):
            return True
    
    return False


def validate_path_secure(path: str, allowed_roots: Optional[List[str]] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Validate and normalize a path with detailed error messages.
    
    Args:
        path: The path to validate
        allowed_roots: List of allowed root directories
        
    Returns:
        (is_valid, normalized_path, error_message)
    """
    if not path:
        return False, "", "Path is required"
    
    if '\x00' in path:
        return False, "", "Invalid characters in path"
    
    if not path.startswith('/'):
        return False, "", "Path must be absolute"
    
    try:
        normalized = os.path.normpath(path)
    except Exception:
        return False, "", "Invalid path format"
    
    roots = allowed_roots if allowed_roots is not None else DEFAULT_ALLOWED_ROOTS
    
    if normalized == '/':
        return True, normalized, None
    
    for root in roots:
        norm_root = os.path.normpath(root)
        if normalized == norm_root or normalized.startswith(norm_root + '/'):
            return True, normalized, None
    
    return False, "", f"Path not within allowed directories"


def is_valid_folder_name(name: str) -> bool:
    """
    Validate folder name for creation.
    Must not contain path separators or null bytes.
    """
    if not name:
        return False
    if '/' in name or '\\' in name or '\x00' in name:
        return False
    if name in ('.', '..'):
        return False
    # Prevent hidden files/folders unless explicitly allowed
    if name.startswith('.') and len(name) > 1:
        # Allow hidden folders but not .. or single .
        pass
    return bool(re.match(r'^[a-zA-Z0-9._-][a-zA-Z0-9._\- ]*$', name))


def is_valid_filename(name: str) -> bool:
    """
    Validate filename for uploads/creation.
    Prevents shell metacharacters and traversal.
    """
    if not name:
        return False
    if '/' in name or '\\' in name or '\x00' in name:
        return False
    if name in ('.', '..'):
        return False
    # Allow common filename characters
    # Reject shell metacharacters: ; ` $ | & < > etc.
    dangerous_chars = set(';`$|&<>(){}[]!#')
    if any(c in name for c in dangerous_chars):
        return False
    return True


def is_valid_ip_address(ip: str) -> bool:
    """Validate IPv4 address format."""
    if not ip:
        return False
    # Allow localhost
    if ip == 'localhost':
        return True
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(part) <= 255 for part in parts)
    except ValueError:
        return False


def is_valid_mac_address(mac: str) -> bool:
    """Validate MAC address format."""
    if not mac:
        return False
    # Accept various formats: AA:BB:CC:DD:EE:FF, AA-BB-CC-DD-EE-FF, AABBCCDDEEFF
    mac_clean = mac.replace(':', '').replace('-', '').upper()
    if len(mac_clean) != 12:
        return False
    return bool(re.match(r'^[0-9A-F]{12}$', mac_clean))


def is_valid_port(port: int) -> bool:
    """Validate port number."""
    return isinstance(port, int) and 1 <= port <= 65535


def is_valid_ssh_user(user: str) -> bool:
    """Validate SSH username."""
    if not user or len(user) > 32:
        return False
    # Standard Unix username validation
    return bool(re.match(r'^[a-z_][a-z0-9_-]*$', user.lower()))


def sanitize_path(path: str) -> str:
    """
    Sanitize a file path for shell commands.
    Escapes single quotes for safe use in shell strings.
    
    WARNING: Prefer using subprocess with lists instead of shell=True.
    This is a fallback for unavoidable shell command construction.
    """
    return path.replace("'", "'\\''")


def normalize_path(path: str) -> str:
    """
    Normalize a path by removing trailing slashes and handling root.
    Also collapses ../ sequences safely.
    """
    if not path:
        return '/'
    normalized = os.path.normpath(path)
    return normalized if normalized != '.' else '/'
