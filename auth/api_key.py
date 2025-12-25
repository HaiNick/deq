"""
DeQ Auth - API Key Authentication
Secure API key generation, hashing, and validation.
"""

import hashlib
import hmac
import secrets
import os
from typing import Optional, Dict, Any

# API key configuration
API_KEY_LENGTH = 32  # 256 bits of entropy
API_KEY_PREFIX = "deq_"


def generate_api_key() -> str:
    """
    Generate a new secure API key.
    Returns the plaintext key (show once to user, store hash only).
    """
    key = secrets.token_urlsafe(API_KEY_LENGTH)
    return f"{API_KEY_PREFIX}{key}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.
    Uses SHA-256 with a consistent salt derived from the key prefix.
    """
    # Remove prefix for hashing
    key_body = api_key.replace(API_KEY_PREFIX, "")
    # Use SHA-256 (bcrypt would be better but we're stdlib-only)
    return hashlib.sha256(key_body.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against a stored hash.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not provided_key or not stored_hash:
        return False
    
    provided_hash = hash_api_key(provided_key)
    return hmac.compare_digest(provided_hash, stored_hash)


def get_auth_config() -> Dict[str, Any]:
    """
    Get authentication configuration.
    Supports both config file and environment variables.
    """
    from config import get_config
    
    config = get_config()
    auth_config = config.get('auth', {})
    
    # Environment variable overrides
    env_key_hash = os.environ.get('DEQ_API_KEY_HASH')
    if env_key_hash:
        auth_config['api_key_hash'] = env_key_hash
    
    env_enabled = os.environ.get('DEQ_AUTH_ENABLED')
    if env_enabled is not None:
        auth_config['enabled'] = env_enabled.lower() in ('true', '1', 'yes')
    
    return auth_config


def is_auth_enabled() -> bool:
    """Check if authentication is enabled."""
    auth_config = get_auth_config()
    return auth_config.get('enabled', False)


def validate_request_auth(headers: Dict[str, str]) -> tuple[bool, Optional[str]]:
    """
    Validate authentication for an incoming request.
    
    Args:
        headers: HTTP headers dict (case-insensitive keys)
        
    Returns:
        (is_valid, error_message) - error_message is None if valid
    """
    if not is_auth_enabled():
        return True, None
    
    auth_config = get_auth_config()
    stored_hash = auth_config.get('api_key_hash')
    
    if not stored_hash:
        # Auth enabled but no key configured - deny all
        return False, "Authentication not configured"
    
    # Check X-API-Key header
    api_key = headers.get('X-API-Key') or headers.get('x-api-key')
    
    if not api_key:
        # Check Authorization header as fallback (Bearer token)
        auth_header = headers.get('Authorization') or headers.get('authorization')
        if auth_header and auth_header.startswith('Bearer '):
            api_key = auth_header[7:]
    
    if not api_key:
        return False, "API key required"
    
    if not api_key.startswith(API_KEY_PREFIX):
        return False, "Invalid API key format"
    
    if not verify_api_key(api_key, stored_hash):
        return False, "Invalid API key"
    
    return True, None


def setup_api_key() -> Dict[str, str]:
    """
    Generate and store a new API key.
    Returns dict with plaintext key (show once) and hash (for storage).
    """
    plaintext_key = generate_api_key()
    key_hash = hash_api_key(plaintext_key)
    
    return {
        "api_key": plaintext_key,
        "api_key_hash": key_hash,
        "message": "Store this API key securely - it cannot be recovered!"
    }
