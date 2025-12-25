"""
DeQ Middleware - Security Headers and Request Validation
Defense-in-depth measures for HTTP handling.
"""

from typing import Dict, Optional

# Maximum request body size (50MB for file uploads)
MAX_REQUEST_SIZE = 50 * 1024 * 1024

# Maximum URL length
MAX_URL_LENGTH = 4096

# Maximum header count
MAX_HEADER_COUNT = 100


def get_security_headers() -> Dict[str, str]:
    """
    Get security headers to include in all responses.
    Following OWASP recommendations.
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
        # CSP is relaxed to allow inline scripts for SPA
        # In production, consider nonces or hashes
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
    }


def get_cors_headers(origin: Optional[str] = None) -> Dict[str, str]:
    """
    Get CORS headers for API responses.
    In production, restrict to specific origins.
    """
    return {
        "Access-Control-Allow-Origin": origin or "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key, Authorization",
        "Access-Control-Max-Age": "86400",  # 24 hours
    }


def validate_request_size(content_length: int) -> tuple[bool, Optional[str]]:
    """
    Validate request body size.
    
    Returns:
        (is_valid, error_message)
    """
    if content_length < 0:
        return False, "Invalid Content-Length"
    
    if content_length > MAX_REQUEST_SIZE:
        return False, f"Request too large. Maximum size is {MAX_REQUEST_SIZE // (1024*1024)}MB"
    
    return True, None


def validate_url_length(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL length to prevent DoS.
    
    Returns:
        (is_valid, error_message)
    """
    if len(url) > MAX_URL_LENGTH:
        return False, "URL too long"
    
    return True, None


def sanitize_header_value(value: str) -> str:
    """
    Sanitize header values to prevent header injection.
    Removes newlines and other control characters.
    """
    # Remove any characters that could enable header injection
    return ''.join(c for c in value if c.isprintable() and c not in '\r\n')
