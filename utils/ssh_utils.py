"""
DeQ Utils - SSH Utilities
SSH connection helpers and remote execution utilities.
"""

import subprocess
from typing import Dict, Any, Tuple, Optional


def build_ssh_base(ip: str, user: str, port: int = 22) -> list:
    """Build base SSH command arguments."""
    return [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
        "-p", str(port), f"{user}@{ip}"
    ]


def run_remote_command(
    ip: str, user: str, port: int, command: str, timeout: int = 30
) -> Tuple[bool, str, str]:
    """
    Execute a command on remote host via SSH.
    Returns (success, stdout, stderr).
    """
    ssh_base = build_ssh_base(ip, user, port)
    try:
        result = subprocess.run(
            ssh_base + [command],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "SSH timeout"
    except Exception as e:
        return False, "", str(e)


def run_remote_script(
    ip: str, user: str, port: int, script: str, timeout: int = 60
) -> Tuple[bool, str, str]:
    """
    Execute a multi-line script on remote host via SSH.
    Returns (success, stdout, stderr).
    """
    ssh_base = build_ssh_base(ip, user, port)
    try:
        result = subprocess.run(
            ssh_base + [f'bash -c "{script}"'],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "SSH timeout"
    except Exception as e:
        return False, "", str(e)


def scp_upload(
    local_path: str, remote_path: str, ip: str, user: str, port: int = 22,
    timeout: int = 600
) -> Dict[str, Any]:
    """
    Upload a file to remote host via SCP.
    Returns success/error dict.
    """
    try:
        result = subprocess.run(
            ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port),
             local_path, f"{user}@{ip}:{remote_path}"],
            capture_output=True, timeout=timeout
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.decode().strip() or "SCP failed"}
        return {"success": True}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SCP timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def scp_download(
    remote_path: str, local_path: str, ip: str, user: str, port: int = 22,
    timeout: int = 600
) -> Dict[str, Any]:
    """
    Download a file from remote host via SCP.
    Returns success/error dict.
    """
    try:
        result = subprocess.run(
            ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port),
             f"{user}@{ip}:{remote_path}", local_path],
            capture_output=True, timeout=timeout
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.decode().strip() or "SCP failed"}
        return {"success": True}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SCP timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_remote_path_exists(
    ip: str, user: str, port: int, path: str, is_dir: bool = True
) -> bool:
    """Check if a path exists on remote host."""
    flag = "-d" if is_dir else "-e"
    cmd = f"test {flag} '{path}' && echo 'exists' || echo 'notfound'"
    success, stdout, _ = run_remote_command(ip, user, port, cmd, timeout=10)
    return success and "exists" in stdout
