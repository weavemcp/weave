"""Tests for proxy server functionality"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, call
from click.testing import CliRunner

from weave.cli import proxy
from weave.config import WeaveMCPConfig, ConfigError
from weave.mcp_proxy import MCPProxyClient, MCPProxyError, get_proxy_client
from weave.proxy_server import ProxyServer, run_proxy_server
from tests.fixtures.test_data import (
    SAMPLE_CONNECTION_DETAILS,
    TEST_API_TOKENS,
    TEST_SERVER_URLS,
)
from tests.fixtures.mocks import MockWeaveMCPClient, MockMCPProxyClient, MockFastMCP


class TestProxyCommand:
    """Test the proxy command functionality"""

    def test_proxy_success(self, mock_config):
        """Test successful proxy startup"""
        runner = CliRunner()

        # Setup config
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.cli.run_proxy_server") as mock_run_proxy:
            mock_run_proxy.return_value = None  # Simulate successful run

            result = runner.invoke(proxy, ["--verbose"])

            assert result.exit_code == 0
            mock_run_proxy.assert_called_once_with(
                server_url=None, token=None, server_alias=None, verbose=True
            )

    def test_proxy_with_explicit_params(self, mock_config):
        """Test proxy with explicit server URL and token"""
        runner = CliRunner()

        with patch("weave.cli.run_proxy_server") as mock_run_proxy:

            result = runner.invoke(
                proxy,
                [
                    "--server-url",
                    TEST_SERVER_URLS["production"],
                    "--token",
                    TEST_API_TOKENS["valid"],
                    "--verbose",
                ],
            )

            assert result.exit_code == 0
            mock_run_proxy.assert_called_once_with(
                server_url=TEST_SERVER_URLS["production"],
                token=TEST_API_TOKENS["valid"],
                server_alias=None,
                verbose=True,
            )

    def test_proxy_with_server_alias(self, mock_config):
        """Test proxy with server alias"""
        runner = CliRunner()

        # Setup multiple servers
        config = WeaveMCPConfig()
        config.add_server(
            "production", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.add_server(
            "staging", TEST_SERVER_URLS["staging"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("production")

        with patch("weave.cli.run_proxy_server") as mock_run_proxy:

            result = runner.invoke(proxy, ["--server", "staging"])

            assert result.exit_code == 0
            mock_run_proxy.assert_called_once_with(
                server_url=None, token=None, server_alias="staging", verbose=False
            )

    def test_proxy_no_authentication(self, mock_config):
        """Test proxy without authentication - should trigger login"""
        runner = CliRunner()

        with (
            patch("weave.cli.run_proxy_server") as mock_run_proxy,
            patch("weave.cli.login") as mock_login,
        ):

            # Mock login to simulate successful authentication
            mock_login.return_value = None

            result = runner.invoke(proxy)

            # Should attempt to run proxy after login
            mock_run_proxy.assert_called_once()

    def test_proxy_keyboard_interrupt(self, mock_config):
        """Test proxy handling keyboard interrupt"""
        runner = CliRunner()

        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.cli.run_proxy_server") as mock_run_proxy:
            mock_run_proxy.side_effect = KeyboardInterrupt()

            result = runner.invoke(proxy, ["--verbose"])

            assert result.exit_code == 0
            assert "Proxy server stopped" in result.output

    def test_proxy_error(self, mock_config):
        """Test proxy with general error"""
        runner = CliRunner()

        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.cli.run_proxy_server") as mock_run_proxy:
            mock_run_proxy.side_effect = MCPProxyError("Connection failed")

            result = runner.invoke(proxy)

            assert result.exit_code == 1
            assert "Proxy error" in result.output


class TestMCPProxyClient:
    """Test MCP proxy client functionality"""

    @pytest.mark.asyncio
    async def test_create_client_success(self):
        """Test successful client creation"""
        client = MCPProxyClient(
            "https://proxy.atlaslabs.weavemcp.app/proxy/test123", "test_token_123"
        )

        with (
            patch("weave.mcp_proxy.AuthenticatedHTTPTransport") as mock_transport,
            patch("weave.mcp_proxy.Client") as mock_client_class,
        ):

            mock_fastmcp_client = AsyncMock()
            mock_client_class.return_value = mock_fastmcp_client

            result = await client.create_client()

            assert result == mock_fastmcp_client
            mock_transport.assert_called_once_with(
                url="https://proxy.atlaslabs.weavemcp.app/proxy/test123",
                token="test_token_123",
            )
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_client_failure(self):
        """Test client creation failure"""
        client = MCPProxyClient("invalid_url", "test_token")

        with patch("weave.mcp_proxy.AuthenticatedHTTPTransport") as mock_transport:
            mock_transport.side_effect = Exception("Transport creation failed")

            with pytest.raises(MCPProxyError) as exc_info:
                await client.create_client()

            assert "Failed to create MCP client" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test client cleanup"""
        client = MCPProxyClient("https://proxy.test.com", "token")

        # Create a mock client
        mock_fastmcp_client = AsyncMock()
        client._client = mock_fastmcp_client

        await client.close()

        mock_fastmcp_client.close.assert_called_once()


