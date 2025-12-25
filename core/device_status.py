"""
DeQ Core - Device Status Cache
Thread-safe caching and async refresh of device status.
Includes health monitoring with notification alerts.
"""

import threading
from typing import Dict, Any, Optional, Set

from core.stats import get_local_stats, get_remote_stats
from core.docker import get_all_container_statuses
from utils.subprocess_utils import ping_host


# === DEVICE STATUS CACHE ===
_device_status_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()
_refresh_in_progress: Set[str] = set()

# Track previous states for change detection
_previous_online_state: Dict[str, bool] = {}
_previous_container_states: Dict[str, Dict[str, str]] = {}  # device_id -> {container: state}


def get_cached_status(device_id: str) -> Optional[Dict[str, Any]]:
    """Get cached status for a device, or None if not cached."""
    with _cache_lock:
        return _device_status_cache.get(device_id)


def set_cached_status(device_id: str, status: Dict[str, Any]) -> None:
    """Set cached status for a device."""
    with _cache_lock:
        _device_status_cache[device_id] = status


def clear_cached_status(device_id: str) -> None:
    """Clear cached status for a device."""
    with _cache_lock:
        _device_status_cache.pop(device_id, None)


def refresh_device_status_async(device: Dict[str, Any]) -> None:
    """
    Start async refresh of device status in background thread.
    Skips if refresh already in progress for this device.
    Also checks for state changes and sends notifications.
    """
    dev_id = device.get('id')
    if dev_id in _refresh_in_progress:
        return
    
    _refresh_in_progress.add(dev_id)

    def do_refresh():
        try:
            # Get container statuses
            container_statuses = get_all_container_statuses(device)
            
            if device.get('is_host'):
                # Local device
                stats = get_local_stats()
                status = {
                    "online": True,
                    "stats": stats,
                    "containers": container_statuses
                }
            else:
                # Remote device
                online = ping_host(device.get('ip', ''))
                stats = None
                if online and device.get('ssh', {}).get('user'):
                    stats = get_remote_stats(
                        device['ip'],
                        device['ssh']['user'],
                        device['ssh'].get('port', 22)
                    )
                status = {
                    "online": online,
                    "stats": stats,
                    "containers": container_statuses
                }
            
            # Check for state changes and send notifications
            _check_and_notify_changes(device, status)
            
            set_cached_status(dev_id, status)
        finally:
            _refresh_in_progress.discard(dev_id)

    thread = threading.Thread(target=do_refresh, daemon=True)
    thread.start()


def _check_and_notify_changes(device: Dict[str, Any], new_status: Dict[str, Any]) -> None:
    """
    Check for state changes and send notifications if enabled.
    Compares new status against previous state to detect:
    - Device going offline/online
    - Containers stopping unexpectedly
    - High resource usage
    """
    dev_id = device.get('id')
    dev_name = device.get('name', dev_id)
    alerts_config = device.get('alerts', {})
    
    # Check online/offline state change (only for non-host devices)
    if not device.get('is_host'):
        new_online = new_status.get('online', False)
        prev_online = _previous_online_state.get(dev_id)
        
        # Only notify if we have a previous state (not first check)
        if prev_online is not None and prev_online != new_online:
            if alerts_config.get('online', True):
                try:
                    from notifications.manager import notify_device_offline, notify_device_online
                    if new_online:
                        notify_device_online(dev_id, dev_name)
                    else:
                        notify_device_offline(dev_id, dev_name)
                except ImportError:
                    pass  # Notifications module not available
        
        _previous_online_state[dev_id] = new_online
    
    # Check container state changes
    new_containers = new_status.get('containers', {})
    prev_containers = _previous_container_states.get(dev_id, {})
    
    for container_name, container_info in new_containers.items():
        new_state = container_info.get('status', 'unknown') if isinstance(container_info, dict) else str(container_info)
        prev_state = prev_containers.get(container_name)
        
        # Container stopped (was running, now not running)
        if prev_state == 'running' and new_state != 'running':
            try:
                from notifications.manager import notify_container_stopped
                notify_container_stopped(dev_id, dev_name, container_name)
            except ImportError:
                pass
    
    # Update previous container states
    _previous_container_states[dev_id] = {
        name: (info.get('status', 'unknown') if isinstance(info, dict) else str(info))
        for name, info in new_containers.items()
    }
    
    # Check resource thresholds
    stats = new_status.get('stats')
    if stats and new_status.get('online', True):
        _check_resource_thresholds(device, stats, alerts_config)


def _check_resource_thresholds(
    device: Dict[str, Any],
    stats: Dict[str, Any],
    alerts_config: Dict[str, Any]
) -> None:
    """Check resource usage against configured thresholds."""
    dev_id = device.get('id')
    dev_name = device.get('name', dev_id)
    
    # CPU threshold
    cpu_threshold = alerts_config.get('cpu', 90)
    cpu_usage = stats.get('cpu')
    if cpu_usage is not None and cpu_usage > cpu_threshold:
        try:
            from notifications.manager import notify_high_resource_usage
            notify_high_resource_usage(dev_id, dev_name, "CPU", cpu_usage, cpu_threshold)
        except ImportError:
            pass
    
    # RAM threshold
    ram_threshold = alerts_config.get('ram', 90)
    ram_usage = stats.get('mem')
    if ram_usage is not None and ram_usage > ram_threshold:
        try:
            from notifications.manager import notify_high_resource_usage
            notify_high_resource_usage(dev_id, dev_name, "RAM", ram_usage, ram_threshold)
        except ImportError:
            pass
    
    # Disk threshold
    disk_threshold = alerts_config.get('disk_usage', 90)
    disk_usage = stats.get('disk')
    if disk_usage is not None and disk_usage > disk_threshold:
        try:
            from notifications.manager import notify_high_resource_usage
            notify_high_resource_usage(dev_id, dev_name, "Disk", disk_usage, disk_threshold)
        except ImportError:
            pass
    
    # Temperature threshold
    temp_threshold = alerts_config.get('cpu_temp', 80)
    temp = stats.get('temp')
    if temp is not None and temp > temp_threshold:
        try:
            from notifications.manager import notify_high_resource_usage
            notify_high_resource_usage(dev_id, dev_name, "Temperature", temp, temp_threshold)
        except ImportError:
            pass


def get_all_device_statuses() -> Dict[str, Dict[str, Any]]:
    """Get cached status for all devices."""
    with _cache_lock:
        return _device_status_cache.copy()


def is_refresh_in_progress(device_id: str) -> bool:
    """Check if refresh is in progress for a device."""
    return device_id in _refresh_in_progress
