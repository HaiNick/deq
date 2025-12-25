"""
Notifications API endpoints.
"""
from typing import Dict, Any
from config import get_config, save_config

# Lazy import to avoid circular dependency
def _get_notification_manager():
    from notifications.manager import NotificationManager
    return NotificationManager()


def handle_get_notification_settings() -> Dict[str, Any]:
    """Get current notification settings."""
    config = get_config()
    notifications = config.get('notifications', {})
    
    # Return settings without sensitive data
    return {
        "success": True,
        "settings": {
            "enabled": notifications.get('enabled', False),
            "ntfy": {
                "enabled": notifications.get('ntfy', {}).get('enabled', False),
                "server": notifications.get('ntfy', {}).get('server', 'https://ntfy.sh'),
                "topic": notifications.get('ntfy', {}).get('topic', ''),
                "has_token": bool(notifications.get('ntfy', {}).get('token', ''))
            },
            "discord": {
                "enabled": notifications.get('discord', {}).get('enabled', False),
                "has_webhook": bool(notifications.get('discord', {}).get('webhook_url', ''))
            },
            "slack": {
                "enabled": notifications.get('slack', {}).get('enabled', False),
                "has_webhook": bool(notifications.get('slack', {}).get('webhook_url', ''))
            },
            "webhook": {
                "enabled": notifications.get('webhook', {}).get('enabled', False),
                "has_url": bool(notifications.get('webhook', {}).get('url', ''))
            },
            "alerts": notifications.get('alerts', {
                "device_offline": True,
                "container_stopped": True,
                "high_cpu": True,
                "high_memory": True,
                "high_disk": True
            }),
            "thresholds": notifications.get('thresholds', {
                "cpu_percent": 90,
                "memory_percent": 90,
                "disk_percent": 90
            })
        }
    }