class TestProxyServer:
    """Test proxy server functionality"""

    @pytest.mark.asyncio
    async def test_proxy_server_start_success(self):
        """Test successful proxy server startup"""
        mock_proxy_client = MockMCPProxyClient("https://proxy.test.com", "token")
        server = ProxyServer(mock_proxy_client, verbose=True)

        with patch("weave.proxy_server.FastMCP") as mock_fastmcp:
            mock_fastmcp_server = MockFastMCP(None)
            mock_fastmcp.as_proxy.return_value = mock_fastmcp_server

            # Mock the run to complete quickly
            async def mock_run(transport="stdio"):
                await asyncio.sleep(0.01)

            mock_fastmcp_server.run_async = mock_run

            # Start server in a task and stop it quickly
            task = asyncio.create_task(server.start())
            await asyncio.sleep(0.02)  # Let it start
            await server.shutdown()

            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected when shutting down

    @pytest.mark.asyncio
    async def test_proxy_server_client_creation_failure(self):
        """Test proxy server with client creation failure"""
        mock_proxy_client = MockMCPProxyClient("https://proxy.test.com", "token")
        mock_proxy_client.set_failure_mode(True)

        server = ProxyServer(mock_proxy_client)

        with pytest.raises(MCPProxyError) as exc_info:
            await server.start()

        assert "Failed to start proxy server" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_proxy_server_fastmcp_failure(self):
        """Test proxy server with FastMCP failure"""
        mock_proxy_client = MockMCPProxyClient("https://proxy.test.com", "token")
        server = ProxyServer(mock_proxy_client)

        with patch("weave.proxy_server.FastMCP") as mock_fastmcp:
            mock_fastmcp_server = MockFastMCP(None)
            mock_fastmcp_server.set_failure_mode(True)
            mock_fastmcp.as_proxy.return_value = mock_fastmcp_server

            with pytest.raises(MCPProxyError):
                await server.start()


class TestGetProxyClient:
    """Test get_proxy_client function"""

    @pytest.mark.asyncio
    async def test_get_proxy_client_with_config(self, mock_config):
        """Test getting proxy client from saved configuration"""
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.mcp_proxy.WeaveMCPClient") as mock_client_class:
            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            proxy_client = await get_proxy_client()

            assert isinstance(proxy_client, MCPProxyClient)
            assert (
                proxy_client.endpoint_url == SAMPLE_CONNECTION_DETAILS["endpoint_url"]
            )
            assert proxy_client.token == SAMPLE_CONNECTION_DETAILS["access_token"]

    @pytest.mark.asyncio
    async def test_get_proxy_client_with_explicit_params(self, mock_config):
        """Test getting proxy client with explicit parameters"""
        with patch("weave.mcp_proxy.WeaveMCPClient") as mock_client_class:
            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            proxy_client = await get_proxy_client(
                server_url=TEST_SERVER_URLS["production"],
                token=TEST_API_TOKENS["valid"],
            )

            assert isinstance(proxy_client, MCPProxyClient)
            mock_client_class.assert_called_once_with(
                TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
            )

    @pytest.mark.asyncio
    async def test_get_proxy_client_with_server_alias(self, mock_config):
        """Test getting proxy client with server alias"""
        config = WeaveMCPConfig()
        config.add_server(
            "staging", TEST_SERVER_URLS["staging"], TEST_API_TOKENS["valid"]
        )

        with patch("weave.mcp_proxy.WeaveMCPClient") as mock_client_class:
            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            proxy_client = await get_proxy_client(server_alias="staging")

            assert isinstance(proxy_client, MCPProxyClient)
            mock_client_class.assert_called_once_with(
                TEST_SERVER_URLS["staging"], TEST_API_TOKENS["valid"]
            )

    @pytest.mark.asyncio
    async def test_get_proxy_client_no_token(self, mock_config):
        """Test getting proxy client when no token is available"""
        config = WeaveMCPConfig()
        config.add_server("default", TEST_SERVER_URLS["production"])  # No token
        config.set_current_server("default")

        with pytest.raises(MCPProxyError) as exc_info:
            await get_proxy_client()

        assert "No authentication token found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_proxy_client_api_error(self, mock_config):
        """Test getting proxy client with API error"""
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["expired"]
        )
        config.set_current_server("default")

        with patch("weave.mcp_proxy.WeaveMCPClient") as mock_client_class:
            mock_client = MockWeaveMCPClient()
            mock_client.set_failure_mode(True, "not_found")
            mock_client_class.return_value = mock_client

            with pytest.raises(MCPProxyError) as exc_info:
                await get_proxy_client()

            assert "No default virtual server found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_proxy_client_no_server(self, mock_config):
        """Test getting proxy client when no virtual server exists"""
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.mcp_proxy.WeaveMCPClient") as mock_client_class:
            mock_client = MockWeaveMCPClient()
            mock_client.set_failure_mode(True, "not_found")
            mock_client_class.return_value = mock_client

            with pytest.raises(MCPProxyError) as exc_info:
                await get_proxy_client()

            assert "No default virtual server found" in str(exc_info.value)


