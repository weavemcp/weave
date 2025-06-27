"""WeaveMCP API client for fetching virtual servers"""

import json
import requests
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin


class WeaveMCPAPIError(Exception):
    """Exception raised for WeaveMCP API errors"""

    pass


class WeaveMCPClient:
    """Client for communicating with WeaveMCP API"""

    def __init__(
        self, base_url: str = "https://weavemcp.dev", api_token: Optional[str] = None
    ):
        """
        Initialize the WeaveMCP API client

        Args:
            base_url: Base URL of the WeaveMCP instance
            api_token: Bearer token for API authentication
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

        if api_token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {api_token}",
                    "Content-Type": "application/json",
                }
            )

    def set_api_token(self, token: str) -> None:
        """Set API bearer token for authentication"""
        self.session.headers.update(
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )

    def get_user_organizations(self) -> Dict:
        """
        Get list of organizations the user is a member of

        Returns:
            Dict containing organizations list and default organization

        Raises:
            WeaveMCPAPIError: If the API request fails
        """
        url = urljoin(self.base_url, "/api/user/organizations/")

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise WeaveMCPAPIError(
                    f"API error: {data.get('error', 'Unknown error')}"
                )

            return data

        except requests.RequestException as e:
            raise WeaveMCPAPIError(f"Failed to fetch organizations: {e}")
        except json.JSONDecodeError as e:
            raise WeaveMCPAPIError(f"Invalid JSON response: {e}")

    def get_default_virtual_server(self) -> Dict:
        """
        Get the user's default virtual MCP server configuration

        Returns:
            Dict containing virtual server details and downstream servers

        Raises:
            WeaveMCPAPIError: If the API request fails or no server found
        """
        url = urljoin(self.base_url, "/api/user/default-server/")

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise WeaveMCPAPIError(
                    f"API error: {data.get('error', 'Unknown error')}"
                )

            return data

        except requests.RequestException as e:
            raise WeaveMCPAPIError(f"Failed to fetch default server: {e}")
        except json.JSONDecodeError as e:
            raise WeaveMCPAPIError(f"Invalid JSON response: {e}")

    def test_connection(self) -> Tuple[bool, Optional[str]]:
        """
        Test if the client can successfully connect to WeaveMCP

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Try to get organizations as a simple connectivity test
            data = self.get_user_organizations()
            return True, None
        except WeaveMCPAPIError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def get_server_connection_details(self) -> Optional[Dict]:
        """
        Get connection details for configuring Claude Desktop

        Returns:
            Dict with connection details or None if no server found
        """
        try:
            server_data = self.get_default_virtual_server()
            server = server_data.get("server")

            if not server:
                return None

            return {
                "name": f"weavemcp-{server['organization']['slug']}",
                "endpoint_url": server["endpoint_url"],
                "access_token": server["access_token"],
                "server_id": server["id"],
                "organization": server["organization"]["slug"],
                "description": f"WeaveMCP virtual server for {server['organization']['name']}",
                "downstream_count": len(server.get("downstream_servers", [])),
            }

        except WeaveMCPAPIError:
            return None
