"""Tests for configuration management functionality"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from weave.cli import setup, status, remove, upgrade
from weave.config import WeaveMCPConfig, ConfigError
from weave.claude_config import ClaudeConfigManager, ClaudeConfigError
from tests.fixtures.test_data import (
    SAMPLE_CONNECTION_DETAILS,
    EMPTY_CLAUDE_CONFIG,
    CLAUDE_CONFIG_WITH_EXISTING_SERVERS,
    CLAUDE_CONFIG_WITH_WEAVEMCP_SERVER,
    CLAUDE_CONFIG_WITH_OLD_WEAVEMCP,
    TEST_API_TOKENS,
    TEST_SERVER_URLS,
)
from tests.fixtures.mocks import MockWeaveMCPClient, create_mock_claude_config


class TestSetupCommand:
    """Test the setup command functionality"""

    def test_setup_success_new_server(self, mock_config, temp_claude_config):
        """Test successful setup with new WeaveMCP server"""
        runner = CliRunner()

        # Setup config with authentication
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        # Create initial Claude config
        create_mock_claude_config(temp_claude_config, EMPTY_CLAUDE_CONFIG)

        with (
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
            patch("weave.cli.ClaudeConfigManager") as mock_claude_class,
        ):

            # Setup API client mock
            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            # Setup Claude config mock
            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.get_config_info.return_value = {
                "config_path": str(temp_claude_config),
                "config_exists": True,
                "total_servers": 0,
                "weavemcp_servers": 0,
                "weavemcp_server_names": [],
            }
            mock_claude_manager.has_weavemcp_server.return_value = False
            mock_claude_manager.backup_config.return_value = (
                str(temp_claude_config) + ".backup"
            )
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(setup, ["--config-path", str(temp_claude_config)])

            assert result.exit_code == 0
            assert "Connected to WeaveMCP successfully" in result.output
            assert "Found default virtual server" in result.output
            assert "Added WeaveMCP server to Claude Desktop" in result.output
            assert "Setup complete" in result.output

            # Verify methods were called
            mock_claude_manager.add_weavemcp_server.assert_called_once()
            mock_claude_manager.backup_config.assert_called_once()

    def test_setup_success_update_existing(self, mock_config, temp_claude_config):
        """Test successful setup updating existing WeaveMCP server"""
        runner = CliRunner()

        # Setup config with authentication
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with (
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
            patch("weave.cli.ClaudeConfigManager") as mock_claude_class,
        ):

            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.get_config_info.return_value = {
                "config_path": str(temp_claude_config),
                "config_exists": True,
                "total_servers": 1,
                "weavemcp_servers": 1,
                "weavemcp_server_names": ["weavemcp-testorg"],
            }
            mock_claude_manager.has_weavemcp_server.return_value = True
            mock_claude_manager.backup_config.return_value = (
                str(temp_claude_config) + ".backup"
            )
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(setup)

            assert result.exit_code == 0
            assert "Updated WeaveMCP server configuration" in result.output

            mock_claude_manager.update_weavemcp_server.assert_called_once()

    def test_setup_dry_run(self, mock_config):
        """Test setup in dry-run mode"""
        runner = CliRunner()

        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with (
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
            patch("weave.cli.ClaudeConfigManager") as mock_claude_class,
        ):

            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.get_config_info.return_value = {
                "config_path": "/tmp/test_config.json",
                "config_exists": True,
                "total_servers": 0,
                "weavemcp_servers": 0,
                "weavemcp_server_names": [],
            }
            mock_claude_manager.has_weavemcp_server.return_value = False
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(setup, ["--dry-run"])

            assert result.exit_code == 0
            assert "DRY RUN MODE" in result.output
            assert "Would add new WeaveMCP server" in result.output

            # Verify no actual changes were made
            mock_claude_manager.add_weavemcp_server.assert_not_called()
            mock_claude_manager.backup_config.assert_not_called()

    def test_setup_no_authentication(self, mock_config):
        """Test setup without authentication configured"""
        runner = CliRunner()

        result = runner.invoke(setup)

        assert result.exit_code == 1
        assert "No authentication configured" in result.output
        assert "Use 'weave login'" in result.output

    def test_setup_api_connection_failure(self, mock_config):
        """Test setup with API connection failure"""
        runner = CliRunner()

        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["expired"]
        )
        config.set_current_server("default")

        with patch("weave.cli.WeaveMCPClient") as mock_client_class:

            mock_client = MockWeaveMCPClient()
            mock_client.set_failure_mode(True, "unauthorized")
            mock_client_class.return_value = mock_client

            result = runner.invoke(setup)

            assert result.exit_code == 1
            assert "Failed to connect to WeaveMCP" in result.output

    def test_setup_no_default_server(self, mock_config):
        """Test setup when no default virtual server is found"""
        runner = CliRunner()

        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with patch("weave.cli.WeaveMCPClient") as mock_client_class:

            mock_client = MockWeaveMCPClient()
            mock_client.set_failure_mode(True, "not_found")
            mock_client_class.return_value = mock_client

            result = runner.invoke(setup)

            assert result.exit_code == 1
            assert "No default virtual server found" in result.output


class TestStatusCommand:
    """Test the status command functionality"""

    def test_status_success(self, temp_claude_config):
        """Test status command with valid configuration"""
        runner = CliRunner()

        create_mock_claude_config(
            temp_claude_config, CLAUDE_CONFIG_WITH_WEAVEMCP_SERVER
        )

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.get_config_info.return_value = {
                "config_path": str(temp_claude_config),
                "config_exists": True,
                "total_servers": 2,
                "weavemcp_servers": 1,
                "weavemcp_server_names": ["weavemcp-testorg"],
            }
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(status, ["--config-path", str(temp_claude_config)])

            assert result.exit_code == 0
            assert str(temp_claude_config) in result.output
            assert "Config exists: ✅" in result.output
            assert "Total MCP servers: 2" in result.output
            assert "WeaveMCP servers: 1" in result.output
            assert "weavemcp-testorg" in result.output

    def test_status_no_config(self):
        """Test status command when config doesn't exist"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.get_config_info.return_value = {
                "config_path": "/nonexistent/config.json",
                "config_exists": False,
                "total_servers": 0,
                "weavemcp_servers": 0,
                "weavemcp_server_names": [],
            }
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(status)

            assert result.exit_code == 0
            assert "Config exists: ❌" in result.output
            assert "Total MCP servers: 0" in result.output

    def test_status_config_error(self):
        """Test status command with configuration error"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:
            mock_claude_class.side_effect = ClaudeConfigError("Config file corrupted")

            result = runner.invoke(status)

            assert result.exit_code == 1
            assert "Error reading config" in result.output


class TestRemoveCommand:
    """Test the remove command functionality"""

    def test_remove_specific_server(self, temp_claude_config):
        """Test removing specific WeaveMCP server"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg"
            ]
            mock_claude_manager.remove_weavemcp_server.return_value = True
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(remove, ["--organization", "testorg"])

            assert result.exit_code == 0
            assert "Removed WeaveMCP server for organization: testorg" in result.output

            mock_claude_manager.remove_weavemcp_server.assert_called_once_with(
                "testorg"
            )

    def test_remove_nonexistent_server(self):
        """Test removing non-existent server"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg"
            ]
            mock_claude_manager.remove_weavemcp_server.return_value = False
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(remove, ["--organization", "nonexistent"])

            assert result.exit_code == 0
            assert (
                "No WeaveMCP server found for organization: nonexistent"
                in result.output
            )

    def test_remove_all_servers(self):
        """Test removing all WeaveMCP servers"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg1",
                "weavemcp-testorg2",
            ]
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(remove, ["--all"], input="y\n")

            assert result.exit_code == 0
            assert "Removed 2 WeaveMCP servers" in result.output

            # Verify both servers were removed
            expected_calls = [Mock().__call__("testorg1"), Mock().__call__("testorg2")]
            assert mock_claude_manager.remove_weavemcp_server.call_count == 2

    def test_remove_list_servers(self):
        """Test listing WeaveMCP servers without removing"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg1",
                "weavemcp-testorg2",
            ]
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(remove)

            assert result.exit_code == 0
            assert "WeaveMCP servers in configuration:" in result.output
            assert "testorg1" in result.output
            assert "testorg2" in result.output
            assert "Use --organization <slug> to remove" in result.output

    def test_remove_no_servers(self):
        """Test remove command when no WeaveMCP servers exist"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = []
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(remove)

            assert result.exit_code == 0
            assert "No WeaveMCP servers found" in result.output


