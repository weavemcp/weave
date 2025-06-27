"""Local HTTP server for receiving authentication tokens"""

import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Tuple, Callable


class AuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for authentication callbacks"""

    def __init__(self, token_callback: Callable[[str, str], None], *args, **kwargs):
        self.token_callback = token_callback
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests to /callback"""
        parsed_url = urlparse(self.path)

        if parsed_url.path == "/callback":
            query_params = parse_qs(parsed_url.query)
            token = query_params.get("token", [None])[0]
            server_url = query_params.get("server", [None])[0]

            if token and server_url:
                # Call the callback with the token
                self.token_callback(token, server_url)

                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                success_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>SuperMCP CLI - Authentication Success</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }}
                        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        .success {{ color: #22c55e; font-size: 48px; margin-bottom: 20px; }}
                        h1 {{ color: #333; margin-bottom: 10px; }}
                        p {{ color: #666; line-height: 1.6; }}
                        .close-note {{ margin-top: 30px; padding: 15px; background: #f0f9ff; border-radius: 5px; color: #0369a1; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Authentication Successful!</h1>
                        <p>Your SuperMCP CLI has been successfully configured.</p>
                        <p>Server: <strong>{server_url}</strong></p>
                        <div class="close-note">
                            <strong>You can now close this browser tab</strong><br>
                            Return to your terminal to continue using the SuperMCP CLI.
                        </div>
                    </div>
                </body>
                </html>
                """

                self.wfile.write(success_html.encode("utf-8"))
            else:
                # Send error response
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                error_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>SuperMCP CLI - Authentication Error</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
                        .container { max-width: 500px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                        .error { color: #ef4444; font-size: 48px; margin-bottom: 20px; }
                        h1 { color: #333; margin-bottom: 10px; }
                        p { color: #666; line-height: 1.6; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error">❌</div>
                        <h1>Authentication Failed</h1>
                        <p>Missing token or server information in the callback.</p>
                        <p>Please try the login process again.</p>
                    </div>
                </body>
                </html>
                """

                self.wfile.write(error_html.encode("utf-8"))
        else:
            # Handle other paths
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        """Suppress default HTTP server logging"""
        pass


class AuthServer:
    """Local HTTP server for authentication callbacks"""

    def __init__(self):
        self.server = None
        self.thread = None
        self.port = None
        self.token = None
        self.server_url = None
        self.received_callback = False

    def _token_callback(self, token: str, server_url: str) -> None:
        """Called when token is received"""
        self.token = token
        self.server_url = server_url
        self.received_callback = True

    def find_available_port(
        self, start_port: int = 8080, max_attempts: int = 10
    ) -> int:
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("localhost", port))
                sock.close()
                return port
            except OSError:
                continue

        raise RuntimeError(
            f"Could not find available port in range {start_port}-{start_port + max_attempts}"
        )

    def start(self, port: Optional[int] = None) -> int:
        """
        Start the authentication server

        Args:
            port: Port to use (auto-detected if None)

        Returns:
            Port number the server is running on
        """
        if port is None:
            port = self.find_available_port()

        self.port = port

        # Create handler class with token callback
        def handler_class(*args, **kwargs):
            return AuthCallbackHandler(self._token_callback, *args, **kwargs)

        self.server = HTTPServer(("localhost", port), handler_class)

        # Start server in background thread
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        return port

    def wait_for_callback(
        self, timeout: float = 300.0
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Wait for authentication callback

        Args:
            timeout: Timeout in seconds (default 5 minutes)

        Returns:
            Tuple of (token, server_url) or (None, None) if timeout
        """
        start_time = time.time()

        while not self.received_callback and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if self.received_callback:
            return self.token, self.server_url
        else:
            return None, None

    def stop(self) -> None:
        """Stop the authentication server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

        if self.thread:
            self.thread.join(timeout=1.0)

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
