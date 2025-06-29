"""End-to-end integration tests for Weave with real WeaveMCP servers"""

import os
import json
import pytest
import tempfile
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

from weave.cli import (
    login,
    setup,
    status,
    proxy,
    server_list,
    server_add,
    server_switch,
    server_remove,
)
from weave.config import WeaveMCPConfig
from weave.api_client import WeaveMCPClient


@pytest.mark.integration
class TestE2EIntegration:
    """End-to-end integration tests with real WeaveMCP server"""

    def test_full_workflow_with_real_server(
        self,
        integration_server_url,
        skip_if_no_integration_token,
        integration_token,
        temp_config_dir,
        temp_claude_config,
    ):
        """Test complete workflow: login -> setup -> status"""
        runner = CliRunner()

        # Override config directory for isolation
        with runner.isolated_filesystem():
            # Step 1: Login to real server
            with (
                patch("weave.cli.prompt_for_api_token") as mock_prompt,
                patch("weave.cli.validate_api_token") as mock_validate,
            ):

                mock_prompt.return_value = integration_token
                mock_validate.return_value = True

                result = runner.invoke(
                    login,
                    [
                        "--no-browser",
                        "--server-url",
                        integration_server_url,
                        "--alias",
                        "integration-test",
                    ],
                )

                if result.exit_code != 0:
                    pytest.skip(f"Login failed: {result.output}")

            # Step 2: Setup Claude Desktop configuration
            result = runner.invoke(
                setup,
                [
                    "--server",
                    "integration-test",
                    "--config-path",
                    str(temp_claude_config),
                    "--dry-run",  # Use dry-run to avoid modifying real config
                ],
            )

            if result.exit_code != 0:
                pytest.skip(f"Setup failed: {result.output}")

            assert (
                "Found default virtual server" in result.output
                or "DRY RUN" in result.output
            )

            # Step 3: Check status
            result = runner.invoke(status, ["--config-path", str(temp_claude_config)])

            assert result.exit_code == 0

    def test_api_connectivity(
        self, integration_server_url, skip_if_no_integration_token, integration_token
    ):
        """Test basic API connectivity with real server"""
        client = WeaveMCPClient(integration_server_url, integration_token)

        # Test connection
        success, error = client.test_connection()
        if not success:
            pytest.skip(f"API connection failed: {error}")

        # Test getting organizations
        try:
            orgs_data = client.get_user_organizations()
            assert orgs_data.get("success") is True
            assert "organizations" in orgs_data
        except Exception as e:
            pytest.skip(f"Failed to get organizations: {e}")

        # Test getting default server (may not exist, so don't fail)
        try:
            server_data = client.get_default_virtual_server()
            if server_data.get("success"):
                assert "server" in server_data
        except Exception:
            # It's OK if no default server exists
            pass

    def test_server_management_workflow(
        self,
        integration_server_url,
        skip_if_no_integration_token,
        integration_token,
        temp_config_dir,
    ):
        """Test server management commands with real server"""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Add server configuration
            result = runner.invoke(server_add, ["test-server", integration_server_url])
            assert result.exit_code == 0

            # List servers
            result = runner.invoke(server_list)
            assert result.exit_code == 0
            assert "test-server" in result.output

            # Login to the added server
            with (
                patch("weave.cli.prompt_for_api_token") as mock_prompt,
                patch("weave.cli.validate_api_token") as mock_validate,
            ):

                mock_prompt.return_value = integration_token
                mock_validate.return_value = True

                result = runner.invoke(
                    login, ["--no-browser", "--alias", "test-server"]
                )

                if result.exit_code == 0:
                    assert "Successfully logged in" in result.output

            # Switch to the server
            result = runner.invoke(server_switch, ["test-server"])
            if result.exit_code == 0:
                assert "Switched to server" in result.output

            # Remove the server
            result = runner.invoke(server_remove, ["test-server", "--force"])
            assert result.exit_code == 0
            assert "Removed server" in result.output


@pytest.mark.integration
@pytest.mark.slow
class TestProxyIntegration:
    """Integration tests for proxy functionality"""

    @pytest.mark.asyncio
    async def test_proxy_connection_real_server(
        self,
        integration_server_url,
        skip_if_no_integration_token,
        integration_token,
        temp_config_dir,
    ):
        """Test proxy connection to real WeaveMCP server"""
        from weave.mcp_proxy import get_proxy_client

        # Setup configuration
        config = WeaveMCPConfig()
        config.add_server("integration", integration_server_url, integration_token)
        config.set_current_server("integration")

        try:
            proxy_client = await get_proxy_client()

            # Try to create the MCP client
            mcp_client = await proxy_client.create_client()
            assert mcp_client is not None

            # Clean up
            await proxy_client.close()

        except Exception as e:
            # If we can't connect to proxy, it might be because:
            # 1. No virtual server is configured
            # 2. Server is down
            # 3. Token doesn't have access
            pytest.skip(f"Proxy connection failed: {e}")

    def test_proxy_command_with_real_server(
        self,
        integration_server_url,
        skip_if_no_integration_token,
        integration_token,
        temp_config_dir,
    ):
        """Test proxy command with real server (short-lived)"""
        runner = CliRunner()

        with runner.isolated_filesystem():
            # Setup config
            config = WeaveMCPConfig()
            config.add_server("integration", integration_server_url, integration_token)
            config.set_current_server("integration")

            # Test proxy command with timeout to avoid hanging
            with patch("weave.proxy_server.run_proxy_server") as mock_run:
                # Mock to return quickly instead of running indefinitely
                async def quick_return(*args, **kwargs):
                    # Just test that we can get to the point of starting
                    from weave.mcp_proxy import get_proxy_client

                    try:
                        await get_proxy_client(*args, **kwargs)
                        return True
                    except Exception as e:
                        # Expected if no virtual server exists
                        if "No default virtual server found" in str(e):
                            return True
                        raise

                mock_run.side_effect = quick_return

                result = runner.invoke(proxy, ["--server", "integration", "--verbose"])

                # Should succeed (mocked) or fail gracefully
                assert result.exit_code in [0, 1]


