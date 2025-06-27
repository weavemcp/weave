"""Utility functions for the SuperMCP setup agent"""

import json
import os
import webbrowser
from typing import Dict, Optional
from urllib.parse import urljoin


def open_token_page(base_url: str) -> str:
    """
    Open the SuperMCP API token management page in the user's browser

    Args:
        base_url: Base URL of the SuperMCP instance

    Returns:
        The URL that was opened
    """
    token_url = urljoin(base_url, "/api-tokens/")
    webbrowser.open(token_url)
    return token_url


def prompt_for_api_token() -> str:
    """
    Prompt user to enter their API token

    Returns:
        API token entered by user
    """
    print("\nTo configure Claude Desktop with SuperMCP, you need an API token.")
    print("1. Log in to SuperMCP in your browser")
    print("2. Go to API Tokens in your profile settings")
    print(
        "3. Create a new token with 'read servers' and 'read organizations' permissions"
    )
    print("4. Copy the token and paste it below")
    print()

    token = input("Enter your SuperMCP API token: ").strip()

    if not token:
        raise ValueError("API token cannot be empty")

    return token


def format_server_info(connection_details: Dict) -> str:
    """
    Format server connection details for display

    Args:
        connection_details: Server connection details

    Returns:
        Formatted string for display
    """
    return f"""
Server Name: {connection_details['name']}
Organization: {connection_details['organization']}
Endpoint: {connection_details['endpoint_url']}
Downstream Servers: {connection_details['downstream_count']}
Description: {connection_details['description']}
"""


def validate_base_url(url: str) -> str:
    """
    Validate and normalize a base URL

    Args:
        url: URL to validate

    Returns:
        Normalized URL

    Raises:
        ValueError: If URL is invalid
    """
    if not url:
        raise ValueError("URL cannot be empty")

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    # Remove trailing slash
    url = url.rstrip("/")

    return url


def save_config_cache(
    config_data: Dict, cache_file: str = "~/.supermcp_cache.json"
) -> None:
    """
    Save configuration data to cache file

    Args:
        config_data: Configuration data to save
        cache_file: Path to cache file
    """
    cache_path = os.path.expanduser(cache_file)

    try:
        with open(cache_path, "w") as f:
            json.dump(config_data, f, indent=2)
    except Exception:
        # Silently fail if cache can't be saved
        pass


def load_config_cache(cache_file: str = "~/.supermcp_cache.json") -> Optional[Dict]:
    """
    Load configuration data from cache file

    Args:
        cache_file: Path to cache file

    Returns:
        Cached configuration data or None
    """
    cache_path = os.path.expanduser(cache_file)

    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def validate_api_token(token: str) -> bool:
    """
    Basic validation of API token format

    Args:
        token: API token to validate

    Returns:
        True if token format looks valid
    """
    if not token:
        return False

    # Basic validation - should be 64 character alphanumeric string
    if len(token) != 64:
        return False

    return token.isalnum()


def get_auth_instructions(base_url: str) -> str:
    """
    Get formatted instructions for obtaining an API token

    Args:
        base_url: Base URL of SuperMCP instance

    Returns:
        Formatted instructions string
    """
    token_url = urljoin(base_url, "/api-tokens/")

    return f"""
To get your SuperMCP API token:

1. Open {base_url} in your browser
2. Log in to your SuperMCP account
3. Go to {token_url}
4. Click "Create New Token"
5. Give it a name like "Claude Desktop Setup"
6. Ensure both "Read Servers" and "Read Organizations" permissions are enabled
7. Click "Create Token"
8. Copy the generated token

The token will only be shown once, so make sure to copy it immediately.
"""
