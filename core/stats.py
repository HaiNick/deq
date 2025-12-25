"""
DeQ Core - System Statistics Gathering
Collects hardware stats from local and remote systems via /proc and SSH.
"""

import subprocess
import os
from typing import Dict, Any, Optional, List


def get_disk_smart_info() -> Dict[str, Dict[str, Any]]:
    """
    Get SMART info and temps for all disks.
    Returns dict keyed by device name with 'temp' and 'smart' status.
    """
    disks: Dict[str, Dict[str, Any]] = {}
    
    try:
        result = subprocess.run(
            ["lsblk", "-d", "-n", "-o", "NAME,TYPE"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 2 and parts[1] == 'disk':
                dev_name = parts[0]
                disks[dev_name] = {"temp": None, "smart": None}
    except Exception:
        pass

    for dev_name in disks:
        try:
            result = subprocess.run(
                ["sudo", "smartctl", "-A", "-H", f"/dev/{dev_name}"],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout

            if "PASSED" in output:
                disks[dev_name]["smart"] = "ok"
            elif "FAILED" in output:
                disks[dev_name]["smart"] = "failed"

            for line in output.split('\n'):
                if 'Temperature' in line and '-' in line:
                    after_dash = line.split('-')[-1].strip()
                    first_num = after_dash.split()[0] if after_dash else ''
                    if first_num.isdigit() and 0 < int(first_num) < 100:
                        disks[dev_name]["temp"] = int(first_num)
                        break
        except Exception:
            pass

    return disks


def get_container_stats() -> Dict[str, Dict[str, float]]:
    """
    Get CPU and RAM stats for all running containers.
    Returns dict keyed by container name with 'cpu' and 'mem' percentages.
    """
    containers: Dict[str, Dict[str, float]] = {}
    
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}:{{.CPUPerc}}:{{.MemPerc}}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        name = parts[0]
                        cpu = parts[1].replace('%', '').strip()
                        mem = parts[2].replace('%', '').strip()
                        try:
                            containers[name] = {
                                "cpu": float(cpu),
                                "mem": float(mem)
                            }
                        except ValueError:
                            pass
    except Exception:
        pass
    
    return containers


def get_local_stats() -> Dict[str, Any]:
    """
    Get stats for the device running DeQ (local system).
    Returns dict with cpu, ram_used, ram_total, temp, disks, uptime, disk_smart, container_stats.
    """
    stats: Dict[str, Any] = {
        "cpu": 0,
        "ram_used": 0,
        "ram_total": 0,
        "temp": None,
        "disks": [],
        "uptime": "",
        "disk_smart": {},
        "container_stats": {}
    }

    try:
        # CPU load
        with open('/proc/loadavg', 'r') as f:
            load = float(f.read().split()[0])
            cpu_count = os.cpu_count() or 1
            stats["cpu"] = min(100, int(load / cpu_count * 100))

        # Memory
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(':')] = int(parts[1]) * 1024
            stats["ram_total"] = meminfo.get("MemTotal", 0)
            stats["ram_used"] = stats["ram_total"] - meminfo.get("MemAvailable", 0)

        # Temperature
        thermal_zones = ["/sys/class/thermal/thermal_zone0/temp"]
        for zone in thermal_zones:
            if os.path.exists(zone):
                with open(zone, 'r') as f:
                    stats["temp"] = int(f.read().strip()) // 1000
                break

        # Disk usage
        result = subprocess.run(
            ["df", "-B1", "--output=source,target,size,used"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split('\n')[1:]:
            parts = line.split()
            if len(parts) >= 4:
                source = parts[0]
                mount = parts[1]
                if mount in ['/', '/home'] or mount.startswith(('/mnt', '/media', '/srv')):
                    if int(parts[2]) > 1e9:
                        dev_name = source.split('/')[-1].rstrip('0123456789')
                        stats["disks"].append({
                            "mount": mount,
                            "total": int(parts[2]),
                            "used": int(parts[3]),
                            "device": dev_name
                        })

        # Uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            stats["uptime"] = f"{days}d {hours}h" if days > 0 else f"{hours}h"

        # SMART info
        stats["disk_smart"] = get_disk_smart_info()
        
        # Container stats
        stats["container_stats"] = get_container_stats()

    except Exception as e:
        print(f"Error getting local stats: {e}")

    return stats


def get_remote_stats(ip: str, user: str, port: int = 22) -> Optional[Dict[str, Any]]:
    """
    Get stats from remote device via SSH.
    Returns dict with same structure as get_local_stats(), or None on failure.
    """
    stats: Dict[str, Any] = {
        "cpu": 0,
        "ram_used": 0,
        "ram_total": 0,
        "temp": None,
        "disks": [],
        "uptime": "",
        "disk_smart": {},
        "container_stats": {}
    }
    
    ssh_base = [
        "ssh", "-o", "StrictHostKeyChecking=no", 
        "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
        "-p", str(port), f"{user}@{ip}"
    ]

    # Basic stats (required)
    try:
        cmd = "nproc; echo '---'; cat /proc/loadavg; echo '---'; cat /proc/meminfo | head -10; echo '---'; cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -1; echo '---'; cat /proc/uptime"
        result = subprocess.run(ssh_base + [cmd], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return None
        
        parts = result.stdout.split('---')

        cpu_count = int(parts[0].strip()) if parts[0].strip().isdigit() else 4
        load = float(parts[1].strip().split()[0])
        stats["cpu"] = min(100, int(load / cpu_count * 100))

        meminfo = {}
        for line in parts[2].strip().split('\n'):
            if ':' in line:
                key, val = line.split(':')
                meminfo[key.strip()] = int(val.split()[0]) * 1024
        stats["ram_total"] = meminfo.get("MemTotal", 0)
        if "MemAvailable" in meminfo:
            stats["ram_used"] = stats["ram_total"] - meminfo["MemAvailable"]
        else:
            free = meminfo.get("MemFree", 0) + meminfo.get("Buffers", 0) + meminfo.get("Cached", 0)
            stats["ram_used"] = stats["ram_total"] - free

        temp_str = parts[3].strip()
        if temp_str.isdigit():
            stats["temp"] = int(temp_str) // 1000

        uptime_seconds = float(parts[4].strip().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        stats["uptime"] = f"{days}d {hours}h" if days > 0 else f"{hours}h"
    except Exception:
        return None

    # Disks (optional)
    try:
        result = subprocess.run(
            ssh_base + ["df -B1 --output=source,target,size,used 2>/dev/null || df -B1"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n')[1:]:
                cols = line.split()
                if len(cols) >= 4:
                    source, mount = cols[0], cols[1]
                    if mount in ['/', '/home'] or mount.startswith(('/mnt', '/media', '/srv')):
                        try:
                            if int(cols[2]) > 1e9:
                                stats["disks"].append({
                                    "mount": mount,
                                    "total": int(cols[2]),
                                    "used": int(cols[3])
                                })
                        except ValueError:
                            pass
    except Exception:
        pass

    # SMART (optional)
    try:
        result = subprocess.run(
            ssh_base + ["lsblk -d -n -o NAME,TYPE 2>/dev/null"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            disk_names = []
            for line in result.stdout.strip().split('\n'):
                cols = line.split()
                if len(cols) >= 2 and cols[1] == 'disk':
                    disk_names.append(cols[0])
                    stats["disk_smart"][cols[0]] = {"temp": None, "smart": None}

            for dev in disk_names:
                try:
                    result = subprocess.run(
                        ssh_base + [f"sudo smartctl -A -H /dev/{dev} 2>/dev/null"],
                        capture_output=True, text=True, timeout=5
                    )
                    output = result.stdout
                    if "PASSED" in output:
                        stats["disk_smart"][dev]["smart"] = "ok"
                    elif "FAILED" in output:
                        stats["disk_smart"][dev]["smart"] = "failed"
                    for line in output.split('\n'):
                        if 'Temperature' in line and '-' in line:
                            after_dash = line.split('-')[-1].strip()
                            first_num = after_dash.split()[0] if after_dash else ''
                            if first_num.isdigit() and 0 < int(first_num) < 100:
                                stats["disk_smart"][dev]["temp"] = int(first_num)
                                break
                except Exception:
                    pass
    except Exception:
        pass

    # Docker stats (optional)
    try:
        result = subprocess.run(
            ssh_base + ["docker stats --no-stream --format '{{.Name}}:{{.CPUPerc}}:{{.MemPerc}}' 2>/dev/null"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    cols = line.split(':')
                    if len(cols) >= 3:
                        try:
                            stats["container_stats"][cols[0]] = {
                                "cpu": float(cols[1].replace('%', '')),
                                "mem": float(cols[2].replace('%', ''))
                            }
                        except ValueError:
                            pass
    except Exception:
        pass

    return stats
