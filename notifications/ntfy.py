"""
DeQ Notifications - ntfy.sh Integration
Push notifications via ntfy.sh (self-hosted or ntfy.sh service).
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional


def send_ntfy_notification(
    server: str,
    topic: str,
    title: str,
    message: str,
    priority: int = 3,
    tags: Optional[list] = None,
    click_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Send a push notification via ntfy.sh.
    
    Args:
        server: ntfy server URL (e.g., "https://ntfy.sh" or self-hosted)
        topic: Topic/channel name to publish to
        title: Notification title
        message: Notification body text
        priority: 1 (min) to 5 (max), default 3 (normal)
        tags: List of emoji tags (e.g., ["warning", "server"])
        click_url: URL to open when notification is clicked
        auth_token: Bearer token for authenticated topics
        timeout: Request timeout in seconds
        
    Returns:
        {"success": bool, "error": str (if failed)}
    """
    if not server or not topic:
        return {"success": False, "error": "Server and topic are required"}
    
    # Normalize server URL
    server = server.rstrip('/')
    url = f"{server}/{topic}"
    
    # Build headers
    headers = {
        "Title": title,
        "Priority": str(priority),
    }
    
    if tags:
        headers["Tags"] = ",".join(tags)
    
    if click_url:
        headers["Click"] = click_url
    
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    try:
        # Create request with message body
        data = message.encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return {"success": True}
            else:
                return {"success": False, "error": f"HTTP {response.status}"}
                
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_ntfy_connection(
    server: str,
    topic: str,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Test ntfy connection by sending a test notification.
    """
    return send_ntfy_notification(
        server=server,
        topic=topic,
        title="DeQ Test",
        message="Test notification from DeQ dashboard",
        priority=2,
        tags=["white_check_mark", "test"],
        auth_token=auth_token
    )
