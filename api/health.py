"""
DeQ API - Health Endpoints
Handles health check and status monitoring API requests.
"""

import time
from typing import Dict, Any, List

from config import get_config, DEFAULT_ALERTS
from core.device_status import get_cached_status, refresh_device_status_async


def get_health_status() -> Dict[str, Any]:
    """
    Get health status for all devices and containers.
    Used for mobile app polling and status overview.
    """
    config = get_config()
    devices: List[Dict[str, Any]] = []
    containers_running = 0
    containers_stopped = 0

    for dev in config.get('devices', []):
        dev_id = dev.get('id')
        cached = get_cached_status(dev_id)
        refresh_device_status_async(dev)

        online = cached.get('online') if cached else None
        stats = cached.get('stats') if cached else None
        container_statuses = cached.get('containers', {}) if cached else {}

        device_alerts = dev.get('alerts', {})
        alerts = {**DEFAULT_ALERTS, **device_alerts}

        # Add container alerts from actual container statuses (all enabled by default)
        if container_statuses:
            default_container_alerts = {name: True for name in container_statuses.keys()}
            user_container_alerts = alerts.get('containers', {})
            alerts['containers'] = {**default_container_alerts, **user_container_alerts}

        device_info: Dict[str, Any] = {
            "id": dev_id,
            "name": dev.get('name', 'Unknown'),
            "online": online,
            "alerts": alerts
        }

        if stats:
            device_info["cpu"] = stats.get("cpu", 0)
            device_info["ram"] = int(
                stats.get("ram_used", 0) / max(stats.get("ram_total", 1), 1) * 100
            )
            device_info["temp"] = stats.get("temp")
            
            # Disk usage - max usage across all disks
            disks = stats.get("disks", [])
            if disks:
                max_disk_usage = max(
                    int(d.get("used", 0) / max(d.get("total", 1), 1) * 100)
                    for d in disks
                )
                device_info["disk"] = max_disk_usage
            
            # SMART status and disk temp
            disk_smart = stats.get("disk_smart", {})
            smart_failed = any(s.get("smart") == "failed" for s in disk_smart.values())
            if smart_failed:
                device_info["smart_failed"] = True
            disk_temps = [s.get("temp") for s in disk_smart.values() if s.get("temp") is not None]
            if disk_temps:
                device_info["disk_temp"] = max(disk_temps)

        # Container statuses for this device
        device_containers: Dict[str, str] = {}
        for name, state in container_statuses.items():
            device_containers[name] = state
            if state == 'running':
                containers_running += 1
            else:
                containers_stopped += 1
        if device_containers:
            device_info["containers"] = device_containers

        devices.append(device_info)

    # Task statuses
    tasks: List[Dict[str, Any]] = []
    for task in config.get('tasks', []):
        if task.get('last_status'):
            tasks.append({
                "id": task.get('id'),
                "name": task.get('name', 'Unknown'),
                "status": task.get('last_status'),
                "error": task.get('last_error'),
                "last_run": task.get('last_run')
            })

    return {
        "devices": devices,
        "containers": {
            "running": containers_running,
            "stopped": containers_stopped
        },
        "tasks": tasks,
        "timestamp": int(time.time())
    }
