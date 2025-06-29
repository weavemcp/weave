"""Mock objects and utilities for testing"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from unittest.mock import Mock, AsyncMock
import responses

from weave.api_client import WeaveMCPClient
from weave.mcp_proxy import MCPProxyClient
from .test_data import (
    SAMPLE_ORGANIZATIONS_RESPONSE,
    SAMPLE_DEFAULT_SERVER_RESPONSE,
    SAMPLE_CONNECTION_DETAILS,
    ERROR_RESPONSES,
)


class MockWeaveMCPClient:
    """Mock WeaveMCP API client for testing"""

    def __init__(
        self,
        base_url: str = "https://atlaslabs.weavemcp.app",
        api_token: Optional[str] = None,
    ):
        self.base_url = base_url
        self.api_token = api_token
        self._should_fail = False
        self._fail_reason = "unauthorized"

    def set_failure_mode(self, should_fail: bool, reason: str = "unauthorized"):
        """Configure client to simulate failures"""
        self._should_fail = should_fail
        self._fail_reason = reason

    def test_connection(self) -> Tuple[bool, Optional[str]]:
        """Mock connection test"""
        if self._should_fail:
            error_msg = ERROR_RESPONSES.get(self._fail_reason, {}).get(
                "error", "Connection failed"
            )
            return False, error_msg
        return True, None

    def get_user_organizations(self) -> Dict:
        """Mock get user organizations"""
        if self._should_fail:
            from weave.api_client import WeaveMCPAPIError

            error = ERROR_RESPONSES.get(
                self._fail_reason, ERROR_RESPONSES["unauthorized"]
            )
            raise WeaveMCPAPIError(error["error"])
        return SAMPLE_ORGANIZATIONS_RESPONSE

    def get_default_virtual_server(self) -> Dict:
        """Mock get default virtual server"""
        if self._should_fail:
            from weave.api_client import WeaveMCPAPIError

            error = ERROR_RESPONSES.get(self._fail_reason, ERROR_RESPONSES["not_found"])
            raise WeaveMCPAPIError(error["error"])
        return SAMPLE_DEFAULT_SERVER_RESPONSE

    def get_server_connection_details(self) -> Optional[Dict]:
        """Mock get server connection details"""
        if self._should_fail:
            return None
        return SAMPLE_CONNECTION_DETAILS


class MockMCPProxyClient:
    """Mock MCP proxy client for testing"""

    def __init__(self, endpoint_url: str, token: str):
        self.endpoint_url = endpoint_url
        self.token = token
        self._client = None
        self._should_fail = False

    def set_failure_mode(self, should_fail: bool):
        """Configure client to simulate failures"""
        self._should_fail = should_fail

    async def create_client(self):
        """Mock create client"""
        if self._should_fail:
            from weave.mcp_proxy import MCPProxyError

            raise MCPProxyError("Failed to create MCP client")

        # Return a mock FastMCP client
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        self._client = mock_client
        return mock_client

    async def close(self):
        """Mock close client"""
        pass


class MockAuthServer:
    """Mock authentication server for testing OAuth flow"""

    def __init__(self, port: int = 8080):
        self.port = port
        self.token = "test_token_123456789"
        self.server_url = "https://atlaslabs.weavemcp.app"
        self._should_timeout = False

    def set_timeout_mode(self, should_timeout: bool):
        """Configure server to simulate timeout"""
        self._should_timeout = should_timeout

    def start(self) -> int:
        """Mock start server"""
        return self.port

    def wait_for_callback(
        self, timeout: int = 300
    ) -> Tuple[Optional[str], Optional[str]]:
        """Mock wait for OAuth callback"""
        if self._should_timeout:
            return None, None
        return self.token, self.server_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockFastMCP:
    """Mock FastMCP server for testing proxy functionality"""

    def __init__(self, client):
        self.client = client
        self._should_fail = False

    def set_failure_mode(self, should_fail: bool):
        """Configure to simulate failures"""
        self._should_fail = should_fail

    async def run_async(self, transport: str = "stdio"):
        """Mock run async"""
        if self._should_fail:
            raise RuntimeError("FastMCP server failed")

        # Simulate running server
        await asyncio.sleep(0.1)
        return True

    @classmethod
    def as_proxy(cls, client, name: str = "Mock Proxy"):
        """Mock FastMCP.as_proxy method"""
        return cls(client)


def setup_responses_for_api_testing(base_url: str = "https://atlaslabs.weavemcp.app"):
    """Setup responses mock for API testing"""

    # Successful responses
    responses.add(
        responses.GET,
        f"{base_url}/api/user/organizations/",
        json=SAMPLE_ORGANIZATIONS_RESPONSE,
        status=200,
    )

    responses.add(
        responses.GET,
        f"{base_url}/api/user/default-server/",
        json=SAMPLE_DEFAULT_SERVER_RESPONSE,
        status=200,
    )

    # Error responses
    responses.add(
        responses.GET,
        f"{base_url}/api/user/organizations/",
        json=ERROR_RESPONSES["unauthorized"],
        status=401,
        match=[
            responses.matchers.header_matcher({"Authorization": "Bearer invalid_token"})
        ],
    )

    responses.add(
        responses.GET,
        f"{base_url}/api/user/default-server/",
        json=ERROR_RESPONSES["not_found"],
        status=404,
        match=[
            responses.matchers.header_matcher(
                {"Authorization": "Bearer no_server_token"}
            )
        ],
    )


def create_mock_config_file(config_dir: Path, config_data: Dict):
    """Create a mock configuration file"""
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps(config_data, indent=2))
    return config_file


def create_mock_claude_config(config_path: Path, config_data: Dict):
    """Create a mock Claude Desktop configuration file"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config_data, indent=2))
    return config_path
