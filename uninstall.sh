#!/bin/bash
#
# DeQ - Uninstall Script
#

set -e

echo "================================================================"
echo "              DeQ - Uninstaller                                 "
echo "================================================================"
echo ""
echo "  This will:"
echo "  - Stop the DeQ service"
echo "  - Remove the systemd service"
echo "  - Optionally delete /opt/deq (including your config!)"
echo ""
echo "================================================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Please run as root (sudo ./uninstall.sh)"
    exit 1
fi

echo "  Type 'DELETE' to confirm uninstall, or anything else to cancel."
read -p "  > " confirm
if [ "$confirm" != "DELETE" ]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""

# Stop and disable service
if systemctl is-active --quiet deq 2>/dev/null; then
    echo "Stopping DeQ service..."
    systemctl stop deq
    echo "[OK] Service stopped"
fi

if systemctl is-enabled --quiet deq 2>/dev/null; then
    echo "Disabling DeQ service..."
    systemctl disable deq
    echo "[OK] Service disabled"
fi

# Remove systemd service file
if [ -f "/etc/systemd/system/deq.service" ]; then
    echo "Removing systemd service..."
    rm /etc/systemd/system/deq.service
    systemctl daemon-reload
    echo "[OK] Service removed"
fi

echo ""
echo "================================================================"
echo "  Service uninstalled successfully!"
echo "================================================================"
echo ""

# Ask about data deletion
if [ -d "/opt/deq" ]; then
    echo "  WARNING: /opt/deq still exists"
    echo ""
    echo "  This directory contains:"
    echo "  - Your configuration (config.json)"
    echo "  - Task logs"
    echo "  - History data"
    echo ""
    read -p "  Delete /opt/deq and ALL data? [y/N]: " delete_data
    if [[ "$delete_data" =~ ^[Yy]$ ]]; then
        echo ""
        echo "  Are you REALLY sure? This cannot be undone!"
        read -p "  Type 'DELETE' to confirm: " confirm_delete
        if [ "$confirm_delete" = "DELETE" ]; then
            rm -rf /opt/deq
            echo ""
            echo "[OK] /opt/deq deleted"
        else
            echo ""
            echo "[INFO] Data preserved at /opt/deq"
        fi
    else
        echo ""
        echo "[INFO] Data preserved at /opt/deq"
        echo "       To delete manually: sudo rm -rf /opt/deq"
    fi
fi

echo ""
echo "================================================================"
echo "  DeQ has been uninstalled."
echo "================================================================"
echo ""
echo "  Optional cleanup on remote devices:"
echo "  If you configured passwordless sudo for shutdown, remove it:"
echo "    sudo rm /etc/sudoers.d/deq-shutdown"
echo ""
