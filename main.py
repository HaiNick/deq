#!/usr/bin/env python3
"""
DeQ - Homelab Dashboard
Main entry point for the application.

A lightweight, zero-dependency dashboard for managing your homelab.
"""

import argparse
import os
import sys
from http.server import HTTPServer

from config import load_config, DATA_DIR, TASK_LOGS_DIR
from web.handler import RequestHandler, set_static_content, VERSION
from core.scheduler import scheduler


# Default port
DEFAULT_PORT = 7654


def ensure_directories() -> None:
    """Ensure required directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(TASK_LOGS_DIR, exist_ok=True)


def load_static_content() -> tuple:
    """Load static content from files or embedded strings."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try to load from static/ directory first
    html_path = os.path.join(script_dir, 'static', 'index.html')
    manifest_path = os.path.join(script_dir, 'static', 'manifest.json')
    icon_path = os.path.join(script_dir, 'static', 'icon.svg')
    
    html = ""
    manifest = ""
    icon = ""
    
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
    
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = f.read()
    
    if os.path.exists(icon_path):
        with open(icon_path, 'r', encoding='utf-8') as f:
            icon = f.read()
    
    # Fallback: check if server.py still exists and has embedded content
    if not html or not manifest or not icon:
        server_py = os.path.join(script_dir, 'server.py')
        if os.path.exists(server_py):
            print("[Warning] Static files not found, using embedded content from server.py")
            # Import from server.py as fallback during migration
            try:
                # This allows gradual migration
                import importlib.util
                spec = importlib.util.spec_from_file_location("server", server_py)
                server_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(server_module)
                
                if not html:
                    html = getattr(server_module, 'HTML_PAGE', '')
                if not manifest:
                    manifest = getattr(server_module, 'MANIFEST_JSON', '')
                if not icon:
                    icon = getattr(server_module, 'ICON_SVG', '')
            except Exception as e:
                print(f"[Warning] Failed to load from server.py: {e}")
    
    return html, manifest, icon


def print_banner(port: int) -> None:
    """Print startup banner."""
    print(f"""
================================================================
              DeQ - Homelab Dashboard
================================================================
  Version: {VERSION}
  Port:    {port}

  Access URL:
  http://YOUR-IP:{port}/
================================================================
    """)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='DeQ - Homelab Dashboard')
    parser.add_argument(
        '--port', 
        type=int, 
        default=DEFAULT_PORT, 
        help=f'Port to run on (default: {DEFAULT_PORT})'
    )
    args = parser.parse_args()
    
    port = args.port
    
    # Setup
    ensure_directories()
    load_config()
    
    # Load static content
    html, manifest, icon = load_static_content()
    if not html:
        print("[Error] No HTML content available. Please ensure static/index.html exists.")
        sys.exit(1)
    
    set_static_content(html, manifest, icon)
    
    # Print banner
    print_banner(port)
    
    # Start task scheduler
    scheduler.start()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    print(f"Server running on port {port}...")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        scheduler.stop()
        server.shutdown()


if __name__ == '__main__':
    main()
