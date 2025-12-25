"""
DeQ Utils - Subprocess Utilities
Safe subprocess execution wrappers and common operations.
"""

import subprocess
import shlex
from typing import Tuple, Optional, List


def ping_host(ip: str, timeout: int = 1) -> bool:
    """
    Ping a host to check if it's online.
    Returns True if host responds, False otherwise.
    """
    # Validate IP to prevent injection
    from utils.validators import is_valid_ip_address
    if not is_valid_ip_address(ip):
        return False
    
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), ip],
            capture_output=True, timeout=timeout + 2
        )
        return result.returncode == 0
    except Exception:
        return False


def run_local_command(cmd: List[str], timeout: int = 300) -> Tuple[bool, str]:
    """
    Run a command locally using an argument list (NO shell=True).
    
    Args:
        cmd: Command as a list of arguments, e.g., ["ls", "-la", "/path"]
        timeout: Command timeout in seconds
        
    Returns:
        (success, stderr) tuple.
    """
    if not cmd or not isinstance(cmd, list):
        return False, "Command must be a non-empty list"
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timeout"
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def run_local_command_output(cmd: List[str], timeout: int = 300) -> Tuple[bool, str, str]:
    """
    Run a command locally and return both stdout and stderr.
    
    Args:
        cmd: Command as a list of arguments
        timeout: Command timeout in seconds
        
    Returns:
        (success, stdout, stderr) tuple.
    """
    if not cmd or not isinstance(cmd, list):
        return False, "", "Command must be a non-empty list"
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timeout"
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return False, "", str(e)


def run_ssh_command(
    ip: str, user: str, port: int, cmd: str, timeout: int = 300
) -> Tuple[bool, str, str]:
    """
    Run a command on remote host via SSH.
    
    Note: cmd is passed as a single string to SSH which executes it in a shell
    on the remote host. For security, validate inputs before constructing cmd.
    
    Returns:
        (success, stdout, stderr) tuple.
    """
    # Validate inputs
    from utils.validators import is_valid_ip_address, is_valid_ssh_user, is_valid_port
    if not is_valid_ip_address(ip):
        return False, "", "Invalid IP address"
    if not is_valid_ssh_user(user):
        return False, "", "Invalid SSH username"
    if not is_valid_port(port):
        return False, "", "Invalid port number"
    
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-p", str(port), f"{user}@{ip}", cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "SSH timeout"
    except Exception as e:
        return False, "", str(e)


def check_ssh_access(ip: str, user: str, port: int = 22) -> bool:
    """
    Check if SSH access is available to a host.
    Returns True if SSH connection succeeds, False otherwise.
    """
    # Validate inputs
    from utils.validators import is_valid_ip_address, is_valid_ssh_user, is_valid_port
    if not is_valid_ip_address(ip):
        return False
    if not is_valid_ssh_user(user):
        return False
    if not is_valid_port(port):
        return False
    
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-o", "BatchMode=yes", "-p", str(port), f"{user}@{ip}", "echo", "ok"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and 'ok' in result.stdout
    except Exception:
        return False


def ssh_shutdown(ip: str, user: str, port: int = 22) -> dict:
    """
    Shutdown a remote host via SSH.
    Returns success/error dict.
    """
    # Validate inputs
    from utils.validators import is_valid_ip_address, is_valid_ssh_user, is_valid_port
    if not is_valid_ip_address(ip):
        return {"success": False, "error": "Invalid IP address"}
    if not is_valid_ssh_user(user):
        return {"success": False, "error": "Invalid SSH username"}
    if not is_valid_port(port):
        return {"success": False, "error": "Invalid port number"}
    
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-p", str(port), f"{user}@{ip}", "sudo", "shutdown", "-h", "now"],
            capture_output=True, text=True, timeout=30
        )
        return {"success": True}
    except subprocess.TimeoutExpired:
        # Expected - shutdown kills connection
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def local_shutdown() -> dict:
    """
    Shutdown the local host.
    Returns success/error dict.
    """
    try:
        subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
