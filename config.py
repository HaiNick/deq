"""
DeQ - Configuration Management
Handles loading, saving, and default configuration structures.
"""

import json
import os
from typing import Dict, Any, Optional

# === CONFIGURATION CONSTANTS ===
DEFAULT_PORT = 5050
DATA_DIR = "/opt/deq"
CONFIG_FILE = f"{DATA_DIR}/config.json"
HISTORY_DIR = f"{DATA_DIR}/history"
TASK_LOGS_DIR = f"{DATA_DIR}/task-logs"
VERSION = "0.9.7"

# === DEFAULT ALERT THRESHOLDS ===
DEFAULT_ALERTS = {
    "online": True,
    "cpu": 90,
    "ram": 90,
    "cpu_temp": 80,
    "disk_usage": 90,
    "disk_temp": 60,
    "smart": True
}

# === DEFAULT HOST DEVICE ===
DEFAULT_HOST_DEVICE = {
    "id": "host",
    "name": "DeQ Host",
    "ip": "localhost",
    "icon": "cpu",
    "is_host": True
}

# === DEFAULT CONFIG STRUCTURE ===
DEFAULT_CONFIG = {
    "settings": {
        "theme": "dark",
        "text_color": "#e0e0e0",
        "accent_color": "#2ed573"
    },
    "links": [],
    "devices": [],
    "tasks": [],
    "auth": {
        "enabled": False,
        "api_keys": []
    },
    "notifications": {
        "enabled": False,
        "ntfy": {
            "enabled": False,
            "server": "https://ntfy.sh",
            "topic": "",
            "token": ""
        },
        "discord": {
            "enabled": False,
            "webhook_url": ""
        },
        "slack": {
            "enabled": False,
            "webhook_url": ""
        },
        "webhook": {
            "enabled": False,
            "url": "",
            "headers": {}
        },
        "alerts": {
            "device_offline": True,
            "container_stopped": True,
            "high_cpu": True,
            "high_memory": True,
            "high_disk": True
        },
        "thresholds": {
            "cpu_percent": 90,
            "memory_percent": 90,
            "disk_percent": 90
        }
    }
}

# Global config instance
_config: Dict[str, Any] = {}


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(TASK_LOGS_DIR, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    Merges with defaults for missing keys and ensures host device exists.
    """
    global _config
    
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            cfg = json.load(f)
            # Merge with defaults for missing keys
            for key in DEFAULT_CONFIG:
                if key not in cfg:
                    cfg[key] = DEFAULT_CONFIG[key]
    else:
        cfg = DEFAULT_CONFIG.copy()
        cfg["devices"] = []

    # Ensure host device exists
    host_exists = any(d.get("is_host") for d in cfg.get("devices", []))
    if not host_exists:
        cfg["devices"].insert(0, DEFAULT_HOST_DEVICE.copy())

    _config = cfg
    return cfg


def save_config(config: Dict[str, Any]) -> None:
    """Persist configuration to JSON file."""
    global _config
    _config = config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_config() -> Dict[str, Any]:
    """Get the current configuration."""
    global _config
    if not _config:
        return load_config()
    return _config


def set_config(config: Dict[str, Any]) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def get_config_with_defaults() -> Dict[str, Any]:
    """
    Get config with default alert settings merged into each device.
    Used when sending config to clients.
    """
    cfg = get_config().copy()
    cfg['devices'] = []
    for dev in get_config().get('devices', []):
        d = dev.copy()
        d['alerts'] = {**DEFAULT_ALERTS, **dev.get('alerts', {})}
        cfg['devices'].append(d)
    return cfg


# === HISTORY MANAGEMENT ===
def get_history_file(device_id: str) -> str:
    """Get the path to a device's history file."""
    return f"{HISTORY_DIR}/{device_id}.json"


def load_history(device_id: str) -> Dict[str, Any]:
    """Load history data for a device."""
    path = get_history_file(device_id)
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def save_history(device_id: str, history: Dict[str, Any]) -> None:
    """
    Save history data for a device.
    Automatically trims data older than 400 days.
    """
    from datetime import datetime, timedelta
    
    # Keep only last 400 days
    cutoff = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    history = {k: v for k, v in history.items() if k >= cutoff}
    
    with open(get_history_file(device_id), 'w') as f:
        json.dump(history, f)


def record_stats(device_id: str, cpu: int, temp: Optional[int]) -> None:
    """Record hourly stats for a device."""
    from datetime import datetime
    
    history = load_history(device_id)
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now().hour

    if today not in history:
        history[today] = {"hourly": {}, "totals": {"samples": 0, "cpu_sum": 0, "temp_max": 0}}

    # Record hourly (keep latest per hour)
    history[today]["hourly"][str(hour)] = {"cpu": cpu, "temp": temp}

    # Update totals
    history[today]["totals"]["samples"] += 1
    history[today]["totals"]["cpu_sum"] += cpu
    history[today]["totals"]["temp_max"] = max(
        history[today]["totals"].get("temp_max", 0), 
        temp or 0
    )

    save_history(device_id, history)


# Initialize directories on module load
ensure_dirs()
