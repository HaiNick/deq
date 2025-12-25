"""
DeQ API - File Endpoints
Handles file management API requests: browse, list, download, upload, operations.
"""

from typing import Dict, Any, Optional, List

from api.devices import get_device_by_id
from fileops.browser import browse_folder, list_files
from fileops.manager import file_operation, get_file_for_download, upload_file


def handle_browse(device_id: str, path: str = "/") -> Dict[str, Any]:
    """Handle GET /api/device/{id}/browse?path=/ - list folders only."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    return browse_folder(device, path)


def handle_list_files(device_id: str, path: str = "/") -> Dict[str, Any]:
    """Handle GET /api/device/{id}/files?path=/ - list files and folders."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    return list_files(device, path)


def handle_download(device_id: str, file_path: str) -> tuple:
    """
    Handle GET /api/device/{id}/download?path=/file.txt
    Returns (content_bytes, filename, error).
    """
    device = get_device_by_id(device_id)
    if not device:
        return None, None, "Device not found"
    
    if not file_path:
        return None, None, "Path required"
    
    return get_file_for_download(device, file_path)


def handle_file_operation(
    device_id: str,
    operation: str,
    paths: List[str],
    dest_device_id: Optional[str] = None,
    dest_path: Optional[str] = None,
    new_name: Optional[str] = None
) -> Dict[str, Any]:
    """Handle POST /api/device/{id}/files - execute file operation."""
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    dest_device = None
    if dest_device_id:
        dest_device = get_device_by_id(dest_device_id)
        if not dest_device:
            return {"success": False, "error": "Destination device not found"}
    
    return file_operation(
        device,
        operation,
        paths,
        dest_device=dest_device,
        dest_path=dest_path,
        new_name=new_name
    )


def handle_upload(
    device_id: str, dest_path: str, files: List[tuple]
) -> Dict[str, Any]:
    """
    Handle POST /api/device/{id}/upload?path=/dest/folder
    files is list of (filename, content_bytes) tuples.
    """
    device = get_device_by_id(device_id)
    if not device:
        return {"success": False, "error": "Device not found"}
    
    uploaded = 0
    errors = []
    
    for filename, content in files:
        result = upload_file(device, dest_path, filename, content)
        if result['success']:
            uploaded += 1
        else:
            errors.append(f"{filename}: {result['error']}")
    
    if errors:
        return {"success": False, "error": "; ".join(errors), "uploaded": uploaded}
    return {"success": True, "uploaded": uploaded}
