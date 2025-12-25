"""
DeQ FileOps - SSH File Operations
Remote file operations via SSH.
"""

import subprocess
from typing import Dict, Any, Optional

from utils.ssh_utils import run_remote_command, check_remote_path_exists


def remote_file_exists(ip: str, user: str, port: int, path: str) -> bool:
    """Check if a file exists on remote host."""
    return check_remote_path_exists(ip, user, port, path, is_dir=False)


def remote_dir_exists(ip: str, user: str, port: int, path: str) -> bool:
    """Check if a directory exists on remote host."""
    return check_remote_path_exists(ip, user, port, path, is_dir=True)


def remote_read_file(ip: str, user: str, port: int, path: str) -> tuple:
    """
    Read file content from remote host.
    Returns (content_bytes, error_string).
    """
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-p", str(port),
             f"{user}@{ip}", f"cat '{path}'"],
            capture_output=True, timeout=60
        )
        if result.returncode != 0:
            return None, result.stderr.decode().strip() or "Failed to read file"
        return result.stdout, None
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def remote_write_file(
    ip: str, user: str, port: int, path: str, content: bytes
) -> Dict[str, Any]:
    """
    Write file content to remote host.
    Uses SCP for file transfer.
    """
    import tempfile
    import os
    
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port),
                 tmp_path, f"{user}@{ip}:{path}"],
                capture_output=True, timeout=600
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.decode().strip() or "SCP failed"}
            return {"success": True}
        finally:
            os.unlink(tmp_path)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def remote_mkdir(ip: str, user: str, port: int, path: str) -> Dict[str, Any]:
    """Create directory on remote host."""
    success, stdout, stderr = run_remote_command(ip, user, port, f"mkdir -p '{path}'")
    if success:
        return {"success": True}
    return {"success": False, "error": stderr}


def remote_delete(ip: str, user: str, port: int, path: str) -> Dict[str, Any]:
    """Delete file or directory on remote host."""
    success, stdout, stderr = run_remote_command(ip, user, port, f"rm -rf '{path}'")
    if success:
        return {"success": True}
    return {"success": False, "error": stderr}


def remote_move(
    ip: str, user: str, port: int, src: str, dest: str
) -> Dict[str, Any]:
    """Move/rename file on remote host."""
    success, stdout, stderr = run_remote_command(ip, user, port, f"mv '{src}' '{dest}'")
    if success:
        return {"success": True}
    return {"success": False, "error": stderr}


def remote_copy(
    ip: str, user: str, port: int, src: str, dest: str
) -> Dict[str, Any]:
    """Copy file on remote host."""
    success, stdout, stderr = run_remote_command(ip, user, port, f"cp -r '{src}' '{dest}'")
    if success:
        return {"success": True}
    return {"success": False, "error": stderr}


def remote_get_file_size(ip: str, user: str, port: int, path: str) -> Optional[int]:
    """Get file size on remote host."""
    success, stdout, stderr = run_remote_command(ip, user, port, f"stat -c%s '{path}' 2>/dev/null")
    if success and stdout.strip().isdigit():
        return int(stdout.strip())
    return None
