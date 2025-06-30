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
        self, base_url: str = "https://weavemcp.com", api_token: Optional[str] = None
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

    def mcp_tools_list(self, server_id: Optional[str] = None) -> Dict:
        """
        Get list of available MCP tools from the virtual server using JSON-RPC MCP protocol

        Args:
            server_id: Optional specific server ID, uses default if not provided

        Returns:
            Dict containing the tools/list response
        """
        if not server_id:
            # Get default server
            server_data = self.get_default_virtual_server()
            server = server_data.get("server")
            if not server:
                raise WeaveMCPAPIError("No default virtual server found")
            server_id = server["id"]

        # Use the proxy endpoint for MCP JSON-RPC requests
        url = urljoin(self.base_url, f"/proxy/{server_id}/")

        # Create JSON-RPC request for tools/list
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        try:
            response = self.session.post(url, json=jsonrpc_request)
            response.raise_for_status()

            result = response.json()

            # Check for JSON-RPC error
            if "error" in result:
                raise WeaveMCPAPIError(f"MCP error: {result['error']}")

            return result
        except requests.exceptions.RequestException as e:
            raise WeaveMCPAPIError(f"HTTP request failed: {e}")
        except json.JSONDecodeError as e:
            raise WeaveMCPAPIError(f"Invalid JSON response: {e}")

    def mcp_tools_call(
        self, tool_name: str, arguments: Dict, server_id: Optional[str] = None
    ) -> Dict:
        """
        Call an MCP tool on the virtual server using JSON-RPC MCP protocol

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            server_id: Optional specific server ID, uses default if not provided

        Returns:
            Dict containing the tools/call response
        """
        if not server_id:
            # Get default server
            server_data = self.get_default_virtual_server()
            server = server_data.get("server")
            if not server:
                raise WeaveMCPAPIError("No default virtual server found")
            server_id = server["id"]

        # Use the proxy endpoint for MCP JSON-RPC requests
        url = urljoin(self.base_url, f"/proxy/{server_id}/")

        # Create JSON-RPC request for tools/call
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        try:
            response = self.session.post(url, json=jsonrpc_request)
            response.raise_for_status()

            result = response.json()

            # Check for JSON-RPC error
            if "error" in result:
                raise WeaveMCPAPIError(f"MCP error: {result['error']}")

            return result
        except requests.exceptions.RequestException as e:
            raise WeaveMCPAPIError(f"HTTP request failed: {e}")
        except json.JSONDecodeError as e:
            raise WeaveMCPAPIError(f"Invalid JSON response: {e}")
