"""
DeQ FileOps - Folder Browser
Directory listing for local and remote systems.
"""

import subprocess
import os
from typing import Dict, Any, List

from utils.validators import normalize_path


def browse_folder(device: Dict[str, Any], path: str = "/") -> Dict[str, Any]:
    """
    List folders in a directory on a device (local or remote via SSH).
    Returns only directories, excludes hidden folders.
    """
    try:
        path = normalize_path(path)

        if device.get('is_host'):
            # Local browsing
            if not os.path.isdir(path):
                return {"success": False, "error": f"Not a directory: {path}"}

            folders: List[str] = []
            try:
                for entry in os.listdir(path):
                    full_path = os.path.join(path, entry)
                    if os.path.isdir(full_path) and not entry.startswith('.'):
                        folders.append(entry)
            except PermissionError:
                return {"success": False, "error": "Permission denied"}

            folders.sort(key=str.lower)
            return {"success": True, "path": path, "folders": folders}

        else:
            # Remote browsing via SSH
            ssh_config = device.get('ssh', {})
            user = ssh_config.get('user')
            port = ssh_config.get('port', 22)
            ip = device.get('ip')

            if not user:
                return {"success": False, "error": "SSH not configured for this device"}

            # Use find to list only directories, exclude hidden
            cmd = f"find '{path}' -maxdepth 1 -mindepth 1 -type d ! -name '.*' -printf '%f\\n' 2>/dev/null | sort -f"
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-p", str(port), f"{user}@{ip}", cmd],
                capture_output=True, text=True, timeout=15
            )

            if result.returncode != 0 and not result.stdout:
                # Check if path exists
                check_cmd = f"test -d '{path}' && echo 'exists' || echo 'notfound'"
                check_result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                     "-p", str(port), f"{user}@{ip}", check_cmd],
                    capture_output=True, text=True, timeout=10
                )
                if "notfound" in check_result.stdout:
                    return {"success": False, "error": f"Path not found: {path}"}
                return {"success": False, "error": "Permission denied or SSH error"}

            folders = [f for f in result.stdout.strip().split('\n') if f]
            return {"success": True, "path": path, "folders": folders}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SSH timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_files(device: Dict[str, Any], path: str = "/") -> Dict[str, Any]:
    """
    List files and folders with size and date.
    Returns full directory listing including files.
    """
    try:
        path = normalize_path(path)
        files: List[Dict[str, Any]] = []

        if device.get('is_host'):
            # Local listing
            if not os.path.isdir(path):
                return {"success": False, "error": f"Not a directory: {path}"}

            try:
                for entry in os.listdir(path):
                    if entry.startswith('.'):
                        continue
                    full_path = os.path.join(path, entry)
                    try:
                        stat = os.stat(full_path)
                        is_dir = os.path.isdir(full_path)
                        files.append({
                            "name": entry,
                            "is_dir": is_dir,
                            "size": stat.st_size if not is_dir else 0,
                            "mtime": int(stat.st_mtime)
                        })
                    except (PermissionError, OSError):
                        continue
            except PermissionError:
                return {"success": False, "error": "Permission denied"}

        else:
            # Remote listing via SSH
            ssh_config = device.get('ssh', {})
            user = ssh_config.get('user')
            port = ssh_config.get('port', 22)
            ip = device.get('ip')

            if not user:
                return {"success": False, "error": "SSH not configured"}

            # Use ls -la (works on BusyBox/Synology too)
            cmd = f"ls -la '{path}' 2>/dev/null"
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-p", str(port), f"{user}@{ip}", cmd],
                capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                return {"success": False, "error": "Failed to list directory"}

            files = _parse_ls_output(result.stdout)

        # Sort: folders first, then by name
        files.sort(key=lambda f: (not f['is_dir'], f['name'].lower()))

        # Get disk space for current path
        storage = _get_storage_info(device, path)

        return {"success": True, "path": path, "files": files, "storage": storage}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SSH timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _parse_ls_output(output: str) -> List[Dict[str, Any]]:
    """Parse ls -la output into file list."""
    from datetime import datetime
    
    files: List[Dict[str, Any]] = []
    
    for line in output.strip().split('\n'):
        if not line or line.startswith('total'):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue

        perms = parts[0]
        size = int(parts[4]) if parts[4].isdigit() else 0
        # Parse date: "Dec 3 10:30" or "Dec 3 2023"
        month = parts[5]
        day = parts[6]
        time_or_year = parts[7]
        name = ' '.join(parts[8:])

        if name in ('.', '..') or name.startswith('.'):
            continue

        # Convert to timestamp (approximate)
        try:
            months = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            mon = months.get(month, 1)
            d = int(day)
            now = datetime.now()
            if ':' in time_or_year:
                # This year
                yr = now.year
            else:
                yr = int(time_or_year)
            mtime = int(datetime(yr, mon, d).timestamp())
        except Exception:
            mtime = 0

        is_dir = perms.startswith('d')
        files.append({
            "name": name,
            "is_dir": is_dir,
            "size": size if not is_dir else 0,
            "mtime": mtime
        })
    
    return files


def _get_storage_info(device: Dict[str, Any], path: str) -> Dict[str, Any] | None:
    """Get disk storage info for a path."""
    try:
        if device.get('is_host'):
            stat = os.statvfs(path)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free
            return {
                "total": total,
                "used": used,
                "free": free,
                "percent": round((used / total) * 100) if total > 0 else 0
            }
        else:
            # Remote via SSH - use df for the path
            ssh_config = device.get('ssh', {})
            user = ssh_config.get('user')
            port = ssh_config.get('port', 22)
            ip = device.get('ip')
            
            if not user:
                return None
                
            cmd = f"df -B1 '{path}' 2>/dev/null | tail -1"
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                 "-p", str(port), f"{user}@{ip}", cmd],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split()
                if len(parts) >= 4:
                    total = int(parts[1]) if parts[1].isdigit() else 0
                    used = int(parts[2]) if parts[2].isdigit() else 0
                    free = int(parts[3]) if parts[3].isdigit() else 0
                    return {
                        "total": total,
                        "used": used,
                        "free": free,
                        "percent": round((used / total) * 100) if total > 0 else 0
                    }
    except Exception:
        pass
    return None
