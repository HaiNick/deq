"""
DeQ Notifications - Alert System
Push notifications via ntfy.sh, webhooks, and other providers.
"""

from notifications.ntfy import send_ntfy_notification
from notifications.webhook import send_webhook_notification
from notifications.manager import notify, NotificationLevel

__all__ = [
    'send_ntfy_notification',
    'send_webhook_notification',
    'notify',
    'NotificationLevel'
]
