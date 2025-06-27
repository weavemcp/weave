# Weave

**Weave** is a command-line tool that seamlessly connects [Claude Desktop](https://claude.ai/download) to [WeaveMCP](https://weavemcp.com) virtual servers, enabling you to use multiple MCP (Model Context Protocol) servers through a single, unified interface.

## What is Weave?

Weave acts as a bridge between Claude Desktop and WeaveMCP's infrastructure, allowing you to:

- **Centrally manage** multiple MCP servers through WeaveMCP's web interface
- **Automatically configure** Claude Desktop with your virtual MCP servers  
- **Proxy MCP requests** from Claude Desktop to your configured servers with proper authentication
- **Upgrade existing** MCP configurations to use WeaveMCP's infrastructure

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
uvx --from git+https://github.com/weavemcp/weave weave
```

Or install for easier access:
```bash
uv tool install git+https://github.com/weavemcp/weave
weave 
```

The below commands will work with either command, but we recommend using `uvx install` for ease of use, and the below commands assume installation via `uvx install`.

```bash
# Login to WeaveMCP
weave login

# Configure Claude Desktop
weave setup

# Check status
weave status
```

## Commands

### Authentication

```bash
# Login to WeaveMCP (opens browser for OAuth)
weave login

# Login with manual token entry
weave login --no-browser

# Login to specific server
weave login --server-url https://your-server.com
```

### Setup & Configuration

```bash
# Set up Claude Desktop with your default WeaveMCP server
weave setup

# Preview setup changes without applying them
weave setup --dry-run

# Check current configuration
weave status
```

### Proxy Server

```bash
# Start STDIO proxy server (used internally by Claude Desktop)
weave proxy

# Start proxy with verbose logging
weave proxy --verbose
```

### Management

```bash
# Upgrade existing MCP servers to use Weave
weave upgrade

# Preview upgrade changes
weave upgrade --dry-run

# Remove WeaveMCP servers from Claude Desktop
weave remove --organization myorg

# Remove all WeaveMCP servers
weave remove --all
```

### Server Management

```bash
# List configured servers
weave server list

# Switch to different server
weave server switch staging

# Add server without token
weave server add production https://prod.weavemcp.com

# Remove server configuration
weave server remove staging
```

## How It Works

1. **Login**: Authenticate with WeaveMCP using OAuth through your browser
2. **Setup**: Weave configures Claude Desktop to use the `weave proxy` command
3. **Proxy**: When Claude Desktop starts, it runs `weave proxy` which:
   - Fetches your virtual server configuration from WeaveMCP
   - Establishes authenticated connections to your MCP servers
   - Proxies all MCP requests between Claude and your servers

### Architecture

```
Claude Desktop ↔ Weave Proxy (STDIO) ↔ WeaveMCP Infrastructure ↔ Your MCP Servers
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
    "weavemcp-yourorg": {
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
weave login
```

**"No default virtual server found"**  
1. Visit [WeaveMCP Dashboard](https://weavemcp.com)
2. Create a virtual server
3. Run `uvx weave setup`

**Claude Desktop not connecting**
1. Restart Claude Desktop after running `weave setup`
2. Check logs: `tail -f ~/.weavemcp/proxy.log`
3. Test proxy: `uvx weave proxy --verbose`

### Debug Mode

Run any command with `--verbose` for detailed logging:

```bash
weave proxy --verbose
weave setup --verbose
```

### Getting Help

```bash
# General help
weave --help

# Command-specific help
weave setup --help
weave proxy --help
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

---

Made with ❤️ by the [IronPress Apps](https://ironpressapps.com) team