def handle_update_notification_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update notification settings."""
    config = get_config()
    
    if 'notifications' not in config:
        config['notifications'] = {}
    
    notifications = config['notifications']
    
    # Update enabled flag
    if 'enabled' in data:
        notifications['enabled'] = bool(data['enabled'])
    
    # Update ntfy settings
    if 'ntfy' in data:
        if 'ntfy' not in notifications:
            notifications['ntfy'] = {}
        ntfy_data = data['ntfy']
        if 'enabled' in ntfy_data:
            notifications['ntfy']['enabled'] = bool(ntfy_data['enabled'])
        if 'server' in ntfy_data:
            notifications['ntfy']['server'] = str(ntfy_data['server'])
        if 'topic' in ntfy_data:
            notifications['ntfy']['topic'] = str(ntfy_data['topic'])
        if 'token' in ntfy_data and ntfy_data['token']:  # Only update if provided
            notifications['ntfy']['token'] = str(ntfy_data['token'])
    
    # Update discord settings
    if 'discord' in data:
        if 'discord' not in notifications:
            notifications['discord'] = {}
        discord_data = data['discord']
        if 'enabled' in discord_data:
            notifications['discord']['enabled'] = bool(discord_data['enabled'])
        if 'webhook_url' in discord_data and discord_data['webhook_url']:
            notifications['discord']['webhook_url'] = str(discord_data['webhook_url'])
    
    # Update slack settings
    if 'slack' in data:
        if 'slack' not in notifications:
            notifications['slack'] = {}
        slack_data = data['slack']
        if 'enabled' in slack_data:
            notifications['slack']['enabled'] = bool(slack_data['enabled'])
        if 'webhook_url' in slack_data and slack_data['webhook_url']:
            notifications['slack']['webhook_url'] = str(slack_data['webhook_url'])
    
    # Update generic webhook settings
    if 'webhook' in data:
        if 'webhook' not in notifications:
            notifications['webhook'] = {}
        webhook_data = data['webhook']
        if 'enabled' in webhook_data:
            notifications['webhook']['enabled'] = bool(webhook_data['enabled'])
        if 'url' in webhook_data and webhook_data['url']:
            notifications['webhook']['url'] = str(webhook_data['url'])
        if 'headers' in webhook_data:
            notifications['webhook']['headers'] = dict(webhook_data['headers'])
    
    # Update alert types
    if 'alerts' in data:
        notifications['alerts'] = {
            "device_offline": bool(data['alerts'].get('device_offline', True)),
            "container_stopped": bool(data['alerts'].get('container_stopped', True)),
            "high_cpu": bool(data['alerts'].get('high_cpu', True)),
            "high_memory": bool(data['alerts'].get('high_memory', True)),
            "high_disk": bool(data['alerts'].get('high_disk', True))
        }
    
    # Update thresholds
    if 'thresholds' in data:
        notifications['thresholds'] = {
            "cpu_percent": int(data['thresholds'].get('cpu_percent', 90)),
            "memory_percent": int(data['thresholds'].get('memory_percent', 90)),
            "disk_percent": int(data['thresholds'].get('disk_percent', 90))
        }
    
    save_config(config)
    
    return {"success": True, "message": "Notification settings updated"}


def handle_test_notification(data: Dict[str, Any]) -> Dict[str, Any]:
    """Send a test notification."""
    channel = data.get('channel', 'all')  # 'ntfy', 'discord', 'slack', 'webhook', 'all'
    
    manager = _get_notification_manager()
    
    test_message = "🧪 Test notification from DeQ Dashboard"
    test_title = "DeQ Test"
    
    results = {}
    
    if channel in ('ntfy', 'all'):
        try:
            from notifications.ntfy import send_ntfy_notification
            config = get_config().get('notifications', {}).get('ntfy', {})
            if config.get('enabled') and config.get('topic'):
                success = send_ntfy_notification(
                    title=test_title,
                    message=test_message,
                    priority="default",
                    tags=["test"]
                )
                results['ntfy'] = {"success": success}
            else:
                results['ntfy'] = {"success": False, "error": "ntfy not configured"}
        except Exception as e:
            results['ntfy'] = {"success": False, "error": str(e)}
    
    if channel in ('discord', 'all'):
        try:
            from notifications.webhook import send_discord_notification
            config = get_config().get('notifications', {}).get('discord', {})
            if config.get('enabled') and config.get('webhook_url'):
                success = send_discord_notification(
                    title=test_title,
                    message=test_message,
                    color=0x00ff00  # Green
                )
                results['discord'] = {"success": success}
            else:
                results['discord'] = {"success": False, "error": "Discord not configured"}
        except Exception as e:
            results['discord'] = {"success": False, "error": str(e)}
    
    if channel in ('slack', 'all'):
        try:
            from notifications.webhook import send_slack_notification
            config = get_config().get('notifications', {}).get('slack', {})
            if config.get('enabled') and config.get('webhook_url'):
                success = send_slack_notification(
                    title=test_title,
                    message=test_message
                )
                results['slack'] = {"success": success}
            else:
                results['slack'] = {"success": False, "error": "Slack not configured"}
        except Exception as e:
            results['slack'] = {"success": False, "error": str(e)}
    
    if channel in ('webhook', 'all'):
        try:
            from notifications.webhook import send_generic_webhook
            config = get_config().get('notifications', {}).get('webhook', {})
            if config.get('enabled') and config.get('url'):
                success = send_generic_webhook(
                    event_type="test",
                    data={"title": test_title, "message": test_message}
                )
                results['webhook'] = {"success": success}
            else:
                results['webhook'] = {"success": False, "error": "Webhook not configured"}
        except Exception as e:
            results['webhook'] = {"success": False, "error": str(e)}
    
    # Overall success if any channel succeeded
    any_success = any(r.get('success', False) for r in results.values())
    
    return {
        "success": any_success,
        "results": results,
        "message": "Test notifications sent" if any_success else "No notifications sent"
    }
