"""
DeQ Notifications - Generic Webhook Integration
Support for Discord, Slack, and custom webhooks.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List


def send_webhook_notification(
    url: str,
    title: str,
    message: str,
    color: Optional[str] = None,
    fields: Optional[List[Dict[str, str]]] = None,
    webhook_type: str = "generic",
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Send a notification via webhook.
    
    Args:
        url: Webhook URL
        title: Notification title
        message: Notification body text
        color: Hex color for embed (Discord/Slack)
        fields: Additional fields [{"name": "...", "value": "..."}]
        webhook_type: "discord", "slack", or "generic"
        timeout: Request timeout in seconds
        
    Returns:
        {"success": bool, "error": str (if failed)}
    """
    if not url:
        return {"success": False, "error": "Webhook URL is required"}
    
    try:
        if webhook_type == "discord":
            payload = _build_discord_payload(title, message, color, fields)
        elif webhook_type == "slack":
            payload = _build_slack_payload(title, message, color, fields)
        else:
            payload = _build_generic_payload(title, message, fields)
        
        data = json.dumps(payload).encode('utf-8')
        headers = {"Content-Type": "application/json"}
        
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Discord returns 204 No Content on success
            if response.status in (200, 201, 204):
                return {"success": True}
            else:
                return {"success": False, "error": f"HTTP {response.status}"}
                
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8')[:200]
        except:
            pass
        return {"success": False, "error": f"HTTP {e.code}: {error_body or e.reason}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _build_discord_payload(
    title: str,
    message: str,
    color: Optional[str],
    fields: Optional[List[Dict[str, str]]]
) -> Dict[str, Any]:
    """Build Discord webhook payload with embed."""
    embed = {
        "title": title,
        "description": message,
    }
    
    if color:
        # Convert hex color to decimal
        color_hex = color.lstrip('#')
        embed["color"] = int(color_hex, 16)
    
    if fields:
        embed["fields"] = [
            {"name": f["name"], "value": f["value"], "inline": f.get("inline", True)}
            for f in fields
        ]
    
    return {"embeds": [embed]}


def _build_slack_payload(
    title: str,
    message: str,
    color: Optional[str],
    fields: Optional[List[Dict[str, str]]]
) -> Dict[str, Any]:
    """Build Slack webhook payload with attachment."""
    attachment = {
        "title": title,
        "text": message,
        "mrkdwn_in": ["text"],
    }
    
    if color:
        attachment["color"] = color
    
    if fields:
        attachment["fields"] = [
            {"title": f["name"], "value": f["value"], "short": f.get("inline", True)}
            for f in fields
        ]
    
    return {"attachments": [attachment]}


def _build_generic_payload(
    title: str,
    message: str,
    fields: Optional[List[Dict[str, str]]]
) -> Dict[str, Any]:
    """Build generic JSON payload."""
    payload = {
        "title": title,
        "message": message,
    }
    
    if fields:
        payload["fields"] = fields
    
    return payload


def test_webhook_connection(
    url: str,
    webhook_type: str = "generic"
) -> Dict[str, Any]:
    """
    Test webhook connection by sending a test notification.
    """
    return send_webhook_notification(
        url=url,
        title="DeQ Test",
        message="Test notification from DeQ dashboard",
        color="#2ed573",
        webhook_type=webhook_type
    )
