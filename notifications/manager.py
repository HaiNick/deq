"""
DeQ Notifications - Notification Manager
Central notification dispatcher with support for multiple providers.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import get_config
from notifications.ntfy import send_ntfy_notification
from notifications.webhook import send_webhook_notification


class NotificationLevel(str, Enum):
    """Notification severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Map notification levels to ntfy priorities
NTFY_PRIORITY_MAP = {
    NotificationLevel.INFO: 2,
    NotificationLevel.WARNING: 3,
    NotificationLevel.ERROR: 4,
    NotificationLevel.CRITICAL: 5,
}

# Map notification levels to colors (hex)
LEVEL_COLORS = {
    NotificationLevel.INFO: "#2ed573",      # Green
    NotificationLevel.WARNING: "#ffa502",   # Orange
    NotificationLevel.ERROR: "#ff4757",     # Red
    NotificationLevel.CRITICAL: "#a55eea",  # Purple
}

# Map notification levels to ntfy tags
NTFY_TAGS_MAP = {
    NotificationLevel.INFO: ["information_source"],
    NotificationLevel.WARNING: ["warning"],
    NotificationLevel.ERROR: ["x"],
    NotificationLevel.CRITICAL: ["rotating_light", "skull"],
}


def get_notification_config() -> Dict[str, Any]:
    """Get notification configuration from config."""
    config = get_config()
    return config.get('notifications', {})


def is_notifications_enabled() -> bool:
    """Check if notifications are enabled."""
    notif_config = get_notification_config()
    return notif_config.get('enabled', False)


def notify(
    title: str,
    message: str,
    level: NotificationLevel = NotificationLevel.INFO,
    device_id: Optional[str] = None,
    device_name: Optional[str] = None,
    container_name: Optional[str] = None,
    click_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send notification to all configured providers.
    
    Args:
        title: Notification title
        message: Notification body
        level: Severity level (info, warning, error, critical)
        device_id: Optional device ID for context
        device_name: Optional device name for display
        container_name: Optional container name for context
        click_url: Optional URL to open on click
        
    Returns:
        {"success": bool, "providers": [results per provider]}
    """
    if not is_notifications_enabled():
        return {"success": True, "skipped": True, "reason": "Notifications disabled"}
    
    notif_config = get_notification_config()
    results = []
    
    # Build context fields
    fields = []
    if device_name:
        fields.append({"name": "Device", "value": device_name})
    elif device_id:
        fields.append({"name": "Device ID", "value": device_id})
    if container_name:
        fields.append({"name": "Container", "value": container_name})
    fields.append({"name": "Time", "value": datetime.now().strftime("%H:%M:%S")})
    
    # ntfy.sh
    ntfy_config = notif_config.get('ntfy', {})
    if ntfy_config.get('enabled'):
        result = send_ntfy_notification(
            server=ntfy_config.get('server', 'https://ntfy.sh'),
            topic=ntfy_config.get('topic', ''),
            title=title,
            message=message,
            priority=NTFY_PRIORITY_MAP.get(level, 3),
            tags=NTFY_TAGS_MAP.get(level, []),
            click_url=click_url,
            auth_token=ntfy_config.get('token')
        )
        results.append({"provider": "ntfy", **result})
    
    # Discord webhook
    discord_config = notif_config.get('discord', {})
    if discord_config.get('enabled') and discord_config.get('webhook_url'):
        result = send_webhook_notification(
            url=discord_config['webhook_url'],
            title=title,
            message=message,
            color=LEVEL_COLORS.get(level),
            fields=fields,
            webhook_type="discord"
        )
        results.append({"provider": "discord", **result})
    
    # Slack webhook
    slack_config = notif_config.get('slack', {})
    if slack_config.get('enabled') and slack_config.get('webhook_url'):
        result = send_webhook_notification(
            url=slack_config['webhook_url'],
            title=title,
            message=message,
            color=LEVEL_COLORS.get(level),
            fields=fields,
            webhook_type="slack"
        )
        results.append({"provider": "slack", **result})
    
    # Generic webhook
    webhook_config = notif_config.get('webhook', {})
    if webhook_config.get('enabled') and webhook_config.get('url'):
        result = send_webhook_notification(
            url=webhook_config['url'],
            title=title,
            message=message,
            fields=fields,
            webhook_type="generic"
        )
        results.append({"provider": "webhook", **result})
    
    # Determine overall success
    if not results:
        return {"success": True, "skipped": True, "reason": "No providers configured"}
    
    all_success = all(r.get('success') for r in results)
    return {
        "success": all_success,
        "providers": results
    }


def notify_device_offline(device_id: str, device_name: str) -> Dict[str, Any]:
    """Send notification when a device goes offline."""
    return notify(
        title=f"🔴 {device_name} Offline",
        message=f"Device '{device_name}' is no longer responding",
        level=NotificationLevel.WARNING,
        device_id=device_id,
        device_name=device_name
    )


def notify_device_online(device_id: str, device_name: str) -> Dict[str, Any]:
    """Send notification when a device comes back online."""
    return notify(
        title=f"🟢 {device_name} Online",
        message=f"Device '{device_name}' is back online",
        level=NotificationLevel.INFO,
        device_id=device_id,
        device_name=device_name
    )


def notify_container_stopped(
    device_id: str,
    device_name: str,
    container_name: str
) -> Dict[str, Any]:
    """Send notification when a container stops unexpectedly."""
    return notify(
        title=f"⏹️ Container Stopped",
        message=f"Container '{container_name}' on {device_name} has stopped",
        level=NotificationLevel.WARNING,
        device_id=device_id,
        device_name=device_name,
        container_name=container_name
    )


def notify_high_resource_usage(
    device_id: str,
    device_name: str,
    resource: str,
    value: int,
    threshold: int
) -> Dict[str, Any]:
    """Send notification for high resource usage."""
    return notify(
        title=f"⚠️ High {resource} on {device_name}",
        message=f"{resource} usage is {value}% (threshold: {threshold}%)",
        level=NotificationLevel.WARNING,
        device_id=device_id,
        device_name=device_name
    )


def notify_task_failed(task_id: str, task_name: str, error: str) -> Dict[str, Any]:
    """Send notification when a scheduled task fails."""
    return notify(
        title=f"❌ Task Failed: {task_name}",
        message=f"Scheduled task failed: {error}",
        level=NotificationLevel.ERROR
    )
