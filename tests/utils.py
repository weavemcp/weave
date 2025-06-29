"""Test utilities for Weave CLI testing"""

import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
from unittest.mock import patch

from weave.config import WeaveMCPConfig
from weave.claude_config import ClaudeConfigManager


class TestConfigManager:
    """Utility for managing test configurations"""

    def __init__(self, temp_dir: Path):
        self.temp_dir = Path(temp_dir)
        self.config_dir = self.temp_dir / ".weavemcp"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.claude_config_path = self.temp_dir / "claude_desktop_config.json"

    def create_weave_config(
        self, servers: Dict[str, Dict[str, str]], current_server: str = "default"
    ) -> WeaveMCPConfig:
        """Create a WeaveMCP configuration with specified servers"""
        with patch("weave.config.Path.home", return_value=self.temp_dir):
            config = WeaveMCPConfig()

            for alias, server_data in servers.items():
                config.add_server(alias, server_data["url"], server_data.get("token"))

            if current_server in servers:
                config.set_current_server(current_server)

            return config

    def create_claude_config(self, config_data: Dict[str, Any]) -> Path:
        """Create a Claude Desktop configuration file"""
        self.claude_config_path.write_text(json.dumps(config_data, indent=2))
        return self.claude_config_path

    def get_claude_manager(self) -> ClaudeConfigManager:
        """Get a Claude configuration manager for the test config"""
        return ClaudeConfigManager(str(self.claude_config_path))

    def cleanup(self):
        """Clean up test configuration files"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)


@contextmanager
def temporary_config():
    """Context manager for temporary test configuration"""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = TestConfigManager(Path(temp_dir))
        try:
            yield manager
        finally:
            manager.cleanup()


class MockResponseBuilder:
    """Builder for creating mock API responses"""

    def __init__(self):
        self.responses = {}

    def add_success_response(
        self, endpoint: str, data: Dict[str, Any]
    ) -> "MockResponseBuilder":
        """Add a successful API response"""
        self.responses[endpoint] = {"success": True, **data}
        return self

    def add_error_response(
        self, endpoint: str, error: str, code: str = "error"
    ) -> "MockResponseBuilder":
        """Add an error API response"""
        self.responses[endpoint] = {"success": False, "error": error, "code": code}
        return self

    def build(self) -> Dict[str, Dict[str, Any]]:
        """Build the responses dictionary"""
        return self.responses


def create_test_server_config(
    alias: str = "test",
    url: str = "https://test.weavemcp.app",
    token: Optional[str] = "test_token_123",
    organization: str = "testorg",
) -> Dict[str, str]:
    """Create a test server configuration"""
    config = {"alias": alias, "url": url, "organization": organization}
    if token:
        config["token"] = token
    return config


def create_test_connection_details(
    organization: str = "testorg",
    endpoint_url: str = "https://proxy.atlaslabs.weavemcp.app/proxy/test123",
    access_token: str = "test_access_token_123",
    server_id: str = "srv_test123",
) -> Dict[str, Any]:
    """Create test connection details for WeaveMCP server"""
    return {
        "name": f"weavemcp-{organization}",
        "endpoint_url": endpoint_url,
        "access_token": access_token,
        "server_id": server_id,
        "organization": organization,
        "description": f"WeaveMCP virtual server for {organization.title()}",
        "downstream_count": 2,
    }


def validate_claude_config(config_path: Path, expected_servers: List[str]) -> bool:
    """Validate Claude Desktop configuration contains expected servers"""
    if not config_path.exists():
        return False

    try:
        config_data = json.loads(config_path.read_text())
        if "mcpServers" not in config_data:
            return False

        servers = config_data["mcpServers"]
        for server_name in expected_servers:
            if server_name not in servers:
                return False

            server_config = servers[server_name]
            if "command" not in server_config or "args" not in server_config:
                return False

        return True

    except (json.JSONDecodeError, KeyError):
        return False


def validate_weave_config(config_dir: Path, expected_servers: List[str]) -> bool:
    """Validate WeaveMCP configuration contains expected servers"""
    config_file = config_dir / "config.json"
    if not config_file.exists():
        return False

    try:
        config_data = json.loads(config_file.read_text())
        if "servers" not in config_data:
            return False

        servers = config_data["servers"]
        for server_alias in expected_servers:
            if server_alias not in servers:
                return False

        return True

    except (json.JSONDecodeError, KeyError):
        return False


class TestDataGenerator:
    """Generator for test data scenarios"""

    @staticmethod
    def minimal_config() -> Dict[str, Any]:
        """Generate minimal configuration data"""
        return {
            "servers": {"default": {"url": "https://weavemcp.app", "alias": "default"}},
            "current_server": "default",
            "version": "0.1.0",
        }

    @staticmethod
    def multi_server_config() -> Dict[str, Any]:
        """Generate configuration with multiple servers"""
        return {
            "servers": {
                "production": {"url": "https://weavemcp.app", "alias": "production"},
                "staging": {"url": "https://staging.weavemcp.app", "alias": "staging"},
                "local": {"url": "http://localhost:8000", "alias": "local"},
            },
            "current_server": "production",
            "version": "0.1.0",
        }

    @staticmethod
    def claude_config_empty() -> Dict[str, Any]:
        """Generate empty Claude Desktop configuration"""
        return {"mcpServers": {}}

    @staticmethod
    def claude_config_with_existing_servers() -> Dict[str, Any]:
        """Generate Claude Desktop configuration with existing MCP servers"""
        return {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                },
                "sqlite": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-sqlite",
                        "--db-path",
                        "/tmp/test.db",
                    ],
                },
            }
        }

    @staticmethod
    def claude_config_with_weave_server(
        organization: str = "testorg",
    ) -> Dict[str, Any]:
        """Generate Claude Desktop configuration with WeaveMCP server"""
        return {
            "mcpServers": {
                f"weavemcp-{organization}": {"command": "weave", "args": ["proxy"]}
            }
        }


class AsyncTestHelper:
    """Helper for async test operations"""

    @staticmethod
    async def wait_for_condition(
        condition_func, timeout: float = 1.0, interval: float = 0.1
    ) -> bool:
        """Wait for a condition to become true"""
        import asyncio

        end_time = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end_time:
            if condition_func():
                return True
            await asyncio.sleep(interval)
        return False

    @staticmethod
    async def run_with_timeout(coro, timeout: float = 5.0):
        """Run coroutine with timeout"""
        import asyncio

        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout} seconds")


def create_integration_test_scenario(
    server_url: str = "https://atlaslabs.weavemcp.app",
    organization: str = "testorg",
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a complete integration test scenario"""
    return {
        "server_config": create_test_server_config(
            alias="integration", url=server_url, token=token, organization=organization
        ),
        "connection_details": create_test_connection_details(
            organization=organization,
            endpoint_url=f"https://proxy.{server_url.split('//')[1]}/proxy/integration123",
        ),
        "expected_claude_servers": [f"weavemcp-{organization}"],
        "expected_weave_servers": ["integration"],
    }


