"""
DeQ Core - Network Scanning
Tailscale and ARP-based network device discovery.
"""

import subprocess
import json
import os
from typing import Dict, Any, List

from utils.subprocess_utils import ping_host


def get_default_ssh_user() -> str:
    """Get default SSH user from /home/ directory."""
    try:
        home_dirs = [d for d in os.listdir('/home') if os.path.isdir(f'/home/{d}')]
        home_dirs = [d for d in home_dirs if not d.startswith('.')]
        if home_dirs:
            return sorted(home_dirs)[0]
    except Exception:
        pass
    return "root"


def scan_network() -> Dict[str, Any]:
    """
    Scan for devices via Tailscale and ARP cache.
    Returns device list with hostname, IPs, MAC, OS, and online status.
    """
    devices: List[Dict[str, Any]] = []
    source = "none"
    default_ssh_user = get_default_ssh_user()

    # Try Tailscale first
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            source = "tailscale"

            # Ping online peers to fill ARP cache
            for peer in data.get('Peer', {}).values():
                if peer.get('Online'):
                    ts_ips = peer.get('TailscaleIPs', [])
                    if ts_ips:
                        ping_host(ts_ips[0], timeout=0.2)

            # Re-fetch tailscale status after pings (CurAddr may be populated now)
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)

            # Read ARP cache after pings
            arp_cache: Dict[str, str] = {}
            try:
                with open('/proc/net/arp', 'r') as f:
                    for line in f.readlines()[1:]:
                        parts = line.split()
                        if len(parts) >= 4 and parts[2] == '0x2':
                            ip = parts[0]
                            mac = parts[3]
                            if mac != '00:00:00:00:00:00':
                                arp_cache[ip] = mac
            except Exception:
                pass

            # Get self node to exclude
            self_node = data.get('Self', {}).get('HostName', '')

            for peer_id, peer in data.get('Peer', {}).items():
                hostname = peer.get('HostName', '')
                if not hostname or hostname == 'localhost':
                    dns_name = peer.get('DNSName', '')
                    hostname = dns_name.split('.')[0] if dns_name else ''
                if not hostname or hostname == self_node:
                    continue

                tailscale_ip = None
                tailscale_ips = peer.get('TailscaleIPs', [])
                for ts_ip in tailscale_ips:
                    if ts_ip.startswith('100.'):
                        tailscale_ip = ts_ip
                        break

                # Extract LAN IP from CurAddr (format: 192.168.x.x:port)
                lan_ip = None
                cur_addr = peer.get('CurAddr', '')
                if cur_addr and not cur_addr.startswith('100.') and not cur_addr.startswith('['):
                    lan_ip = cur_addr.rsplit(':', 1)[0]
                    if lan_ip.startswith('100.') or not lan_ip[0].isdigit():
                        lan_ip = None

                mac = arp_cache.get(lan_ip) if lan_ip else None
                os_type = peer.get('OS', '').lower()
                online = peer.get('Online', False)

                devices.append({
                    "hostname": hostname,
                    "tailscale_ip": tailscale_ip,
                    "lan_ip": lan_ip,
                    "mac": mac,
                    "os": os_type,
                    "online": online
                })
    except Exception:
        pass

    # Fallback to ARP only if no Tailscale
    if source == "none":
        arp_cache: Dict[str, str] = {}
        try:
            with open('/proc/net/arp', 'r') as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 4 and parts[2] == '0x2':
                        ip = parts[0]
                        mac = parts[3]
                        if mac != '00:00:00:00:00:00':
                            arp_cache[ip] = mac
        except Exception:
            pass
        
        if arp_cache:
            source = "arp"
            for ip, mac in arp_cache.items():
                devices.append({
                    "hostname": None,
                    "tailscale_ip": None,
                    "lan_ip": ip,
                    "mac": mac,
                    "os": None,
                    "online": True
                })

    return {
        "success": True,
        "source": source,
        "devices": devices,
        "default_ssh_user": default_ssh_user
    }