class TestRunProxyServer:
    """Test run_proxy_server function"""

    @pytest.mark.asyncio
    async def test_run_proxy_server_success(self, mock_config):
        """Test successful proxy server run"""
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with (
            patch("weave.proxy_server.get_proxy_client") as mock_get_client,
            patch("weave.proxy_server.ProxyServer") as mock_server_class,
        ):

            mock_proxy_client = MockMCPProxyClient("https://proxy.test.com", "token")
            mock_get_client.return_value = mock_proxy_client

            mock_server = Mock()
            mock_server.start = AsyncMock()
            mock_server_class.return_value = mock_server

            await run_proxy_server(verbose=True)

            mock_get_client.assert_called_once_with(None, None, None)
            mock_server_class.assert_called_once_with(mock_proxy_client, verbose=True)
            mock_server.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_proxy_server_with_params(self):
        """Test proxy server run with explicit parameters"""
        with (
            patch("weave.proxy_server.get_proxy_client") as mock_get_client,
            patch("weave.proxy_server.ProxyServer") as mock_server_class,
        ):

            mock_proxy_client = MockMCPProxyClient("https://proxy.test.com", "token")
            mock_get_client.return_value = mock_proxy_client

            mock_server = Mock()
            mock_server.start = AsyncMock()
            mock_server_class.return_value = mock_server

            await run_proxy_server(
                server_url=TEST_SERVER_URLS["production"],
                token=TEST_API_TOKENS["valid"],
                server_alias="production",
                verbose=False,
            )

            mock_get_client.assert_called_once_with(
                TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"], "production"
            )

    @pytest.mark.asyncio
    async def test_run_proxy_server_keyboard_interrupt(self, mock_config, capsys):
        """Test proxy server handling keyboard interrupt"""
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with (
            patch("weave.proxy_server.get_proxy_client") as mock_get_client,
            patch("weave.proxy_server.ProxyServer") as mock_server_class,
        ):

            mock_proxy_client = MockMCPProxyClient("https://proxy.test.com", "token")
            mock_get_client.return_value = mock_proxy_client

            mock_server = Mock()
            mock_server.start = AsyncMock(side_effect=KeyboardInterrupt())
            mock_server_class.return_value = mock_server

            await run_proxy_server()

            captured = capsys.readouterr()
            assert "interrupt signal" in captured.err

    @pytest.mark.asyncio
    async def test_run_proxy_server_error(self, mock_config, capsys):
        """Test proxy server error handling"""
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.proxy_server.get_proxy_client") as mock_get_client:
            mock_get_client.side_effect = MCPProxyError("Connection failed")

            # Should exit with code 1
            with pytest.raises(SystemExit) as exc_info:
                await run_proxy_server()

            assert exc_info.value.code == 1

            captured = capsys.readouterr()
            assert "Proxy server error" in captured.err


@pytest.mark.unit
class TestAuthenticatedHTTPTransport:
    """Test authenticated HTTP transport"""

    def test_transport_initialization(self):
        """Test transport initializes with correct headers"""
        from weave.mcp_proxy import AuthenticatedHTTPTransport

        with patch("weave.mcp_proxy.StreamableHttpTransport.__init__") as mock_init:
            mock_init.return_value = None  # Mock successful initialization

            transport = AuthenticatedHTTPTransport(
                "https://proxy.test.com", "test_token_123"
            )

            # Verify __init__ was called with Authorization header
            call_args = mock_init.call_args
            assert call_args[0][0] == "https://proxy.test.com"  # URL argument
            assert "headers" in call_args[1]
            assert call_args[1]["headers"]["Authorization"] == "Bearer test_token_123"

    def test_transport_preserves_existing_headers(self):
        """Test transport preserves existing headers while adding auth"""
        from weave.mcp_proxy import AuthenticatedHTTPTransport

        with patch("weave.mcp_proxy.StreamableHttpTransport.__init__") as mock_init:
            mock_init.return_value = None

            existing_headers = {"X-Custom": "value"}
            transport = AuthenticatedHTTPTransport(
                "https://proxy.test.com", "test_token_123", headers=existing_headers
            )

            call_args = mock_init.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer test_token_123"
            assert headers["X-Custom"] == "value"
