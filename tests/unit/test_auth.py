"""Tests for authentication functionality"""

import pytest
from unittest.mock import Mock, patch, call
from click.testing import CliRunner
import responses

from weave.cli import login, server_list, server_switch, server_add, server_remove
from weave.config import WeaveMCPConfig, ConfigError
from tests.fixtures.test_data import TEST_API_TOKENS, TEST_SERVER_URLS
from tests.fixtures.mocks import MockAuthServer, MockWeaveMCPClient


class TestLoginCommand:
    """Test the login command functionality"""

    def test_login_manual_token_success(self, mock_config, mock_webbrowser):
        """Test successful manual token login"""
        runner = CliRunner()

        with (
            patch("weave.cli.prompt_for_api_token") as mock_prompt,
            patch("weave.cli.validate_api_token") as mock_validate,
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
        ):

            # Setup mocks
            mock_prompt.return_value = TEST_API_TOKENS["valid"]
            mock_validate.return_value = True

            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            # Run command
            result = runner.invoke(
                login, ["--no-browser", "--server-url", TEST_SERVER_URLS["production"]]
            )

            assert result.exit_code == 0
            assert "Successfully logged in" in result.output

            # Verify token was prompted and validated
            mock_prompt.assert_called_once()
            mock_validate.assert_called_once_with(TEST_API_TOKENS["valid"])

    def test_login_manual_token_invalid_format(self, mock_config):
        """Test login with invalid token format"""
        runner = CliRunner()

        with (
            patch("weave.cli.prompt_for_api_token") as mock_prompt,
            patch("weave.cli.validate_api_token") as mock_validate,
        ):

            mock_prompt.return_value = TEST_API_TOKENS["invalid"]
            mock_validate.return_value = False

            result = runner.invoke(
                login, ["--no-browser", "--server-url", TEST_SERVER_URLS["production"]]
            )

            assert result.exit_code == 1
            assert "Invalid token format" in result.output

    def test_login_manual_token_auth_failure(self, mock_config):
        """Test login with token that fails authentication"""
        runner = CliRunner()

        with (
            patch("weave.cli.prompt_for_api_token") as mock_prompt,
            patch("weave.cli.validate_api_token") as mock_validate,
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
        ):

            mock_prompt.return_value = TEST_API_TOKENS["expired"]
            mock_validate.return_value = True

            mock_client = MockWeaveMCPClient()
            mock_client.set_failure_mode(True, "unauthorized")
            mock_client_class.return_value = mock_client

            result = runner.invoke(
                login, ["--no-browser", "--server-url", TEST_SERVER_URLS["production"]]
            )

            assert result.exit_code == 1
            assert "Token validation failed" in result.output

    def test_login_browser_success(self, mock_config, mock_webbrowser):
        """Test successful browser-based login"""
        runner = CliRunner()

        with (
            patch("weave.cli.AuthServer") as mock_auth_server_class,
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
        ):

            # Setup auth server mock
            mock_auth_server = MockAuthServer()
            mock_auth_server_class.return_value.__enter__.return_value = (
                mock_auth_server
            )

            # Setup API client mock
            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            result = runner.invoke(
                login, ["--server-url", TEST_SERVER_URLS["production"]]
            )

            assert result.exit_code == 0
            assert "Successfully logged in" in result.output
            assert "Opening browser" in result.output

            # Verify browser was opened
            mock_webbrowser.assert_called_once()

    def test_login_browser_timeout(self, mock_config, mock_webbrowser):
        """Test browser-based login timeout"""
        runner = CliRunner()

        with patch("weave.cli.AuthServer") as mock_auth_server_class:

            mock_auth_server = MockAuthServer()
            mock_auth_server.set_timeout_mode(True)
            mock_auth_server_class.return_value.__enter__.return_value = (
                mock_auth_server
            )

            result = runner.invoke(
                login, ["--server-url", TEST_SERVER_URLS["production"]]
            )

            assert result.exit_code == 1
            assert "Authentication timeout" in result.output

    def test_login_custom_alias(self, mock_config, mock_webbrowser):
        """Test login with custom server alias"""
        runner = CliRunner()

        with (
            patch("weave.cli.AuthServer") as mock_auth_server_class,
            patch("weave.cli.WeaveMCPClient") as mock_client_class,
        ):

            mock_auth_server = MockAuthServer()
            mock_auth_server_class.return_value.__enter__.return_value = (
                mock_auth_server
            )

            mock_client = MockWeaveMCPClient()
            mock_client_class.return_value = mock_client

            result = runner.invoke(
                login,
                ["--server-url", TEST_SERVER_URLS["staging"], "--alias", "staging"],
            )

            assert result.exit_code == 0
            assert "Successfully logged in and saved as 'staging'" in result.output


