"""CLI interface for Weave setup agent"""

import click
import sys
import webbrowser
import time
import asyncio
from typing import Optional

from .api_client import WeaveMCPClient, WeaveMCPAPIError
from .claude_config import ClaudeConfigManager, ClaudeConfigError
from .config import WeaveMCPConfig, ConfigError
from .auth_server import AuthServer
from .mcp_proxy import MCPProxyError
from .proxy_server import run_proxy_server
from .utils import (
    open_token_page,
    prompt_for_api_token,
    validate_base_url,
    format_server_info,
    get_auth_instructions,  
    validate_api_token,
)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Weave - Configure Claude Desktop with your WeaveMCP servers"""
    pass


@main.command()
@click.option(
    "--server-url",
    default="https://weavemcp.com",
    help="WeaveMCP server URL (default: https://weavemcp.com)",
)
@click.option(
    "--alias", default="default", help="Server alias to save as (default: default)"
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Don't open browser automatically (manual token entry)",
)
def login(server_url: str, alias: str, no_browser: bool):
    """Log in to WeaveMCP and save authentication token"""

    try:
        # Initialize config manager
        config = WeaveMCPConfig()

        # Validate and normalize server URL
        server_url = validate_base_url(server_url)
        click.echo(f"Logging in to WeaveMCP at: {server_url}")

        if no_browser:
            # Manual token entry mode
            click.echo(get_auth_instructions(server_url))
            token = prompt_for_api_token()

            if not validate_api_token(token):
                click.echo("❌ Invalid token format", err=True)
                sys.exit(1)

            # Test the token
            client = WeaveMCPClient(server_url, token)
            success, error = client.test_connection()

            if not success:
                click.echo(f"❌ Token validation failed: {error}", err=True)
                sys.exit(1)

            # Save token
            config.add_server(alias, server_url, token)
            config.set_current_server(alias)

            click.echo(f"✅ Successfully logged in and saved as '{alias}'")

        else:
            # Browser-based login with local server
            click.echo("Starting local authentication server...")

            with AuthServer() as auth_server:
                try:
                    port = auth_server.start()
                    click.echo(f"📡 Listening on http://localhost:{port}")

                    # Open browser to login page
                    login_url = f"{server_url}/cli/login/?port={port}"
                    click.echo(f"🌐 Opening browser to: {login_url}")

                    if webbrowser.open(login_url):
                        click.echo(
                            "Please complete the login process in your browser..."
                        )
                    else:
                        click.echo("⚠️  Could not open browser automatically")
                        click.echo(f"Please manually open: {login_url}")

                    # Wait for callback
                    click.echo("⏳ Waiting for authentication callback...")
                    token, callback_server_url = auth_server.wait_for_callback(
                        timeout=300
                    )

                    if token and callback_server_url:
                        # Verify the server URLs match
                        if callback_server_url.rstrip("/") != server_url.rstrip("/"):
                            click.echo(
                                f"⚠️  Server URL mismatch: expected {server_url}, got {callback_server_url}"
                            )

                        # Save token
                        config.add_server(alias, server_url, token)
                        config.set_current_server(alias)

                        click.echo(f"✅ Successfully logged in and saved as '{alias}'")

                        # Test the connection
                        client = WeaveMCPClient(server_url, token)
                        try:
                            server_data = client.get_default_virtual_server()
                            server = server_data["server"]
                            click.echo(f"🎯 Connected to server: {server['name']}")
                        except WeaveMCPAPIError:
                            click.echo(
                                "ℹ️  Token saved (server connection will be tested during setup)"
                            )

                    else:
                        click.echo("❌ Authentication timeout or failed", err=True)
                        click.echo(
                            "You can try again or use --no-browser for manual token entry"
                        )
                        sys.exit(1)

                except Exception as e:
                    click.echo(f"❌ Authentication server error: {e}", err=True)
                    click.echo("Try using --no-browser for manual token entry")
                    sys.exit(1)

    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


def _get_auth_config(
    server_url: Optional[str] = None,
    token: Optional[str] = None,
    server_alias: Optional[str] = None,
):
    """Get authentication configuration, preferring saved config"""
    config = WeaveMCPConfig()

    if server_alias:
        # Use specific server alias
        servers = config.list_servers()
        alias_server = next((s for s in servers if s["alias"] == server_alias), None)
        if not alias_server:
            raise click.ClickException(
                f"Server alias '{server_alias}' not found. Use 'login' command first."
            )
        return alias_server["url"], config.get_token(server_alias)

    if server_url and token:
        # Both provided explicitly
        return validate_base_url(server_url), token

    if token:
        # Token provided, use current server URL or default
        current_server = config.get_current_server()
        return current_server["url"], token

    if server_url:
        # Server URL provided, try to get saved token
        server_url = validate_base_url(server_url)
        servers = config.list_servers()
        matching_server = next((s for s in servers if s["url"] == server_url), None)
        if matching_server and matching_server.get("has_token"):
            return server_url, config.get_token(matching_server["alias"])
        else:
            raise click.ClickException(
                f"No saved token for {server_url}. Use 'login' command first."
            )

    # Nothing provided, use current server
    current_server = config.get_current_server()
    if not current_server["token"]:
        raise click.ClickException(
            "No authentication configured. Use 'login' command first."
        )

    return current_server["url"], current_server["token"]


@main.command()
@click.option(
    "--server-url", help="WeaveMCP server URL (uses saved config if not provided)"
)
@click.option(
    "--token", help="API token for authentication (uses saved token if not provided)"
)
@click.option("--server", help="Server alias to use (e.g., 'default', 'staging')")
@click.option(
    "--config-path",
    help="Path to Claude Desktop config file (auto-detected if not provided)",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
def setup(
    server_url: Optional[str],
    token: Optional[str],
    server: Optional[str],
    config_path: Optional[str],
    dry_run: bool,
):
    """Set up Claude Desktop with your default WeaveMCP virtual server"""

    try:
        # Get authentication configuration
        try:
            server_url, token = _get_auth_config(server_url, token, server)
        except click.ClickException as e:
            click.echo(f"❌ {e.message}", err=True)
            click.echo("💡 Use 'weave login' to authenticate first")
            sys.exit(1)

        click.echo(f"🔗 Connecting to WeaveMCP at: {server_url}")

        # Initialize API client
        client = WeaveMCPClient(server_url, token)

        # Test connection
        click.echo("Testing connection to WeaveMCP...")
        success, error = client.test_connection()
        if not success:
            click.echo(f"❌ Failed to connect to WeaveMCP: {error}", err=True)
            sys.exit(1)

        click.echo("✅ Connected to WeaveMCP successfully")

        # Get server details
        click.echo("Fetching your default virtual server...")
        connection_details = client.get_server_connection_details()

        if not connection_details:
            click.echo("❌ No default virtual server found.", err=True)
            click.echo(
                "Please create a virtual server in the WeaveMCP dashboard first."
            )
            sys.exit(1)

        click.echo("✅ Found default virtual server")
        click.echo(format_server_info(connection_details))

        # Initialize Claude config manager
        config_manager = ClaudeConfigManager(config_path)
        config_info = config_manager.get_config_info()

        click.echo(f"Claude Desktop config: {config_info['config_path']}")
        click.echo(f"Existing servers: {config_info['total_servers']}")
        click.echo(f"Existing WeaveMCP servers: {config_info['weavemcp_servers']}")

        if dry_run:
            click.echo("\n🔍 DRY RUN MODE - No changes will be made")
            if config_manager.has_weavemcp_server(connection_details["organization"]):
                click.echo("Would update existing WeaveMCP server configuration")
            else:
                click.echo("Would add new WeaveMCP server to Claude Desktop")
            return

        # Create backup
        backup_path = config_manager.backup_config()
        if backup_path:
            click.echo(f"📋 Created backup: {backup_path}")

        # Add or update server
        if config_manager.has_weavemcp_server(connection_details["organization"]):
            click.echo("Updating existing WeaveMCP server...")
            config_manager.update_weavemcp_server(connection_details)
            click.echo("✅ Updated WeaveMCP server configuration")
        else:
            click.echo("Adding WeaveMCP server to Claude Desktop...")
            config_manager.add_weavemcp_server(connection_details)
            click.echo("✅ Added WeaveMCP server to Claude Desktop")

        click.echo("\n🎉 Setup complete!")
        click.echo("Your WeaveMCP server is now configured to use the built-in proxy.")
        click.echo("Restart Claude Desktop to use your WeaveMCP server.")

    except WeaveMCPAPIError as e:
        click.echo(f"❌ WeaveMCP API error: {e}", err=True)
        sys.exit(1)
    except ClaudeConfigError as e:
        click.echo(f"❌ Claude Desktop config error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--config-path",
    help="Path to Claude Desktop config file (auto-detected if not provided)",
)
def status(config_path: Optional[str]):
    """Show current Claude Desktop configuration status"""

    try:
        config_manager = ClaudeConfigManager(config_path)
        config_info = config_manager.get_config_info()

        click.echo(f"Claude Desktop Config: {config_info['config_path']}")
        click.echo(f"Config exists: {'✅' if config_info['config_exists'] else '❌'}")
        click.echo(f"Total MCP servers: {config_info['total_servers']}")
        click.echo(f"WeaveMCP servers: {config_info['weavemcp_servers']}")

        if config_info["weavemcp_server_names"]:
            click.echo("\nWeaveMCP servers:")
            for server_name in config_info["weavemcp_server_names"]:
                click.echo(f"  • {server_name}")

    except ClaudeConfigError as e:
        click.echo(f"❌ Error reading config: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--server-url",
    default="https://weavemcp.dev",
    help="WeaveMCP server URL (default: https://weavemcp.dev)",
)
@click.option(
    "--token", help="API token for authentication (if not provided, will prompt)"
)
def test(server_url: str, token: Optional[str]):
    """Test connection to WeaveMCP API"""

    try:
        server_url = validate_base_url(server_url)

        if not token:
            token = prompt_for_api_token()

        if not validate_api_token(token):
            click.echo("❌ Invalid token format", err=True)
            sys.exit(1)

        client = WeaveMCPClient(server_url, token)

        click.echo("Testing connection...")
        success, error = client.test_connection()

        if success:
            click.echo("✅ Connection successful")

            # Test API endpoints
            try:
                orgs_data = client.get_user_organizations()
                click.echo(f"✅ Found {len(orgs_data['organizations'])} organizations")

                server_data = client.get_default_virtual_server()
                server = server_data["server"]
                click.echo(f"✅ Found default server: {server['name']}")

            except WeaveMCPAPIError as e:
                click.echo(f"⚠️  API test failed: {e}")
        else:
            click.echo(f"❌ Connection failed: {error}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--organization",
    help="Organization slug to remove (if not provided, will list all)",
)
@click.option(
    "--config-path",
    help="Path to Claude Desktop config file (auto-detected if not provided)",
)
@click.option("--all", "remove_all", is_flag=True, help="Remove all WeaveMCP servers")
def remove(organization: Optional[str], config_path: Optional[str], remove_all: bool):
    """Remove WeaveMCP servers from Claude Desktop configuration"""

    try:
        config_manager = ClaudeConfigManager(config_path)
        weavemcp_servers = config_manager.list_weavemcp_servers()

        if not weavemcp_servers:
            click.echo("No WeaveMCP servers found in configuration")
            return

        if remove_all:
            if click.confirm(f"Remove all {len(weavemcp_servers)} WeaveMCP servers?"):
                for server_name in weavemcp_servers:
                    org_slug = server_name.replace("weavemcp-", "")
                    config_manager.remove_weavemcp_server(org_slug)
                click.echo(f"✅ Removed {len(weavemcp_servers)} WeaveMCP servers")
            return

        if not organization:
            click.echo("WeaveMCP servers in configuration:")
            for server_name in weavemcp_servers:
                org_slug = server_name.replace("weavemcp-", "")
                click.echo(f"  • {org_slug}")
            click.echo("\nUse --organization <slug> to remove a specific server")
            return

        if config_manager.remove_weavemcp_server(organization):
            click.echo(f"✅ Removed WeaveMCP server for organization: {organization}")
        else:
            click.echo(f"❌ No WeaveMCP server found for organization: {organization}")

    except ClaudeConfigError as e:
        click.echo(f"❌ Config error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--config-path",
    help="Path to Claude Desktop config file (auto-detected if not provided)",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be updated without making changes"
)
def upgrade(config_path: Optional[str], dry_run: bool):
    """Upgrade existing WeaveMCP servers to use the new built-in proxy"""
    
    try:
        config_manager = ClaudeConfigManager(config_path)
        config = config_manager._read_config()
        weavemcp_servers = config_manager.list_weavemcp_servers()
        
        if not weavemcp_servers:
            click.echo("No WeaveMCP servers found in configuration")
            return
        
        updated_count = 0
        for server_name in weavemcp_servers:
            server_config = config["mcpServers"].get(server_name, {})
            
            # Check if this server is using old methods (npx or weavemcp-setup)
            if ((server_config.get("command") == "npx" and 
                "@modelcontextprotocol/server-proxy" in server_config.get("args", [])) or
                server_config.get("command") == "weavemcp-setup"):
                
                updated_count += 1
                if dry_run:
                    click.echo(f"Would update {server_name} to use weave proxy")
                else:
                    # Update to new proxy command
                    config["mcpServers"][server_name] = {
                        "command": "weave",
                        "args": ["proxy"],
                    }
        
        if dry_run:
            click.echo(f"\n🔍 DRY RUN - Found {updated_count} servers that would be updated")
            return
        
        if updated_count > 0:
            # Create backup
            backup_path = config_manager.backup_config()
            if backup_path:
                click.echo(f"📋 Created backup: {backup_path}")
            
            # Write updated config
            config_manager._write_config(config)
            click.echo(f"✅ Updated {updated_count} WeaveMCP servers to use built-in proxy")
            click.echo("Restart Claude Desktop to use the updated configuration.")
        else:
            click.echo("All WeaveMCP servers are already using the latest configuration")
    
    except ClaudeConfigError as e:
        click.echo(f"❌ Config error: {e}", err=True)
        sys.exit(1)


@main.group()
def server():
    """Manage WeaveMCP server configurations"""
    pass


@server.command("list")
def server_list():
    """List configured WeaveMCP servers"""
    try:
        config = WeaveMCPConfig()
        servers = config.list_servers()

        if not servers:
            click.echo("No servers configured. Use 'login' command to add a server.")
            return

        click.echo("Configured WeaveMCP servers:")
        click.echo()

        for server_config in servers:
            current_marker = "👉 " if server_config["is_current"] else "   "
            token_status = "✅" if server_config["has_token"] else "❌"

            click.echo(f"{current_marker}{server_config['alias']}")
            click.echo(f"    URL: {server_config['url']}")
            click.echo(f"    Token: {token_status}")
            click.echo()

    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)


@server.command("switch")
@click.argument("alias")
def server_switch(alias: str):
    """Switch to a different server configuration"""
    try:
        config = WeaveMCPConfig()
        config.set_current_server(alias)
        click.echo(f"✅ Switched to server: {alias}")

    except ConfigError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)


@server.command("remove")
@click.argument("alias")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def server_remove(alias: str, force: bool):
    """Remove a server configuration"""
    try:
        config = WeaveMCPConfig()

        if not force:
            servers = config.list_servers()
            server_to_remove = next((s for s in servers if s["alias"] == alias), None)
            if not server_to_remove:
                click.echo(f"❌ Server '{alias}' not found", err=True)
                sys.exit(1)

            click.echo(f"Remove server configuration:")
            click.echo(f"  Alias: {alias}")
            click.echo(f"  URL: {server_to_remove['url']}")

            if not click.confirm("Are you sure?"):
                click.echo("Cancelled")
                return

        if config.remove_server(alias):
            click.echo(f"✅ Removed server: {alias}")
        else:
            click.echo(f"❌ Server '{alias}' not found", err=True)
            sys.exit(1)

    except ConfigError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)


@server.command("add")
@click.argument("alias")
@click.argument("url")
def server_add(alias: str, url: str):
    """Add a new server configuration (without token)"""
    try:
        config = WeaveMCPConfig()
        config.add_server(alias, url)
        click.echo(f"✅ Added server '{alias}' at {url}")
        click.echo(f"💡 Use 'weave login --alias {alias}' to authenticate")

    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--server-url", help="WeaveMCP server URL (uses saved config if not provided)"
)
@click.option(
    "--token", help="API token for authentication (uses saved token if not provided)"
)
@click.option("--server", help="Server alias to use (e.g., 'default', 'staging')")
@click.option(
    "--verbose", "-v", is_flag=True, help="Enable verbose logging to stderr"
)
@click.option(
    "--log-file", 
    help="Override default log file path (default: ~/.weavemcp/proxy.log)"
)
def proxy(
    server_url: Optional[str],
    token: Optional[str], 
    server: Optional[str],
    verbose: bool,
    log_file: Optional[str]
):
    """Start STDIO proxy server for WeaveMCP virtual servers"""
    
    def ensure_authenticated():
        """Ensure user is authenticated, trigger login if needed"""
        try:
            config = WeaveMCPConfig()
            current_server = config.get_current_server()
            
            if not current_server["token"]:
                click.echo("❌ No authentication found. Starting login flow...")
                # Use the login command implementation
                ctx = click.get_current_context()
                ctx.invoke(login, server_url=current_server["url"], alias=current_server["alias"])
                
        except ConfigError:
            click.echo("❌ No server configuration found. Starting login flow...")
            ctx = click.get_current_context()
            ctx.invoke(login)
    
    try:
        # Check authentication before starting proxy
        if not token and not server:
            ensure_authenticated()
        
        if verbose:
            click.echo("🚀 Starting Weave STDIO proxy server...")
            if server_url:
                click.echo(f"   Server URL: {server_url}")
            if server:
                click.echo(f"   Server alias: {server}")
            if log_file:
                click.echo(f"   Log file: {log_file}")
        
        # Run the async proxy server
        asyncio.run(run_proxy_server(
            server_url=server_url,
            token=token,
            server_alias=server,
            verbose=verbose
        ))
        
    except MCPProxyError as e:
        click.echo(f"❌ Proxy error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        if verbose:
            click.echo("\n⏹️  Proxy server stopped", err=True)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