def assert_config_integrity(config_manager: TestConfigManager):
    """Assert that configuration files maintain integrity"""
    # Check WeaveMCP config exists and is valid JSON
    config_file = config_manager.config_dir / "config.json"
    if config_file.exists():
        try:
            json.loads(config_file.read_text())
        except json.JSONDecodeError:
            raise AssertionError("WeaveMCP config file is not valid JSON")

    # Check Claude config exists and is valid JSON
    if config_manager.claude_config_path.exists():
        try:
            config_data = json.loads(config_manager.claude_config_path.read_text())
            if "mcpServers" not in config_data:
                raise AssertionError("Claude config missing 'mcpServers' section")
        except json.JSONDecodeError:
            raise AssertionError("Claude config file is not valid JSON")


class LogCapture:
    """Utility for capturing and asserting log messages"""

    def __init__(self):
        self.messages = []

    def add_message(self, level: str, message: str):
        """Add a log message"""
        self.messages.append({"level": level, "message": message})

    def assert_message_contains(self, level: str, substring: str):
        """Assert that a log message contains a substring"""
        for msg in self.messages:
            if msg["level"] == level and substring in msg["message"]:
                return True
        raise AssertionError(f"No {level} message containing '{substring}' found")

    def assert_no_errors(self):
        """Assert that no error messages were logged"""
        error_messages = [msg for msg in self.messages if msg["level"] == "ERROR"]
        if error_messages:
            raise AssertionError(f"Found error messages: {error_messages}")

    def clear(self):
        """Clear captured messages"""
        self.messages.clear()
