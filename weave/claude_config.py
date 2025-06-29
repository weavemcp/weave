"""Claude Desktop configuration management"""

import json
import os
import platform
import shutil
from pathlib import Path
from typing import Dict, Optional, List


class ClaudeConfigError(Exception):
    """Exception raised for Claude Desktop configuration errors"""

    pass


class ClaudeConfigManager:
    """Manager for Claude Desktop configuration without external dependencies"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Claude Desktop config manager

        Args:
            config_path: Optional custom path to config file
        """
        self.config_path = config_path or self.get_default_config_path()

    @staticmethod
    def get_default_config_path() -> str:
        """Get the default Claude Desktop config file path for the current platform"""
        system = platform.system()

        if system == "Darwin":  # macOS
            return os.path.expanduser(
                "~/Library/Application Support/Claude/claude_desktop_config.json"
            )
        elif system == "Windows":
            return os.path.expanduser(
                "~/AppData/Roaming/Claude/claude_desktop_config.json"
            )
        elif system == "Linux":
            return os.path.expanduser("~/.config/claude/claude_desktop_config.json")
        else:
            raise ClaudeConfigError(f"Unsupported platform: {system}")

    def _read_config(self) -> Dict:
        """Read the current configuration file"""
        if not os.path.exists(self.config_path):
            return {"mcpServers": {}}

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            # Ensure mcpServers section exists
            if "mcpServers" not in config:
                config["mcpServers"] = {}

            return config
        except (json.JSONDecodeError, IOError) as e:
            raise ClaudeConfigError(f"Failed to read config file: {e}")

    def _write_config(self, config: Dict) -> None:
        """Write configuration to file"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2, sort_keys=True)

        except IOError as e:
            raise ClaudeConfigError(f"Failed to write config file: {e}")

    def backup_config(self) -> str:
        """
        Create a backup of the current configuration

        Returns:
            Path to the backup file
        """
        if not os.path.exists(self.config_path):
            return ""

        backup_path = f"{self.config_path}.backup"
        shutil.copy2(self.config_path, backup_path)
        return backup_path

    def get_existing_servers(self) -> Dict[str, Dict]:
        """
        Get dictionary of existing MCP servers in the configuration

        Returns:
            Dictionary of server configurations
        """
        config = self._read_config()
        return config.get("mcpServers", {})

    def has_weavemcp_server(self, organization_slug: str) -> bool:
        """
        Check if a WeaveMCP server for the given organization already exists

        Args:
            organization_slug: Organization slug to check for

        Returns:
            True if server exists, False otherwise
        """
        servers = self.get_existing_servers()
        server_name = f"weavemcp-{organization_slug}"
        return server_name in servers

    def add_weavemcp_server(self, connection_details: Dict) -> bool:
        """
        Add a WeaveMCP server to Claude Desktop configuration

        Args:
            connection_details: Server connection details from API

        Returns:
            True if server was added, False if it already exists
        """
        server_name = connection_details["name"]

        # Check if server already exists
        if self.has_weavemcp_server(connection_details["organization"]):
            return False

        config = self._read_config()

        # Create server configuration for Claude Desktop
        # WeaveMCP servers now use the weave proxy command
        config["mcpServers"][server_name] = {
            "command": "weave",
            "args": ["proxy"],
        }

        try:
            self._write_config(config)
            return True
        except ClaudeConfigError:
            raise

    def remove_weavemcp_server(self, organization_slug: str) -> bool:
        """
        Remove a WeaveMCP server from Claude Desktop configuration

        Args:
            organization_slug: Organization slug to remove

        Returns:
            True if server was removed, False if it didn't exist
        """
        server_name = f"weavemcp-{organization_slug}"

        config = self._read_config()

        if server_name not in config["mcpServers"]:
            return False

        del config["mcpServers"][server_name]

        try:
            self._write_config(config)
            return True
        except ClaudeConfigError:
            raise

    def update_weavemcp_server(self, connection_details: Dict) -> bool:
        """
        Update an existing WeaveMCP server configuration

        Args:
            connection_details: Updated server connection details

        Returns:
            True if server was updated
        """
        server_name = connection_details["name"]

        config = self._read_config()

        # Update server configuration for Claude Desktop
        # WeaveMCP servers now use the weave proxy command
        config["mcpServers"][server_name] = {
            "command": "weave",
            "args": ["proxy"],
        }

        try:
            self._write_config(config)
            return True
        except ClaudeConfigError:
            raise

    def list_weavemcp_servers(self) -> List[str]:
        """
        Get list of WeaveMCP server names in the configuration

        Returns:
            List of WeaveMCP server names
        """
        servers = self.get_existing_servers()
        return [name for name in servers.keys() if name.startswith("weavemcp-")]

    def get_config_info(self) -> Dict:
        """
        Get information about the current configuration

        Returns:
            Dict with config file path, backup info, and server counts
        """
        existing_servers = self.get_existing_servers()
        weavemcp_servers = self.list_weavemcp_servers()

        return {
            "config_path": self.config_path,
            "config_exists": os.path.exists(self.config_path),
            "total_servers": len(existing_servers),
            "weavemcp_servers": len(weavemcp_servers),
            "weavemcp_server_names": weavemcp_servers,
        }