class TestServerManagement:
    """Test server configuration management commands"""

    def test_server_list_empty(self, mock_config):
        """Test listing servers when none are configured"""
        runner = CliRunner()

        # Mock empty server list
        with patch("weave.cli.WeaveMCPConfig") as mock_config_class:
            mock_config_instance = Mock()
            mock_config_instance.list_servers.return_value = []
            mock_config_class.return_value = mock_config_instance

            result = runner.invoke(server_list)

            assert result.exit_code == 0
            assert "No servers configured" in result.output

    def test_server_list_with_servers(self, mock_config):
        """Test listing configured servers"""
        runner = CliRunner()

        # Add some test servers to config
        config = WeaveMCPConfig()
        config.add_server(
            "production", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.add_server("staging", TEST_SERVER_URLS["staging"])
        config.set_current_server("production")

        result = runner.invoke(server_list)

        assert result.exit_code == 0
        assert "production" in result.output
        assert "staging" in result.output
        assert "👉" in result.output  # Current server marker
        assert "✅" in result.output  # Has token marker
        assert "❌" in result.output  # No token marker

    def test_server_switch_success(self, mock_config):
        """Test switching to existing server"""
        runner = CliRunner()

        # Setup servers
        config = WeaveMCPConfig()
        config.add_server("production", TEST_SERVER_URLS["production"])
        config.add_server("staging", TEST_SERVER_URLS["staging"])
        config.set_current_server("production")

        result = runner.invoke(server_switch, ["staging"])

        assert result.exit_code == 0
        assert "Switched to server: staging" in result.output

        # Verify switch worked
        current = config.get_current_server()
        assert current["alias"] == "staging"

    def test_server_switch_nonexistent(self, mock_config):
        """Test switching to non-existent server"""
        runner = CliRunner()

        result = runner.invoke(server_switch, ["nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_server_add_success(self, mock_config):
        """Test adding new server configuration"""
        runner = CliRunner()

        result = runner.invoke(server_add, ["local", TEST_SERVER_URLS["local"]])

        assert result.exit_code == 0
        assert "Added server 'local'" in result.output
        assert "Use 'weave login --alias local'" in result.output

    def test_server_remove_success(self, mock_config):
        """Test removing server configuration"""
        runner = CliRunner()

        # Add server first
        config = WeaveMCPConfig()
        config.add_server("test", TEST_SERVER_URLS["local"])

        result = runner.invoke(server_remove, ["test", "--force"])

        assert result.exit_code == 0
        assert "Removed server: test" in result.output

    def test_server_remove_nonexistent(self, mock_config):
        """Test removing non-existent server"""
        runner = CliRunner()

        result = runner.invoke(server_remove, ["nonexistent", "--force"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_server_remove_with_confirmation(self, mock_config):
        """Test removing server with confirmation prompt"""
        runner = CliRunner()

        # Add server first
        config = WeaveMCPConfig()
        config.add_server("test", TEST_SERVER_URLS["local"])

        # Test cancellation
        result = runner.invoke(server_remove, ["test"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.output

        # Test confirmation
        result = runner.invoke(server_remove, ["test"], input="y\n")
        assert result.exit_code == 0
        assert "Removed server: test" in result.output


class TestConfigError:
    """Test configuration error handling"""

    def test_login_config_error(self, mock_config):
        """Test login command with configuration error"""
        runner = CliRunner()

        with patch("weave.cli.WeaveMCPConfig") as mock_config_class:
            mock_config_class.side_effect = ConfigError("Config file corrupted")

            result = runner.invoke(login, ["--no-browser"])

            assert result.exit_code == 1
            assert "Configuration error" in result.output

    def test_server_list_config_error(self, mock_config):
        """Test server list with configuration error"""
        runner = CliRunner()

        with patch("weave.cli.WeaveMCPConfig") as mock_config_class:
            mock_config_class.side_effect = ConfigError("Config file corrupted")

            result = runner.invoke(server_list)

            assert result.exit_code == 1
            assert "Configuration error" in result.output


@pytest.mark.unit
class TestAuthHelpers:
    """Test authentication helper functions"""

    def test_get_auth_config_with_saved_config(self, mock_config):
        """Test _get_auth_config with saved configuration"""
        from weave.cli import _get_auth_config

        # Setup config
        config = WeaveMCPConfig()
        config.add_server(
            "default", TEST_SERVER_URLS["production"], TEST_API_TOKENS["valid"]
        )
        config.set_current_server("default")

        server_url, token = _get_auth_config()

        assert server_url == TEST_SERVER_URLS["production"]
        assert token == TEST_API_TOKENS["valid"]

    def test_get_auth_config_with_explicit_params(self, mock_config):
        """Test _get_auth_config with explicit parameters"""
        from weave.cli import _get_auth_config

        server_url, token = _get_auth_config(
            server_url=TEST_SERVER_URLS["staging"], token=TEST_API_TOKENS["valid"]
        )

        assert server_url == TEST_SERVER_URLS["staging"]
        assert token == TEST_API_TOKENS["valid"]

    def test_get_auth_config_with_server_alias(self, mock_config):
        """Test _get_auth_config with server alias"""
        from weave.cli import _get_auth_config

        # Setup config
        config = WeaveMCPConfig()
        config.add_server(
            "staging", TEST_SERVER_URLS["staging"], TEST_API_TOKENS["valid"]
        )

        server_url, token = _get_auth_config(server_alias="staging")

        assert server_url == TEST_SERVER_URLS["staging"]
        assert token == TEST_API_TOKENS["valid"]

    def test_get_auth_config_no_auth(self, mock_config):
        """Test _get_auth_config when no authentication is configured"""
        from weave.cli import _get_auth_config
        from click.exceptions import ClickException

        with pytest.raises(ClickException) as exc_info:
            _get_auth_config()

        assert "No authentication configured" in str(exc_info.value)
