"""Configuration management for WeaveMCP CLI"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, List


class ConfigError(Exception):
    """Exception raised for configuration errors"""

    pass


class WeaveMCPConfig:
    """Manager for WeaveMCP CLI configuration"""

    def __init__(
        self, config_path: Optional[str] = None, context_override: Optional[str] = None
    ):
        """
        Initialize config manager

        Args:
            config_path: Optional custom path to config file
            context_override: Optional context alias to override current server
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path.home() / ".weavemcp" / "config.json"

        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Store context override for server resolution
        self.context_override = context_override

    def _read_config(self) -> Dict:
        """Read the configuration file"""
        if not self.config_path.exists():
            return {
                "servers": {
                    "default": {"url": "https://weavemcp.com", "token": None},
                    "local": {"url": "http://127.0.0.1:8000", "token": None},
                },
                "current_server": "default",
            }

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            # Ensure required structure exists
            if "servers" not in config:
                config["servers"] = {}
            if "current_server" not in config:
                config["current_server"] = "default"

            # Ensure default servers exist
            if "default" not in config["servers"]:
                config["servers"]["default"] = {
                    "url": "https://weavemcp.com",
                    "token": None,
                }
            if "local" not in config["servers"]:
                config["servers"]["local"] = {
                    "url": "http://127.0.0.1:8000",
                    "token": None,
                }

            return config

        except (json.JSONDecodeError, IOError) as e:
            raise ConfigError(f"Failed to read config file: {e}")

    def _write_config(self, config: Dict) -> None:
        """Write configuration to file"""
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2, sort_keys=True)
        except IOError as e:
            raise ConfigError(f"Failed to write config file: {e}")

    def add_server(self, alias: str, url: str, token: Optional[str] = None) -> None:
        """
        Add or update a server configuration

        Args:
            alias: Server alias (e.g., 'default', 'staging')
            url: Server URL
            token: Optional API token
        """
        config = self._read_config()

        # Normalize URL
        url = url.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        config["servers"][alias] = {"url": url, "token": token}

        self._write_config(config)

    def remove_server(self, alias: str) -> bool:
        """
        Remove a server configuration

        Args:
            alias: Server alias to remove

        Returns:
            True if server was removed, False if it didn't exist
        """
        config = self._read_config()

        if alias not in config["servers"]:
            return False

        # Don't allow removing the current server
        if alias == config["current_server"]:
            raise ConfigError(
                f"Cannot remove current server '{alias}'. Switch to another server first."
            )

        # Don't allow removing the last server
        if len(config["servers"]) <= 1:
            raise ConfigError("Cannot remove the last server configuration")

        del config["servers"][alias]
        self._write_config(config)
        return True

    def set_current_server(self, alias: str) -> None:
        """
        Set the current active server

        Args:
            alias: Server alias to make current
        """
        config = self._read_config()

        if alias not in config["servers"]:
            raise ConfigError(f"Server '{alias}' not found")

        config["current_server"] = alias
        self._write_config(config)

    def get_current_server(self) -> Dict[str, str]:
        """
        Get current server configuration

        Returns:
            Dict with 'alias', 'url', and 'token' keys
        """
        config = self._read_config()
        current_alias = config["current_server"]

        if current_alias not in config["servers"]:
            # Fallback to default if current server is missing
            current_alias = "default"
            config["current_server"] = current_alias
            self._write_config(config)

        server_config = config["servers"][current_alias]
        return {
            "alias": current_alias,
            "url": server_config["url"],
            "token": server_config.get("token"),
        }

    def set_token(self, alias: str, token: str) -> None:
        """
        Set API token for a server

        Args:
            alias: Server alias
            token: API token
        """
        config = self._read_config()

        if alias not in config["servers"]:
            raise ConfigError(f"Server '{alias}' not found")

        config["servers"][alias]["token"] = token
        self._write_config(config)

    def get_token(self, alias: Optional[str] = None) -> Optional[str]:
        """
        Get API token for a server

        Args:
            alias: Server alias (defaults to current server)

        Returns:
            API token or None if not set
        """
        if alias is None:
            server_config = self.get_current_server()
            return server_config["token"]

        config = self._read_config()
        if alias not in config["servers"]:
            return None

        return config["servers"][alias].get("token")

    def list_servers(self) -> List[Dict[str, str]]:
        """
        List all configured servers

        Returns:
            List of server configurations with alias, url, and has_token fields
        """
        config = self._read_config()
        current_alias = config["current_server"]

        servers = []
        for alias, server_config in config["servers"].items():
            servers.append(
                {
                    "alias": alias,
                    "url": server_config["url"],
                    "has_token": bool(server_config.get("token")),
                    "is_current": alias == current_alias,
                }
            )

        return servers

    def get_config_info(self) -> Dict:
        """
        Get configuration file information

        Returns:
            Dict with config path and existence info
        """
        return {
            "config_path": str(self.config_path),
            "config_exists": self.config_path.exists(),
            "server_count": len(self._read_config()["servers"]),
        }

    def ensure_authenticated(self, alias: Optional[str] = None) -> bool:
        """
        Check if user is authenticated for a server

        Args:
            alias: Server alias to check (defaults to current server)

        Returns:
            True if authenticated, False otherwise
        """
        try:
            if alias:
                token = self.get_token(alias)
            else:
                current_server = self.get_current_server()
                token = current_server["token"]

            return bool(token)
        except ConfigError:
            return False

    def get_proxy_log_path(self) -> Path:
        """
        Get the default proxy log file path

        Returns:
            Path to proxy log file
        """
        return self.config_path.parent / "proxy.log"

    def get_effective_server(
        self, server_alias: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get the effective server configuration based on context override and parameters

        Args:
            server_alias: Optional server alias to use instead of current server

        Returns:
            Dict with 'alias', 'url', and 'token' keys
        """
        # Priority order: provided alias -> context override -> current server
        effective_alias = server_alias or self.context_override

        if effective_alias:
            # Use specific server alias
            servers = self.list_servers()
            alias_server = next(
                (s for s in servers if s["alias"] == effective_alias), None
            )
            if not alias_server:
                raise ConfigError(
                    f"Server alias '{effective_alias}' not found. Use 'login' command first."
                )

            return {
                "alias": effective_alias,
                "url": alias_server["url"],
                "token": self.get_token(effective_alias),
            }
        else:
            # Use current server
            return self.get_current_server()

    def get_auth_config(
        self,
        server_url: Optional[str] = None,
        token: Optional[str] = None,
        server_alias: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Get authentication configuration for API calls

        Args:
            server_url: Optional server URL override
            token: Optional token override
            server_alias: Optional server alias override

        Returns:
            Tuple of (server_url, token)
        """
        # If both server_url and token are provided explicitly, use them
        if server_url and token:
            from .utils import validate_base_url

            return validate_base_url(server_url), token

        # If only token is provided, use it with current server URL
        if token:
            current_server = self.get_effective_server(server_alias)
            return current_server["url"], token

        # If only server_url is provided, try to get saved token
        if server_url:
            from .utils import validate_base_url

            server_url = validate_base_url(server_url)
            servers = self.list_servers()
            matching_server = next((s for s in servers if s["url"] == server_url), None)
            if matching_server and matching_server.get("has_token"):
                return server_url, self.get_token(matching_server["alias"])
            else:
                raise ConfigError(
                    f"No saved token for {server_url}. Use 'login' command first."
                )

        # Use effective server (with context override support)
        effective_server = self.get_effective_server(server_alias)
        if not effective_server["token"]:
            raise ConfigError(
                "No authentication configured. Use 'login' command first."
            )

        return effective_server["url"], effective_server["token"]
