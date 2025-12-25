"""
DeQ API - Task Endpoints
Handles task scheduling, execution, and status API requests.
"""

import threading
import subprocess
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set

from config import (
    get_config, save_config, TASK_LOGS_DIR
)
from api.devices import get_device_by_id
from core.docker import docker_action
from utils.subprocess_utils import ping_host


# Track running tasks
_running_tasks: Dict[str, bool] = {}


def get_running_tasks() -> list:
    """Get list of currently running task IDs."""
    return list(_running_tasks.keys())


def is_task_running(task_id: str) -> bool:
    """Check if a task is currently running."""
    return task_id in _running_tasks


def log_task(task_id: str, message: str) -> None:
    """Append a log line to the task's log file."""
    log_file = f"{TASK_LOGS_DIR}/{task_id}.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] {message}\n")


def calculate_next_run(task: Dict[str, Any]) -> Optional[str]:
    """Calculate the next run time for a task based on its schedule."""
    if not task.get('enabled', True):
        return None

    schedule = task.get('schedule', {})
    schedule_type = schedule.get('type', 'daily')
    time_str = schedule.get('time', '03:00')

    try:
        hour, minute = map(int, time_str.split(':'))
    except Exception:
        hour, minute = 3, 0

    now = datetime.now()

    if schedule_type == 'hourly':
        next_run = now.replace(minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(hours=1)

    elif schedule_type == 'daily':
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

    elif schedule_type == 'weekly':
        day = schedule.get('day', 0)  # 0 = Sunday
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Convert to Python weekday (0=Monday)
        py_day = (day - 1) % 7 if day > 0 else 6
        days_ahead = py_day - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and next_run <= now):
            days_ahead += 7
        next_run += timedelta(days=days_ahead)

    elif schedule_type == 'monthly':
        date = schedule.get('date', 1)
        year, month = now.year, now.month
        for _ in range(12):
            try:
                next_run = datetime(year, month, date, hour, minute, 0)
                if next_run > now:
                    break
                month += 1
                if month > 12:
                    month = 1
                    year += 1
            except ValueError:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        else:
            return None
    else:
        return None

    return next_run.isoformat()


def run_task(task_id: str) -> Dict[str, Any]:
    """Start a task in background thread, return immediately."""
    config = get_config()
    task = next((t for t in config.get('tasks', []) if t['id'] == task_id), None)
    
    if not task:
        return {"success": False, "error": "Task not found"}

    if task_id in _running_tasks:
        return {"success": False, "error": "Task already running"}

    # Start in background thread
    _running_tasks[task_id] = True
    thread = threading.Thread(target=_run_task_async, args=(task_id,), daemon=True)
    thread.start()

    return {"success": True, "started": True}


def _run_task_async(task_id: str) -> None:
    """Execute a task in a background thread."""
    config = get_config()
    task = next((t for t in config.get('tasks', []) if t['id'] == task_id), None)
    
    if not task:
        _running_tasks.pop(task_id, None)
        return

    task_type = task.get('type', 'backup')
    log_task(task_id, f"Starting {task_type} task: {task.get('name', 'unnamed')}")

    try:
        if task_type == 'backup':
            result = _run_backup_task(task)
        elif task_type == 'wake':
            result = _run_wake_task(task)
        elif task_type == 'shutdown':
            result = _run_shutdown_task(task)
        else:
            result = {"success": False, "error": f"Unknown task type: {task_type}"}

        # Update task status
        task['last_run'] = datetime.now().isoformat()
        if result.get('success'):
            task['last_status'] = 'success'
            task['last_error'] = None
            if 'size' in result:
                task['last_size'] = result['size']
            log_task(task_id, "Completed successfully")
        elif result.get('skipped'):
            task['last_status'] = 'skipped'
            task['last_error'] = result.get('error', 'source offline')
            log_task(task_id, f"Skipped: {task['last_error']}")
        else:
            task['last_status'] = 'failed'
            task['last_error'] = result.get('error', 'unknown error')
            log_task(task_id, f"Failed: {task['last_error']}")

        save_config(config)

    except Exception as e:
        task['last_run'] = datetime.now().isoformat()
        task['last_status'] = 'failed'
        task['last_error'] = str(e)
        save_config(config)
        log_task(task_id, f"Exception: {e}")

    finally:
        _running_tasks.pop(task_id, None)


