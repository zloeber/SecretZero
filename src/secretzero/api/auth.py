"""Authentication and security for the API."""

import hashlib
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

# API Key authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key_from_env() -> Optional[str]:
    """Get the API key from environment variable."""
    return os.environ.get("SECRETZERO_API_KEY")


def generate_api_key() -> str:
    """Generate a random API key."""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash an API key for comparison."""
    return hashlib.sha256(api_key.encode()).hexdigest()


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify the API key from the request header.

    Args:
        api_key: The API key from the request header.

    Returns:
        The verified API key.

    Raises:
        HTTPException: If the API key is invalid or missing.
    """
    # If no API key is configured, allow all requests (insecure mode for testing)
    env_api_key = get_api_key_from_env()
    if env_api_key is None:
        # Running in insecure mode
        return "insecure-mode"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Compare hashes for timing attack resistance
    provided_hash = hash_api_key(api_key)
    expected_hash = hash_api_key(env_api_key)

    if not secrets.compare_digest(provided_hash, expected_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


# Dependency for routes that require authentication
RequireAuth = Depends(verify_api_key)