class TestUpgradeCommand:
    """Test the upgrade command functionality"""

    def test_upgrade_old_servers(self, temp_claude_config):
        """Test upgrading old WeaveMCP server configurations"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg"
            ]
            mock_claude_manager._read_config.return_value = (
                CLAUDE_CONFIG_WITH_OLD_WEAVEMCP
            )
            mock_claude_manager.backup_config.return_value = (
                str(temp_claude_config) + ".backup"
            )
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(upgrade)

            assert result.exit_code == 0
            assert "Updated 1 WeaveMCP servers" in result.output
            assert "use built-in proxy" in result.output

            mock_claude_manager.backup_config.assert_called_once()
            mock_claude_manager._write_config.assert_called_once()

    def test_upgrade_dry_run(self):
        """Test upgrade in dry-run mode"""
        runner = CliRunner()

        # Create a fresh copy of the old config to avoid state issues
        old_config = {
            "mcpServers": {
                "weavemcp-testorg": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-proxy",
                        "https://proxy.atlaslabs.weavemcp.app/proxy/old123",
                        "old_token_123",
                    ],
                }
            }
        }

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg"
            ]
            mock_claude_manager._read_config.return_value = old_config
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(upgrade, ["--dry-run"])

            assert result.exit_code == 0
            assert "DRY RUN" in result.output
            assert "Found 1 servers that would be updated" in result.output

            # Verify no actual changes were made
            mock_claude_manager.backup_config.assert_not_called()
            mock_claude_manager._write_config.assert_not_called()

    def test_upgrade_no_servers(self):
        """Test upgrade when no WeaveMCP servers exist"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = []
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(upgrade)

            assert result.exit_code == 0
            assert "No WeaveMCP servers found" in result.output

    def test_upgrade_already_current(self):
        """Test upgrade when servers are already using current format"""
        runner = CliRunner()

        with patch("weave.cli.ClaudeConfigManager") as mock_claude_class:

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.list_weavemcp_servers.return_value = [
                "weavemcp-testorg"
            ]
            mock_claude_manager._read_config.return_value = (
                CLAUDE_CONFIG_WITH_WEAVEMCP_SERVER
            )
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(upgrade)

            assert result.exit_code == 0
            assert "already using the latest configuration" in result.output