def _run_backup_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a backup task using rsync."""
    config = get_config()
    source = task.get('source', {})
    dest = task.get('dest', {})
    options = task.get('options', {})

    source_device = get_device_by_id(source.get('device'))
    dest_device = get_device_by_id(dest.get('device'))

    if not source_device or not dest_device:
        return {"success": False, "error": "Source or destination device not found"}

    source_path = source.get('path', '')
    dest_path = dest.get('path', '')

    if not source_path or not dest_path:
        return {"success": False, "error": "Source or destination path not specified"}

    # Check if source device is online
    source_is_host = source_device.get('is_host', False)
    if not source_is_host:
        if not ping_host(source_device['ip']):
            return {"success": False, "skipped": True, "error": "source offline"}

    # Build rsync command
    rsync_opts = ["-avz", "--stats"]
    if options.get('delete'):
        rsync_opts.append("--delete")

    # Source path
    if source_is_host:
        rsync_source = source_path
    else:
        ssh_user = source_device.get('ssh', {}).get('user', 'root')
        ssh_port = source_device.get('ssh', {}).get('port', 22)
        rsync_opts.extend(["-e", f"ssh -p {ssh_port} -o StrictHostKeyChecking=no -o ConnectTimeout=10"])
        rsync_source = f"{ssh_user}@{source_device['ip']}:{source_path}"

    # Destination path
    dest_is_host = dest_device.get('is_host', False)
    if dest_is_host:
        os.makedirs(dest_path, exist_ok=True)
        rsync_dest = dest_path
    else:
        ssh_user = dest_device.get('ssh', {}).get('user', 'root')
        ssh_port = dest_device.get('ssh', {}).get('port', 22)
        if "-e" not in rsync_opts:
            rsync_opts.extend(["-e", f"ssh -p {ssh_port} -o StrictHostKeyChecking=no -o ConnectTimeout=10"])
        rsync_dest = f"{ssh_user}@{dest_device['ip']}:{dest_path}"

    cmd = ["rsync"] + rsync_opts + [rsync_source, rsync_dest]
    log_task(task['id'], f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if result.returncode == 0:
            size = _parse_rsync_size(result.stdout)
            return {"success": True, "size": size}
        else:
            return {"success": False, "error": result.stderr[:200] if result.stderr else "rsync failed"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout (1h)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_rsync_size(output: str) -> str:
    """Parse total size from rsync stats output."""
    for line in output.split('\n'):
        if 'Total file size' in line and 'transferred' not in line:
            parts = line.split(':')
            if len(parts) > 1:
                size = parts[1].strip().split()[0]
                try:
                    bytes_val = int(size.replace(',', '').replace('.', ''))
                    if bytes_val >= 1e9:
                        return f"{bytes_val/1e9:.1f}GB"
                    elif bytes_val >= 1e6:
                        return f"{bytes_val/1e6:.0f}MB"
                    else:
                        return f"{bytes_val/1e3:.0f}KB"
                except Exception:
                    pass
    return ""


def _run_wake_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a wake task - WOL for device, docker start for container."""
    import socket
    
    target = task.get('target', 'device')

    if target == 'docker':
        container = task.get('container')
        if not container:
            return {"success": False, "error": "No container specified"}
        return docker_action(container, 'start')

    # Device wake (WOL)
    device_id = task.get('device') or task.get('source', {}).get('device')
    device = get_device_by_id(device_id)

    if not device:
        return {"success": False, "error": "Device not found"}

    wol_config = device.get('wol', {})
    if not wol_config.get('mac'):
        return {"success": False, "error": "Device has no WOL configured"}

    mac = wol_config['mac'].replace(":", "").replace("-", "").upper()
    broadcast = wol_config.get('broadcast', '255.255.255.255')
    
    try:
        magic = b'\xff' * 6 + bytes.fromhex(mac) * 16
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (broadcast, 9))
        sock.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_shutdown_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a shutdown task - SSH shutdown for device, docker stop for container."""
    from utils.subprocess_utils import ssh_shutdown, local_shutdown
    
    target = task.get('target', 'device')

    if target == 'docker':
        container = task.get('container')
        if not container:
            return {"success": False, "error": "No container specified"}
        return docker_action(container, 'stop')

    # Device shutdown
    device_id = task.get('device')
    device = get_device_by_id(device_id)

    if not device:
        return {"success": False, "error": "Device not found"}

    if device.get('is_host'):
        return local_shutdown()

    ssh_config = device.get('ssh', {})
    if not ssh_config.get('user'):
        return {"success": False, "error": "Device has no SSH configured"}

    return ssh_shutdown(device['ip'], ssh_config['user'], ssh_config.get('port', 22))


def handle_task_run(task_id: str) -> Dict[str, Any]:
    """Handle POST /api/task/{id}/run - execute task immediately."""
    return run_task(task_id)


def handle_task_status(task_id: str) -> Dict[str, Any]:
    """Handle GET /api/task/{id}/status - get task status."""
    config = get_config()
    task = next((t for t in config.get('tasks', []) if t['id'] == task_id), None)
    
    if not task:
        return {"success": False, "error": "Task not found"}
    
    return {
        "success": True,
        "running": is_task_running(task_id),
        "last_status": task.get('last_status'),
        "last_error": task.get('last_error'),
        "last_size": task.get('last_size')
    }


def handle_task_toggle(task_id: str) -> Dict[str, Any]:
    """Toggle task enabled/disabled state."""
    config = get_config()
    task = next((t for t in config.get('tasks', []) if t['id'] == task_id), None)
    
    if not task:
        return {"success": False, "error": "Task not found"}
    
    task['enabled'] = not task.get('enabled', True)
    if task['enabled']:
        task['next_run'] = calculate_next_run(task)
    else:
        task['next_run'] = None
    
    save_config(config)
    return {"success": True, "enabled": task['enabled']}