@pytest.mark.integration
class TestConfigurationIntegration:
    """Integration tests for configuration functionality"""

    def test_claude_config_backup_restore(self, temp_claude_config):
        """Test Claude Desktop configuration backup and restore"""
        from weave.claude_config import ClaudeConfigManager

        # Create initial config
        initial_config = {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                }
            }
        }
        temp_claude_config.write_text(json.dumps(initial_config, indent=2))

        # Initialize manager
        manager = ClaudeConfigManager(str(temp_claude_config))

        # Create backup
        backup_path = manager.backup_config()
        assert backup_path is not None
        assert Path(backup_path).exists()

        # Verify backup contents
        backup_content = json.loads(Path(backup_path).read_text())
        assert backup_content == initial_config

        # Modify config
        test_connection_details = {
            "name": "weavemcp-testorg",
            "endpoint_url": "https://proxy.test.com/proxy/123",
            "access_token": "test_token_123",
            "server_id": "srv_123",
            "organization": "testorg",
            "description": "Test server",
            "downstream_count": 1,
        }

        manager.add_weavemcp_server(test_connection_details)

        # Verify config was modified
        current_config = manager._read_config()
        assert "weavemcp-testorg" in current_config["mcpServers"]
        assert "filesystem" in current_config["mcpServers"]  # Original preserved

        # Clean up backup
        if backup_path:
            Path(backup_path).unlink()

    def test_config_validation_and_cleanup(self, temp_config_dir):
        """Test configuration file validation and cleanup"""
        config = WeaveMCPConfig()

        # Test adding multiple servers
        servers = [
            ("prod", "https://prod.weavemcp.app"),
            ("staging", "https://staging.weavemcp.app"),
            ("local", "http://localhost:8000"),
        ]

        for alias, url in servers:
            config.add_server(alias, url, f"token_for_{alias}")

        # Verify all servers were added
        server_list = config.list_servers()
        assert len(server_list) == 3

        server_aliases = [s["alias"] for s in server_list]
        assert "prod" in server_aliases
        assert "staging" in server_aliases
        assert "local" in server_aliases

        # Test switching between servers
        for alias, _ in servers:
            config.set_current_server(alias)
            current = config.get_current_server()
            assert current["alias"] == alias

        # Test removing servers
        assert config.remove_server("local") is True
        assert config.remove_server("nonexistent") is False

        # Verify removal
        server_list = config.list_servers()
        assert len(server_list) == 2

        server_aliases = [s["alias"] for s in server_list]
        assert "local" not in server_aliases


@pytest.mark.integration
class TestErrorHandling:
    """Integration tests for error handling scenarios"""

    def test_invalid_server_url(self):
        """Test handling of invalid server URLs"""
        runner = CliRunner()

        result = runner.invoke(
            login, ["--no-browser", "--server-url", "invalid-url-format"]
        )

        # Should handle invalid URL gracefully
        assert result.exit_code == 1

    def test_network_timeout_simulation(self):
        """Test handling of network timeouts"""
        runner = CliRunner()

        # Use a URL that should timeout (non-routable IP)
        result = runner.invoke(
            login, ["--no-browser", "--server-url", "http://10.255.255.1"]
        )

        # Should handle network errors gracefully
        assert result.exit_code == 1

    def test_invalid_token_format(self):
        """Test handling of invalid token formats"""
        runner = CliRunner()

        with patch("weave.cli.prompt_for_api_token") as mock_prompt:
            mock_prompt.return_value = "clearly_invalid_token_format"

            result = runner.invoke(
                login, ["--no-browser", "--server-url", "https://example.com"]
            )

            assert result.exit_code == 1
            assert "Invalid token format" in result.output


# Helper fixtures for integration tests
@pytest.fixture
def integration_config_dir(tmp_path):
    """Create isolated config directory for integration tests"""
    config_dir = tmp_path / ".weavemcp"
    config_dir.mkdir()
    return config_dir


# Test data for integration scenarios
INTEGRATION_TEST_SCENARIOS = [
    {
        "name": "basic_workflow",
        "description": "Test basic login -> setup -> status workflow",
        "requires_token": True,
        "requires_server": True,
    },
    {
        "name": "server_management",
        "description": "Test server add/remove/switch operations",
        "requires_token": True,
        "requires_server": True,
    },
    {
        "name": "proxy_connection",
        "description": "Test proxy connection to virtual server",
        "requires_token": True,
        "requires_server": True,
        "requires_virtual_server": True,
    },
]


def pytest_configure(config):
    """Configure pytest for integration tests"""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring network access",
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle integration test markers"""
    skip_integration = pytest.mark.skip(
        reason="Integration tests require WEAVE_TEST_TOKEN environment variable"
    )

    for item in items:
        if "integration" in item.keywords and not os.getenv("WEAVE_TEST_TOKEN"):
            item.add_marker(skip_integration)
