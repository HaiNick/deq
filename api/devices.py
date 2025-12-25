"""
DeQ API - Device Endpoints
Handles device-related API requests: status, stats, wake, shutdown, docker.
"""

from typing import Dict, Any, Optional

from config import get_config, save_config, DEFAULT_ALERTS
from core.stats import get_local_stats, get_remote_stats
from core.device_status import (
    get_cached_status, refresh_device_status_async
)
from core.docker import (
    docker_action, remote_docker_action, scan_docker_containers,
    is_valid_container_name, get_container_logs
)
from utils.subprocess_utils import (
    ping_host, ssh_shutdown, local_shutdown, check_ssh_access
)


def get_device_by_id(device_id: str) -> Optional[Dict[str, Any]]:
    """Get device by ID from config."""
    config = get_config()
    return next((d for d in config.get('devices', []) if d['id'] == device_id), None)


def handle_device_status(device_id: str) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/status - get cached status and trigger refresh."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    cached = get_cached_status(device_id)
    refresh_device_status_async(device)
    
    if cached:
        return {"success": True, **cached}
    return {"success": True, "online": None, "stats": None, "containers": {}}


def handle_device_stats(device_id: str) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/stats - get fresh stats."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    if device.get('is_host'):
        stats = get_local_stats()
        online = True
    else:
        online = ping_host(device.get('ip', ''))
        ssh = device.get('ssh', {})
        if online and ssh.get('user'):
            stats = get_remote_stats(device['ip'], ssh['user'], ssh.get('port', 22))
        else:
            stats = None
    
    return {"success": True, "stats": stats or {}, "online": online}


def handle_device_wake(device_id: str) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/wake - send Wake-on-LAN packet."""
    import socket
    
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    wol_config = device.get('wol', {})
    mac = wol_config.get('mac')
    
    if not mac:
        return {"success": False, "error": "WOL not configured"}
    
    broadcast = wol_config.get('broadcast', '255.255.255.255')
    
    try:
        mac = mac.replace(":", "").replace("-", "").upper()
        if len(mac) != 12:
            return {"success": False, "error": "Invalid MAC address"}
        magic = b'\xff' * 6 + bytes.fromhex(mac) * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (broadcast, 9))
        sock.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def handle_device_shutdown(device_id: str) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/shutdown - shutdown device."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    if device.get('is_host'):
        return local_shutdown()
    
    ssh_config = device.get('ssh', {})
    if not ssh_config.get('user'):
        return {"success": False, "error": "SSH not configured"}
    
    return ssh_shutdown(
        device['ip'],
        ssh_config['user'],
        ssh_config.get('port', 22)
    )


def handle_docker_action(
    device_id: str, container_name: str, action: str
) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/docker/{container}/{action}."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    if not is_valid_container_name(container_name):
        return {"success": False, "error": "Invalid container name"}
    
    # Verify container is configured for this device
    containers = device.get('docker', {}).get('containers', [])
    container_names = [
        c.get('name') if isinstance(c, dict) else c
        for c in containers
    ]
    
    if container_name not in container_names:
        return {"success": False, "error": f"Container '{container_name}' not configured"}
    
    if device.get('is_host'):
        return docker_action(container_name, action)
    else:
        ssh_config = device.get('ssh', {})
        if not ssh_config.get('user'):
            return {"success": False, "error": "SSH not configured"}
        
        return remote_docker_action(
            device['ip'],
            ssh_config['user'],
            ssh_config.get('port', 22),
            container_name,
            action
        )


def handle_scan_containers(device_id: str) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/scan-containers."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    return scan_docker_containers(device)


def handle_ssh_check(device_id: str) -> Dict[str, Any]:
    """Handle GET /api/device/{id}/ssh-check - verify SSH access."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    ssh_config = device.get('ssh', {})
    if not ssh_config.get('user'):
        return {"success": False, "error": "No SSH user configured"}
    
    if check_ssh_access(device['ip'], ssh_config['user'], ssh_config.get('port', 22)):
        return {"success": True}
    return {"success": False, "error": "SSH auth failed"}


def handle_container_logs(
    device_id: str,
    container_name: str,
    lines: int = 100,
    since: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle GET /api/device/{id}/docker/{container}/logs
    Returns container logs.
    """
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    if not is_valid_container_name(container_name):
        return {"success": False, "error": "Invalid container name"}
    
    # Verify container is configured for this device
    containers = device.get('docker', {}).get('containers', [])
    container_names = [
        c.get('name') if isinstance(c, dict) else c
        for c in containers
    ]
    
    if container_name not in container_names:
        return {"success": False, "error": f"Container '{container_name}' not configured"}
    
    return get_container_logs(device, container_name, lines, since)
