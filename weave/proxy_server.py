"""STDIO proxy server using FastMCP for transport bridging"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from .mcp_proxy import MCPProxyClient, MCPProxyError, get_proxy_client


class ProxyServer:
    """STDIO proxy server that bridges to FastMCP HTTP endpoint"""

    def __init__(self, proxy_client: MCPProxyClient, verbose: bool = False):
        """
        Initialize proxy server

        Args:
            proxy_client: MCP proxy client for HTTP communication
            verbose: Enable verbose logging
        """
        self.proxy_client = proxy_client
        self.verbose = verbose
        self._logger = self._setup_logging()
        self._shutdown_event = asyncio.Event()
        self._proxy_server: Optional[FastMCP] = None

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for proxy server"""
        logger = logging.getLogger("weavemcp.proxy.server")

        # Avoid duplicate handlers
        if logger.handlers:
            return logger

        # Always add a handler to prevent default stdout logging
        # Use stderr or file to avoid interfering with STDIO JSON-RPC
        if self.verbose:
            # Verbose mode: log to stderr
            handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        else:
            # Non-verbose mode: log to file only to avoid STDIO interference
            log_path = Path.home() / ".weavemcp" / "proxy.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            handler = logging.FileHandler(log_path)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.ERROR)  # Only log errors to reduce noise

        logger.propagate = False  # Prevent duplicate logs
        return logger

    async def start(self):
        """
        Start the STDIO proxy server

        Raises:
            MCPProxyError: If proxy server fails to start
        """
        try:
            self._logger.info("Starting WeaveMCP STDIO proxy server...")

            # Create FastMCP client with HTTP transport
            mcp_client = await self.proxy_client.create_client()

            # Create proxy server using FastMCP.as_proxy()
            self._proxy_server = FastMCP.as_proxy(
                mcp_client, name="WeaveMCP STDIO Proxy"
            )

            self._logger.info("Created FastMCP proxy server")

            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # Start the proxy server with STDIO transport
            self._logger.info("Starting STDIO transport...")

            # Run the proxy server
            await self._run_proxy_server()

        except Exception as e:
            self._logger.error(f"Failed to start proxy server: {e}")
            raise MCPProxyError(f"Failed to start proxy server: {e}")

    async def _run_proxy_server(self):
        """Run the proxy server with proper error handling"""
        try:
            # Create a task for the proxy server
            server_task = asyncio.create_task(
                self._proxy_server.run_async(transport="stdio")
            )

            # Wait for either the server to complete or shutdown signal
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())

            self._logger.info("Proxy server running on STDIO transport")

            # Wait for either completion or shutdown
            done, pending = await asyncio.wait(
                [server_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Check if server task completed with error
            if server_task in done:
                try:
                    await server_task
                except Exception as e:
                    self._logger.error(f"Proxy server error: {e}")
                    raise

        except asyncio.CancelledError:
            self._logger.info("Proxy server cancelled")
        except Exception as e:
            self._logger.error(f"Proxy server runtime error: {e}")
            raise

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            self._logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.shutdown())

        # Setup signal handlers (Unix only)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, signal_handler)

    async def shutdown(self):
        """Shutdown the proxy server gracefully"""
        self._logger.info("Shutting down proxy server...")

        # Signal shutdown
        self._shutdown_event.set()

        # Close proxy client
        if self.proxy_client:
            await self.proxy_client.close()

        self._logger.info("Proxy server shutdown complete")


async def run_proxy_server(
    server_url: Optional[str] = None,
    token: Optional[str] = None,
    server_alias: Optional[str] = None,
    verbose: bool = False,
):
    """
    Run the STDIO proxy server

    Args:
        server_url: Optional server URL override
        token: Optional token override
        server_alias: Optional server alias to use
        verbose: Enable verbose logging

    Raises:
        MCPProxyError: If proxy server fails to start or run
    """
    proxy_client = None

    try:
        # Get proxy client
        proxy_client = await get_proxy_client(server_url, token, server_alias)

        # Create and start proxy server
        server = ProxyServer(proxy_client, verbose=verbose)
        await server.start()

    except KeyboardInterrupt:
        print("\nReceived interrupt signal, shutting down...", file=sys.stderr)
    except Exception as e:
        print(f"Proxy server error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if proxy_client:
            await proxy_client.close()
