"""Pytest configuration and shared fixtures for Weave tests"""

import json
import tempfile
import pytest
from pathlib import Path
from typing import Dict, Generator, Optional
from unittest.mock import Mock, patch

from weave.config import WeaveMCPConfig
from weave.api_client import WeaveMCPClient


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for configuration files"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / ".weavemcp"
        config_dir.mkdir(parents=True, exist_ok=True)
        yield config_dir


@pytest.fixture
def temp_claude_config() -> Generator[Path, None, None]:
    """Create a temporary Claude Desktop configuration file"""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "claude_desktop_config.json"
        config_file.write_text(json.dumps({"mcpServers": {}}, indent=2))
        yield config_file


@pytest.fixture
def mock_config(temp_config_dir: Path, monkeypatch) -> WeaveMCPConfig:
    """Create a mocked WeaveMCP configuration"""
    # Patch the config directory
    monkeypatch.setattr("weave.config.Path.home", lambda: temp_config_dir.parent)

    config = WeaveMCPConfig()
    return config


@pytest.fixture
def sample_server_config() -> Dict:
    """Sample server configuration data"""
    return {
        "name": "weavemcp-testorg",
        "endpoint_url": "https://proxy.atlaslabs.weavemcp.app/proxy/abcd1234",
        "access_token": "test_access_token_123",
        "server_id": "srv_123",
        "organization": "testorg",
        "description": "WeaveMCP virtual server for Test Organization",
        "downstream_count": 2,
    }


@pytest.fixture
def sample_api_response() -> Dict:
    """Sample API response for default virtual server"""
    return {
        "success": True,
        "server": {
            "id": "srv_123",
            "name": "Test Server",
            "endpoint_url": "https://proxy.atlaslabs.weavemcp.app/proxy/abcd1234",
            "access_token": "test_access_token_123",
            "organization": {"slug": "testorg", "name": "Test Organization"},
            "downstream_servers": [
                {"name": "filesystem", "status": "active"},
                {"name": "sqlite", "status": "active"},
            ],
        },
    }


@pytest.fixture
def mock_api_client(sample_api_response: Dict) -> Mock:
    """Create a mocked WeaveMCP API client"""
    client = Mock(spec=WeaveMCPClient)
    client.test_connection.return_value = (True, None)
    client.get_default_virtual_server.return_value = sample_api_response
    client.get_user_organizations.return_value = {
        "success": True,
        "organizations": [{"slug": "testorg", "name": "Test Organization"}],
        "default_organization": "testorg",
    }
    client.get_server_connection_details.return_value = {
        "name": "weavemcp-testorg",
        "endpoint_url": "https://proxy.atlaslabs.weavemcp.app/proxy/abcd1234",
        "access_token": "test_access_token_123",
        "server_id": "srv_123",
        "organization": "testorg",
        "description": "WeaveMCP virtual server for Test Organization",
        "downstream_count": 2,
    }
    return client


@pytest.fixture
def integration_server_url() -> str:
    """URL for integration testing"""
    return "https://atlaslabs.weavemcp.app"


@pytest.fixture
def integration_token() -> Optional[str]:
    """
    Integration test token - should be set via environment variable
    WEAVE_TEST_TOKEN for integration tests to work
    """
    import os

    return os.getenv("WEAVE_TEST_TOKEN")


@pytest.fixture
def skip_if_no_integration_token(integration_token: Optional[str]):
    """Skip test if no integration token is available"""
    if not integration_token:
        pytest.skip("Integration token not available (set WEAVE_TEST_TOKEN)")


class MockAuthServer:
    """Mock authentication server for testing"""

    def __init__(self):
        self.port = 8080
        self.token = "test_token_123"
        self.server_url = "https://atlaslabs.weavemcp.app"

    def start(self) -> int:
        return self.port

    def wait_for_callback(self, timeout: int = 300) -> tuple[str, str]:
        return self.token, self.server_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_auth_server() -> MockAuthServer:
    """Create a mock authentication server"""
    return MockAuthServer()


@pytest.fixture
def mock_webbrowser():
    """Mock webbrowser.open function"""
    with patch("webbrowser.open") as mock:
        mock.return_value = True
        yield mock
