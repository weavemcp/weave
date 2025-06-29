"""MCP proxy handler using FastMCP for STDIO to HTTP bridging"""

import asyncio
import logging
from typing import Optional
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from .api_client import WeaveMCPClient, WeaveMCPAPIError
from .config import WeaveMCPConfig, ConfigError


class MCPProxyError(Exception):
    """Exception raised for MCP proxy errors"""

    pass


class AuthenticatedHTTPTransport(StreamableHttpTransport):
    """HTTP transport with Bearer token authentication"""

    def __init__(self, url: str, token: str, **kwargs):
        """
        Initialize HTTP transport with Bearer authentication

        Args:
            url: FastMCP proxy endpoint URL
            token: Bearer token for authentication
            **kwargs: Additional StreamableHttpTransport arguments
        """
        # Add Authorization header and Weave CLI headers to all requests
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Weave-Version"] = "1.0.0"
        headers["User-Agent"] = "Weave-CLI/1.0.0"
        headers["Content-Type"] = "application/json"
        kwargs["headers"] = headers

        super().__init__(url, **kwargs)


class MCPProxyClient:
    """Client for connecting to FastMCP proxy with authentication"""

    def __init__(self, endpoint_url: str, token: str):
        """
        Initialize MCP proxy client

        Args:
            endpoint_url: FastMCP proxy endpoint URL
            token: Bearer token for authentication
        """
        self.endpoint_url = endpoint_url
        self.token = token
        self._client: Optional[Client] = None
        self._logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for proxy operations"""
        logger = logging.getLogger("weavemcp.proxy")

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        # Create log file if it doesn't exist
        log_path = Path.home() / ".weavemcp" / "proxy.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure file handler with rotation
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Prevent duplicate logs

        return logger

    async def create_client(self) -> Client:
        """
        Create FastMCP client with authenticated HTTP transport

        Returns:
            Configured FastMCP Client

        Raises:
            MCPProxyError: If client creation fails
        """
        try:
            # Create authenticated HTTP transport
            transport = AuthenticatedHTTPTransport(
                url=self.endpoint_url, token=self.token
            )

            # Create FastMCP client
            self._client = Client(transport=transport)

            self._logger.info(f"Created MCP client for endpoint: {self.endpoint_url}")
            return self._client

        except Exception as e:
            self._logger.error(f"Failed to create MCP client: {e}")
            raise MCPProxyError(f"Failed to create MCP client: {e}")

    async def close(self):
        """Close the MCP client connection"""
        if self._client:
            try:
                await self._client.close()
                self._logger.info("Closed MCP client connection")
            except Exception as e:
                self._logger.error(f"Error closing MCP client: {e}")


async def get_proxy_client(
    server_url: Optional[str] = None,
    token: Optional[str] = None,
    server_alias: Optional[str] = None,
) -> MCPProxyClient:
    """
    Get MCP proxy client with authentication from config

    Args:
        server_url: Optional server URL override
        token: Optional token override
        server_alias: Optional server alias to use

    Returns:
        Configured MCPProxyClient

    Raises:
        MCPProxyError: If configuration or endpoint fetch fails
    """
    try:
        # Get authentication configuration
        config = WeaveMCPConfig()

        if server_alias:
            servers = config.list_servers()
            alias_server = next(
                (s for s in servers if s["alias"] == server_alias), None
            )
            if not alias_server:
                raise MCPProxyError(f"Server alias '{server_alias}' not found")
            server_url = alias_server["url"]
            token = config.get_token(server_alias)
        elif server_url and token:
            # Both provided explicitly
            pass
        else:
            # Use current server
            current_server = config.get_current_server()
            server_url = current_server["url"]
            token = current_server["token"]

        if not token:
            raise MCPProxyError(
                "No authentication token found. Run 'weave login' first."
            )

        # Get proxy endpoint from WeaveMCP API
        client = WeaveMCPClient(server_url, token)
        connection_details = client.get_server_connection_details()

        if not connection_details:
            raise MCPProxyError(
                "No default virtual server found. Run 'weave setup' first."
            )

        # Use the proxy endpoint instead of the direct MCP endpoint
        server_id = connection_details["server_id"]
        endpoint_url = f"{server_url}/proxy/{server_id}/"
        access_token = token  # Use the user's API token for proxy access

        # Create proxy client
        proxy_client = MCPProxyClient(endpoint_url, access_token)

        return proxy_client

    except WeaveMCPAPIError as e:
        if "404" in str(e) or "not found" in str(e).lower():
            raise MCPProxyError(
                "No default virtual server found. Run 'weave setup' first."
            )
        elif "401" in str(e) or "unauthorized" in str(e).lower():
            raise MCPProxyError("Authentication failed. Run 'weave login' first.")
        elif "403" in str(e) or "forbidden" in str(e).lower():
            raise MCPProxyError(
                "Access denied. Check your permissions or run 'weave login' again."
            )
        else:
            raise MCPProxyError(f"WeaveMCP API error: {e}")
    except ConfigError as e:
        raise MCPProxyError(f"Configuration error: {e}")
    except Exception as e:
        raise MCPProxyError(f"Unexpected error: {e}")
