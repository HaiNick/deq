"""
DeQ Core - Docker Container Management
Container orchestration, scanning, and status operations.
"""

import subprocess
import re
from typing import Dict, Any, List, Optional


def is_valid_container_name(name: str) -> bool:
    """Validate docker container name to prevent shell injection."""
    if not name or len(name) > 128:
        return False
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$', name))


def docker_action(container: str, action: str) -> Dict[str, Any]:
    """
    Execute docker action on local container.
    Actions: status, start, stop
    """
    if not is_valid_container_name(container):
        return {"success": False, "error": "Invalid container name"}
    
    try:
        if action == "status":
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", container],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                status = result.stdout.strip()
                return {"success": True, "status": status, "running": status == "running"}
            return {"success": False, "error": "Container not found"}
        
        elif action in ["start", "stop"]:
            result = subprocess.run(
                ["docker", action, container],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                return {"success": True}
            return {
                "success": False,
                "error": result.stderr.strip()[:100] if result.stderr else f"docker {action} failed"
            }
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


def remote_docker_action(
    ip: str, user: str, port: int, container: str, action: str, use_sudo: bool = False
) -> Dict[str, Any]:
    """Execute docker command on remote host via SSH."""
    if not is_valid_container_name(container):
        return {"success": False, "error": "Invalid container name"}

    docker_cmd = "sudo docker" if use_sudo else "docker"

    if action == "status":
        ssh_cmd = f"{docker_cmd} inspect -f '{{{{.State.Status}}}}' '{container}'"
    elif action in ("start", "stop"):
        ssh_cmd = f"{docker_cmd} {action} '{container}'"
    else:
        return {"success": False, "error": "Unknown action"}

    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-p", str(port), f"{user}@{ip}", f'bash -lc "{ssh_cmd}"'],
            capture_output=True, text=True, timeout=60
        )

        output = (result.stdout + result.stderr).lower()

        if "permission denied" in output:
            if not use_sudo:
                return remote_docker_action(ip, user, port, container, action, use_sudo=True)
            return {"success": False, "error": "Docker permission denied"}

        if result.returncode == 0:
            if action == "status":
                status = result.stdout.strip()
                return {"success": True, "status": status, "running": status == "running"}
            return {"success": True}

        if action == "status":
            return {"success": False, "error": "Container not found"}
        return {
            "success": False,
            "error": result.stderr.strip()[:100] if result.stderr else f"docker {action} failed"
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SSH timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def scan_docker_containers(device: Dict[str, Any]) -> Dict[str, Any]:
    """Scan for docker containers on device (local or remote)."""
    is_host = device.get('is_host', False)

    if is_host:
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return {"success": False, "error": "Docker not available"}
            names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
            return {"success": True, "containers": names}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Remote device
    ssh_config = device.get('ssh', {})
    user = ssh_config.get('user')
    port = ssh_config.get('port', 22)
    ip = device.get('ip')

    if not user:
        return {"success": False, "error": "SSH not configured. Add SSH user to scan for containers."}

    def try_scan(use_sudo: bool = False):
        docker_cmd = "sudo docker" if use_sudo else "docker"
        ssh_cmd = f'{docker_cmd} ps -a --format "{{{{.Names}}}}"'
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-p", str(port), f"{user}@{ip}", f'bash -lc "{ssh_cmd}"'],
            capture_output=True, text=True, timeout=15
        )
        return result, use_sudo

    try:
        result, used_sudo = try_scan(False)
        output = (result.stdout + result.stderr).lower()
        if result.returncode != 0 or "permission denied" in output:
            if not used_sudo:
                result, used_sudo = try_scan(True)
                output = (result.stdout + result.stderr).lower()

        if result.returncode != 0:
            error = result.stderr.strip() if result.stderr else "Docker not available"
            return {"success": False, "error": error}
        if "permission denied" in output:
            return {
                "success": False,
                "error": "Docker permission denied. Add user to docker group or configure passwordless sudo."
            }
        names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
        return {"success": True, "containers": names}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SSH timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_all_container_statuses(device: Dict[str, Any]) -> Dict[str, str]:
    """Get status of all containers with single docker ps call."""
    containers = device.get('docker', {}).get('containers', [])
    if not containers:
        return {}

    configured_names = set(
        c.get('name') if isinstance(c, dict) else c
        for c in containers
    )

    is_host = device.get('is_host', False)

    if is_host:
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}:{{.State}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return {name: 'unknown' for name in configured_names}
        except Exception:
            return {name: 'unknown' for name in configured_names}
    else:
        ssh_config = device.get('ssh', {})
        user = ssh_config.get('user')
        port = ssh_config.get('port', 22)
        ip = device.get('ip')

        if not user:
            return {name: 'unknown' for name in configured_names}

        try:
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-p", str(port), f"{user}@{ip}",
                 "docker ps -a --format '{{.Names}}:{{.State}}'"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return {name: 'unknown' for name in configured_names}
        except Exception:
            return {name: 'unknown' for name in configured_names}

    all_statuses: Dict[str, str] = {}
    for line in result.stdout.strip().split('\n'):
        if ':' in line:
            name, state = line.split(':', 1)
            all_statuses[name] = state.lower()

    return {
        name: all_statuses.get(name, 'unknown')
        for name in configured_names
    }


def get_container_logs(
    device: Dict[str, Any],
    container: str,
    lines: int = 100,
    since: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get container logs.
    
    Args:
        device: Device configuration dict
        container: Container name
        lines: Number of lines to return (tail)
        since: Only return logs since this time (e.g., "1h", "30m")
        
    Returns:
        {"success": bool, "logs": str, "error": str}
    """
    if not is_valid_container_name(container):
        return {"success": False, "error": "Invalid container name"}
    
    # Build docker logs command args
    cmd_args = ["docker", "logs", "--tail", str(min(lines, 1000))]
    if since:
        # Validate since format (simple check)
        if re.match(r'^\d+[smh]$', since):
            cmd_args.extend(["--since", since])
    cmd_args.append(container)
    
    is_host = device.get('is_host', False)
    
    if is_host:
        try:
            result = subprocess.run(
                cmd_args,
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.strip() or "Failed to get logs"}
            # Docker logs outputs to stderr for some containers
            logs = result.stdout or result.stderr
            return {"success": True, "logs": logs}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout getting logs"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    else:
        # Remote via SSH
        ssh_config = device.get('ssh', {})
        user = ssh_config.get('user')
        port = ssh_config.get('port', 22)
        ip = device.get('ip')
        
        if not user:
            return {"success": False, "error": "SSH not configured"}
        
        # Build SSH command
        docker_cmd = ' '.join(cmd_args)
        try:
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-p", str(port), f"{user}@{ip}", docker_cmd],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr.strip() or "Failed to get logs"}
            logs = result.stdout or result.stderr
            return {"success": True, "logs": logs}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "SSH timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
