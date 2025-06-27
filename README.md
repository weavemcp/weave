# Weave

**Weave** is a command-line tool that seamlessly connects [Claude Desktop](https://claude.ai/download) to [SuperMCP](https://weavemcp.com) virtual servers, enabling you to use multiple MCP (Model Context Protocol) servers through a single, unified interface.

## What is Weave?

Weave acts as a bridge between Claude Desktop and SuperMCP's infrastructure, allowing you to:

- **Centrally manage** multiple MCP servers through SuperMCP's web interface
- **Automatically configure** Claude Desktop with your virtual MCP servers  
- **Proxy MCP requests** from Claude Desktop to your configured servers with proper authentication
- **Upgrade existing** MCP configurations to use SuperMCP's infrastructure

## Quick Start

### 1. Install UV (if you don't have it)

Weave uses [UV](https://docs.astral.sh/uv/) for fast, reliable Python package management.

**macOS and Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Alternative installation methods:**
- **Homebrew:** `brew install uv`
- **pip:** `pip install uv`

For more installation options, see the [UV installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### 2. Run Weave with uvx

No installation required! Use `uvx` to run Weave directly:

```bash
uv tool install git+https://github.com/weavemcp/weave
```

Or install for easier access:
```bash
uv tool install git+https://github.com/weavemcp/weave
weave 
```

```bash
# Login to SuperMCP
uvx weave login

# Configure Claude Desktop
uvx weave setup

# Check status
uvx weave status
```

## Commands

### Authentication

```bash
# Login to SuperMCP (opens browser for OAuth)
uvx weave login

# Login with manual token entry
uvx weave login --no-browser

# Login to specific server
uvx weave login --server-url https://your-server.com
```

### Setup & Configuration

```bash
# Set up Claude Desktop with your default SuperMCP server
uvx weave setup

# Preview setup changes without applying them
uvx weave setup --dry-run

# Check current configuration
uvx weave status
```

### Proxy Server

```bash
# Start STDIO proxy server (used internally by Claude Desktop)
uvx weave proxy

# Start proxy with verbose logging
uvx weave proxy --verbose
```

### Management

```bash
# Upgrade existing MCP servers to use Weave
uvx weave upgrade

# Preview upgrade changes
uvx weave upgrade --dry-run

# Remove SuperMCP servers from Claude Desktop
uvx weave remove --organization myorg

# Remove all SuperMCP servers
uvx weave remove --all
```

### Server Management

```bash
# List configured servers
uvx weave server list

# Switch to different server
uvx weave server switch staging

# Add server without token
uvx weave server add production https://prod.weavemcp.com

# Remove server configuration
uvx weave server remove staging
```

## How It Works

1. **Login**: Authenticate with SuperMCP using OAuth through your browser
2. **Setup**: Weave configures Claude Desktop to use the `weave proxy` command
3. **Proxy**: When Claude Desktop starts, it runs `weave proxy` which:
   - Fetches your virtual server configuration from SuperMCP
   - Establishes authenticated connections to your MCP servers
   - Proxies all MCP requests between Claude and your servers

### Architecture

```
Claude Desktop ↔ Weave Proxy (STDIO) ↔ SuperMCP Infrastructure ↔ Your MCP Servers
```

## Configuration Files

Weave stores configuration in your home directory:

- **`~/.weavemcp/config.json`** - Server URLs and authentication tokens
- **`~/.weavemcp/proxy.log`** - Proxy operation logs
- **Claude Desktop config** - Updated automatically by `weave setup`

## Claude Desktop Integration

After running `weave setup`, your Claude Desktop configuration will include:

```json
{
  "mcpServers": {
    "supermcp-yourorg": {
      "command": "weave",
      "args": ["proxy"]
    }
  }
}
```

## Troubleshooting

### Common Issues

**"No authentication found"**
```bash
uvx weave login
```

**"No default virtual server found"**  
1. Visit [SuperMCP Dashboard](https://weavemcp.com)
2. Create a virtual server
3. Run `uvx weave setup`

**Claude Desktop not connecting**
1. Restart Claude Desktop after running `weave setup`
2. Check logs: `tail -f ~/.weavemcp/proxy.log`
3. Test proxy: `uvx weave proxy --verbose`

### Debug Mode

Run any command with `--verbose` for detailed logging:

```bash
uvx weave proxy --verbose
uvx weave setup --verbose
```

### Getting Help

```bash
# General help
uvx weave --help

# Command-specific help
uvx weave setup --help
uvx weave proxy --help
```

## Development

### Local Development

```bash
# Clone the repository
git clone https://github.com/weavemcp/weave.git
cd weave

# Install dependencies
uv sync

# Run locally
uv run weave --help
```

### Requirements

- Python ≥ 3.10
- UV package manager
- Claude Desktop (for MCP integration)

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

MIT License. See [LICENSE](LICENSE) for details.

## Support

- **Documentation**: [docs.weavemcp.com](https://docs.weavemcp.com)
- **Issues**: [GitHub Issues](https://github.com/weavemcp/weave/issues)
- **Community**: [SuperMCP Discord](https://discord.gg/supermcp)

---

Made with ❤️ by the [SuperMCP](https://weavemcp.com) team
