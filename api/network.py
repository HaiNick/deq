"""
DeQ API - Network Endpoints
Handles network scanning and discovery API requests.
"""

from typing import Dict, Any

from core.network import scan_network as do_scan_network


def handle_network_scan() -> Dict[str, Any]:
    """Handle GET /api/network/scan - scan for devices on network."""
    return do_scan_network()
