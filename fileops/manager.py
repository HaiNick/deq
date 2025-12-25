"""
DeQ FileOps - File Manager
File operations: copy, move, zip, delete, rename, mkdir.
"""

import subprocess
import os
import time
from typing import Dict, Any, List, Optional

from utils.validators import sanitize_path, is_valid_path, is_valid_folder_name, is_valid_filename, validate_path_secure


def file_operation(
    device: Dict[str, Any],
    operation: str,
    paths: List[str],
    dest_device: Optional[Dict[str, Any]] = None,
    dest_path: Optional[str] = None,
    new_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute file operations: copy, move, rename, delete, zip, mkdir.
    """
    # Validate all source paths
    for p in paths:
        valid, normalized, error = validate_path_secure(p)
        if not valid:
            return {"success": False, "error": f"Invalid path '{p}': {error}"}
    
    # Validate destination path if provided
    if dest_path:
        valid, normalized, error = validate_path_secure(dest_path)
        if not valid:
            return {"success": False, "error": f"Invalid destination path: {error}"}
    
    try:
        ssh_config = device.get('ssh', {})
        user = ssh_config.get('user')
        port = ssh_config.get('port', 22)
        ip = device.get('ip')
        is_host = device.get('is_host', False)

        if not is_host and not user:
            return {"success": False, "error": "SSH not configured"}

        def run_local(cmd: List[str]) -> tuple:
            """Run local command with argument list (no shell)."""
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stderr

        def run_remote(cmd: List[str]) -> tuple:
            """Run remote command via SSH with argument list."""
            ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                       "-p", str(port), f"{user}@{ip}"] + cmd
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=300)
            return result.returncode == 0, result.stderr

        run_cmd = run_local if is_host else run_remote

        if operation == 'delete':
            return _delete_files(run_cmd, paths)
        elif operation == 'rename':
            return _rename_file(run_cmd, paths, new_name)
        elif operation == 'mkdir':
            return _create_folder(run_cmd, paths, new_name)
        elif operation == 'zip':
            return _zip_files(run_cmd, paths, is_host, user, ip, port)
        elif operation in ('copy', 'move'):
            return _transfer_files(
                device, is_host, user, ip, port,
                operation, paths, dest_device, dest_path
            )
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Operation timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _delete_files(run_cmd, paths: List[str]) -> Dict[str, Any]:
    """Delete files/folders using argument list (no shell)."""
    for p in paths:
        # Use rm with explicit arguments, no shell
        success, err = run_cmd(["rm", "-rf", "--", p])
        if not success:
            return {"success": False, "error": f"Failed to delete {p}: {err}"}
    return {"success": True}


def _rename_file(run_cmd, paths: List[str], new_name: Optional[str]) -> Dict[str, Any]:
    """Rename a file/folder using argument list (no shell)."""
    if len(paths) != 1 or not new_name:
        return {"success": False, "error": "Rename requires exactly one file and new name"}
    
    # Validate new name
    if not is_valid_filename(new_name) and not is_valid_folder_name(new_name):
        return {"success": False, "error": "Invalid new name"}
    
    old_path = paths[0]
    parent = '/'.join(paths[0].rstrip('/').split('/')[:-1]) or '/'
    new_path = f"{parent}/{new_name}"
    
    success, err = run_cmd(["mv", "--", old_path, new_path])
    if not success:
        return {"success": False, "error": f"Failed to rename: {err}"}
    return {"success": True}


def _create_folder(run_cmd, paths: List[str], new_name: Optional[str]) -> Dict[str, Any]:
    """Create a new folder using argument list (no shell)."""
    if not new_name:
        return {"success": False, "error": "Folder name required"}
    
    if not is_valid_folder_name(new_name):
        return {"success": False, "error": "Invalid folder name"}
    
    parent = paths[0] if paths else '/'
    folder_path = f"{parent.rstrip('/')}/{new_name}"
    
    success, err = run_cmd(["mkdir", "-p", "--", folder_path])
    if not success:
        return {"success": False, "error": f"Failed to create folder: {err}"}
    return {"success": True}


def _zip_files(
    run_cmd, paths: List[str], is_host: bool, user: str, ip: str, port: int
) -> Dict[str, Any]:
    """Create zip archive from files using argument list (no shell)."""
    if not paths:
        return {"success": False, "error": "No files selected"}

    first_path = paths[0].rstrip('/')
    parent = '/'.join(first_path.split('/')[:-1]) or '/'
    base_name = first_path.split('/')[-1]

    # Check if zip is available
    if is_host:
        result = subprocess.run(["which", "zip"], capture_output=True, text=True)
        use_zip = result.returncode == 0
    else:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-p", str(port), f"{user}@{ip}", "which", "zip"],
            capture_output=True, text=True, timeout=10
        )
        use_zip = result.returncode == 0

    if len(paths) == 1:
        archive_name = f"{base_name}.zip" if use_zip else f"{base_name}.tar.gz"
    else:
        archive_name = f"archive_{int(time.time())}.zip" if use_zip else f"archive_{int(time.time())}.tar.gz"

    archive_path = f"{parent}/{archive_name}"

    # Get relative names for archiving
    rel_names = [p.split('/')[-1] for p in paths]

    # Build command as argument list
    if use_zip:
        # zip -r archive.zip file1 file2 ... (in parent directory)
        # We need to cd first, so use a shell-free approach via subprocess with cwd
        if is_host:
            cmd = ["zip", "-r", archive_name] + rel_names
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=parent)
            success = result.returncode == 0
            err = result.stderr
        else:
            # For remote, we need to use a shell command via SSH
            # Construct safely with proper escaping
            safe_names = ' '.join([f"'{sanitize_path(n)}'" for n in rel_names])
            ssh_cmd = f"cd '{sanitize_path(parent)}' && zip -r '{sanitize_path(archive_name)}' {safe_names}"
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-p", str(port), f"{user}@{ip}", ssh_cmd],
                capture_output=True, text=True, timeout=300
            )
            success = result.returncode == 0
            err = result.stderr
    else:
        # tar -czf archive.tar.gz file1 file2 ...
        if is_host:
            cmd = ["tar", "-czf", archive_name] + rel_names
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=parent)
            success = result.returncode == 0
            err = result.stderr
        else:
            safe_names = ' '.join([f"'{sanitize_path(n)}'" for n in rel_names])
            ssh_cmd = f"cd '{sanitize_path(parent)}' && tar -czf '{sanitize_path(archive_name)}' {safe_names}"
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-p", str(port), f"{user}@{ip}", ssh_cmd],
                capture_output=True, text=True, timeout=300
            )
            success = result.returncode == 0
            err = result.stderr
    if not success:
        return {"success": False, "error": f"Failed to create archive: {err}"}
    return {"success": True, "archive": archive_path}


def _transfer_files(
    device: Dict[str, Any], is_host: bool, user: str, ip: str, port: int,
    operation: str, paths: List[str],
    dest_device: Optional[Dict[str, Any]], dest_path: Optional[str]
) -> Dict[str, Any]:
    """Copy or move files between devices using rsync (no shell=True)."""
    if not dest_device or not dest_path:
        return {"success": False, "error": "Destination required"}

    dest_ssh = dest_device.get('ssh', {})
    dest_user = dest_ssh.get('user')
    dest_port = dest_ssh.get('port', 22)
    dest_ip = dest_device.get('ip')
    dest_is_host = dest_device.get('is_host', False)

    if not dest_is_host and not dest_user:
        return {"success": False, "error": "Destination SSH not configured"}

    for src_path in paths:
        # Determine rsync command as argument list
        if is_host and dest_is_host:
            # Local to local
            rsync_cmd = ["rsync", "-a", "--", src_path, f"{dest_path}/"]
            result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=300)
            success, err = result.returncode == 0, result.stderr
        elif is_host and not dest_is_host:
            # Local to remote
            rsync_cmd = [
                "rsync", "-a", "-e", f"ssh -o StrictHostKeyChecking=no -p {dest_port}",
                "--", src_path, f"{dest_user}@{dest_ip}:{dest_path}/"
            ]
            result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=300)
            success, err = result.returncode == 0, result.stderr
        elif not is_host and dest_is_host:
            # Remote to local
            rsync_cmd = [
                "rsync", "-a", "-e", f"ssh -o StrictHostKeyChecking=no -p {port}",
                "--", f"{user}@{ip}:{src_path}", f"{dest_path}/"
            ]
            result = subprocess.run(rsync_cmd, capture_output=True, text=True, timeout=300)
            success, err = result.returncode == 0, result.stderr
        else:
            # Remote to remote - copy through host
            temp_path = f"/tmp/deq_transfer_{int(time.time())}"
            rsync_cmd1 = [
                "rsync", "-a", "-e", f"ssh -o StrictHostKeyChecking=no -p {port}",
                "--", f"{user}@{ip}:{src_path}", f"{temp_path}/"
            ]
            result = subprocess.run(rsync_cmd1, capture_output=True, text=True, timeout=300)
            success, err = result.returncode == 0, result.stderr
            
            if success:
                src_name = src_path.rstrip('/').split('/')[-1]
                rsync_cmd2 = [
                    "rsync", "-a", "-e", f"ssh -o StrictHostKeyChecking=no -p {dest_port}",
                    "--", f"{temp_path}/{src_name}", f"{dest_user}@{dest_ip}:{dest_path}/"
                ]
                result = subprocess.run(rsync_cmd2, capture_output=True, text=True, timeout=300)
                success, err = result.returncode == 0, result.stderr
                # Cleanup temp
                subprocess.run(["rm", "-rf", "--", temp_path], capture_output=True, timeout=30)

        if not success:
            return {"success": False, "error": f"Failed to {operation} {src_path}: {err}"}

        # For move, delete source after successful copy
        if operation == 'move':
            if is_host:
                del_result = subprocess.run(["rm", "-rf", "--", src_path], capture_output=True, text=True, timeout=60)
                del_success = del_result.returncode == 0
                del_err = del_result.stderr
            else:
                del_result = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
                     "-p", str(port), f"{user}@{ip}", "rm", "-rf", "--", src_path],
                    capture_output=True, text=True, timeout=60
                )
                del_success = del_result.returncode == 0
                del_err = del_result.stderr
            
            if not del_success:
                return {"success": False, "error": f"Copied but failed to delete source: {del_err}"}

    return {"success": True}


def get_file_for_download(device: Dict[str, Any], file_path: str) -> tuple:
    """
    Get file content for download.
    Returns (content_bytes, filename, error).
    """
    try:
        if device.get('is_host'):
            if not os.path.isfile(file_path):
                return None, None, "Not a file"
            with open(file_path, 'rb') as f:
                content = f.read()
            filename = os.path.basename(file_path)
            return content, filename, None
        else:
            ssh_config = device.get('ssh', {})
            user = ssh_config.get('user')
            port = ssh_config.get('port', 22)
            ip = device.get('ip')

            if not user:
                return None, None, "SSH not configured"

            # Use cat to get file content
            result = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-p", str(port),
                 f"{user}@{ip}", f"cat '{file_path}'"],
                capture_output=True, timeout=60
            )

            if result.returncode != 0:
                return None, None, "Failed to read file"

            filename = file_path.rstrip('/').split('/')[-1]
            return result.stdout, filename, None

    except subprocess.TimeoutExpired:
        return None, None, "Timeout"
    except Exception as e:
        return None, None, str(e)


def upload_file(
    device: Dict[str, Any], dest_path: str, filename: str, content: bytes
) -> Dict[str, Any]:
    """
    Upload file content to device.
    Returns {"success": bool, "error": str}.
    """
    try:
        full_path = os.path.join(dest_path, filename)

        if device.get('is_host'):
            # Direct write for host
            with open(full_path, 'wb') as f:
                f.write(content)
            return {"success": True}
        else:
            # Remote: write temp file, then SCP
            ssh_config = device.get('ssh', {})
            user = ssh_config.get('user')
            port = ssh_config.get('port', 22)
            ip = device.get('ip')

            if not user:
                return {"success": False, "error": "SSH not configured"}

            # Write to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                # SCP to remote
                result = subprocess.run(
                    ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port),
                     tmp_path, f"{user}@{ip}:{full_path}"],
                    capture_output=True, timeout=600
                )
                if result.returncode != 0:
                    return {"success": False, "error": result.stderr.decode().strip() or "SCP failed"}
                return {"success": True}
            finally:
                os.unlink(tmp_path)

    except Exception as e:
        return {"success": False, "error": str(e)}