@pytest.mark.unit
class TestConfigurationValidation:
    """Test configuration validation and error handling"""

    def test_setup_claude_config_error(self, mock_config):
        """Test setup with Claude Desktop configuration error"""
        runner = CliRunner()

        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        with (
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
            patch("weave.cli.ClaudeConfigManager") as mock_claude_class,
        ):

            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            mock_claude_class.side_effect = ClaudeConfigError(
                "Cannot write to config file"
            )

            result = runner.invoke(setup)

            assert result.exit_code == 1
            assert "Claude Desktop config error" in result.output

    def test_explicit_server_and_token_params(self, temp_claude_config):
        """Test setup with explicit server URL and token parameters"""
        runner = CliRunner()

        create_mock_claude_config(temp_claude_config, EMPTY_CLAUDE_CONFIG)

        with (
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
            patch("weave.cli.ClaudeConfigManager") as mock_claude_class,
        ):

            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            mock_claude_manager = Mock(spec=ClaudeConfigManager)
            mock_claude_manager.get_config_info.return_value = {
                "config_path": str(temp_claude_config),
                "config_exists": True,
                "total_servers": 0,
                "weavemcp_servers": 0,
                "weavemcp_server_names": [],
            }
            mock_claude_manager.has_weavemcp_server.return_value = False
            mock_claude_manager.backup_config.return_value = None  # No backup needed
            mock_claude_class.return_value = mock_claude_manager

            result = runner.invoke(
                setup,
                [
                    "--server-url",
                    TEST_SERVER_URLS["production"],
                    "--token",
                    TEST_API_TOKENS["valid"],
                    "--config-path",
                    str(temp_claude_config),
                ],
            )

            assert result.exit_code == 0
            assert "Setup complete" in result.output

            # Verify client was initialized with correct parameters
            mock_client_class.assert_called_with(
                TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
            )
