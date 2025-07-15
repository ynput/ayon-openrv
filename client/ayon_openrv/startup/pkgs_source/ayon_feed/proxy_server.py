import http.server
import socketserver
import threading
import urllib.parse
import http.client
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ReverseProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler with reverse proxy capabilities."""

    # Class variables to store configuration
    serve_directory = None
    proxy_paths = None
    target_host = None
    auth_headers = None

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header(
            "Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _proxy_request(self):
        if not self.target_host:
            self.send_error(500, "No target host configured for proxy")
            return

        # Parse target URL
        url = urllib.parse.urlparse(self.target_host)

        # Handle both hostname and full URL formats
        if url.scheme and url.netloc:
            # Full URL provided
            target_host = url.netloc
            target_scheme = url.scheme
        else:
            # Just hostname provided, assume HTTPS
            # Extract host from URL-like string
            cleaned_host = self.target_host.replace(
                "https://", "").replace("http://", "")
            if "/" in cleaned_host:
                target_host = cleaned_host.split("/")[0]
            else:
                target_host = cleaned_host
            target_scheme = "https" if "https" in self.target_host else "http"

        logger.debug(
            f"Parsed target: scheme={target_scheme}, host={target_host}")

        path = self.path

        # Don't strip the proxy path prefix - keep the full path
        # The AYON server expects the full API paths like /api/info,
        # /api/projects, etc.

        # Log proxy request details
        logger.debug(
            f"Proxying {self.command} request "
            f"to {target_scheme}://{target_host}{path}")
        logger.debug(
            f"Target host: {target_host}, Target scheme: {target_scheme}")

        # Forward request to target server
        conn_class = (
            http.client.HTTPSConnection
            if target_scheme == "https"
            else http.client.HTTPConnection
        )
        conn = conn_class(target_host)
        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ['host', 'connection']
        }
        headers["Host"] = target_host
        headers["Connection"] = "close"

        # Log incoming request headers for debugging
        logger.debug("Incoming request headers:")
        for k, v in self.headers.items():
            logger.debug(f"  {k}: {v}")

        # Add authentication headers if configured
        if self.auth_headers:
            headers.update(self.auth_headers)
            logger.debug(
                f"Added auth headers: {list(self.auth_headers.keys())}")
            for key, value in self.auth_headers.items():
                logger.debug(
                    f"Auth header {key}: {value[:20]}..."
                    if len(value) > 20
                    else f"Auth header {key}: {value}"
                )

        body = None
        if self.command in ["POST", "PUT", "PATCH"]:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            logger.debug(f"Request body length: {content_length}")

        try:
            logger.debug(
                f"Sending {self.command} request "
                f"with headers: {dict(headers)}"
            )
            conn.request(self.command, path, body=body, headers=headers)
            res = conn.getresponse()

            logger.debug(f"Received response status: {res.status}")

            # Read the full response body first to log it
            response_body = res.read()
            logger.debug(f"Response body length: {len(response_body)}")
            preview_body_text =(
               response_body[:500].decode('utf-8', errors='replace')
               if response_body else 'Empty'
            )
            logger.debug(
                f"Response body preview: {preview_body_text}")

            # Log response headers for debugging authentication issues
            logger.debug("Response headers:")
            for header, value in res.getheaders():
                logger.debug(f"  {header}: {value}")

            self.send_response(res.status)

            # Copy headers (excluding hop-by-hop headers)
            for header, value in res.getheaders():
                if header.lower() not in [
                    "connection", "transfer-encoding", "keep-alive"
                ]:
                    self.send_header(header, value)
            self._set_cors_headers()
            self.end_headers()

            # Write the response body
            if response_body:
                self.wfile.write(response_body)
            else:
                logger.warning(
                    f"Empty response body for {self.command} {path}")
        except Exception as e:
            logger.error(f"Error during proxy request: {e}", exc_info=True)
            self.send_error(502, f"Bad Gateway: {str(e)}")
        finally:
            conn.close()

    def _serve_local_file(self):
        # Resolve safe file path
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"

        # Security check: detect path traversal attempts
        if (
            ".." in path
            or path.startswith("/etc/")
            or path.startswith("\\etc\\")
        ):
            self.send_error(403, "Forbidden")
            return

        # Use pathlib for path operations
        requested_path = Path(path.lstrip("/"))
        filepath = (self.serve_directory / requested_path).resolve()

        # Additional security check: ensure the resolved path is within
        # serve_directory
        try:
            filepath.relative_to(self.serve_directory.resolve())
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if not filepath.exists() or not filepath.is_file():
            self.send_error(404, "Not Found")
            return

        # Guess content type based on suffix
        content_type_map = {
            '.html': 'text/html',
            '.js': 'text/javascript',
            '.css': 'text/css',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.json': 'application/json',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon'
        }

        content_type = content_type_map.get(
            filepath.suffix.lower(), 'text/plain')

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self._set_cors_headers()
        self.end_headers()

        with open(filepath, "rb") as f:
            self.wfile.write(f.read())

    def handle_request(self):
        # Extract path without query string for matching
        path_only = self.path.split('?')[0]

        # Check if path should be proxied
        if (
            self.proxy_paths
            and any(
                path_only.startswith(proxy_path)
                for proxy_path in self.proxy_paths
            )
        ):
            self._proxy_request()
        else:
            self._serve_local_file()

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PUT(self):
        self.handle_request()

    def do_DELETE(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()


class ProxyServer:
    """Encapsulates the reverse proxy server functionality."""

    def __init__(self, host="localhost", port=8000, serve_directory=None,
                 proxy_paths=None, target_host=None, auth_headers=None):
        self.host = host
        self.port = port
        self.serve_directory = Path(serve_directory or Path.cwd())
        self.proxy_paths = proxy_paths or []
        self.target_host = target_host
        self.auth_headers = auth_headers or {}
        self.server = None
        self.server_thread = None

    def create_handler(self):
        """Create a handler class with bound configuration."""

        class ConfiguredHandler(ReverseProxyHandler):
            serve_directory = self.serve_directory
            proxy_paths = self.proxy_paths
            target_host = self.target_host
            auth_headers = self.auth_headers

        return ConfiguredHandler

    def start(self, daemon=True):
        """Start the server in a separate thread."""
        handler_class = self.create_handler()
        self.server = socketserver.TCPServer(
            (self.host, self.port), handler_class)

        def run():
            print(f"Serving on http://{self.host}:{self.port}")
            print(f"Serving files from: {self.serve_directory}")
            if self.proxy_paths and self.target_host:
                print(f"Proxying {self.proxy_paths} to {self.target_host}")
            self.server.serve_forever()

        self.server_thread = threading.Thread(target=run, daemon=daemon)
        self.server_thread.start()

    def stop(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()
            self.server_thread.join()


def start_proxy_server(
    host="localhost",
    port=8000,
    serve_directory=None,
    proxy_paths=None,
    target_host=None,
    auth_headers=None,
    daemon=True,
):
    """
    Start a reverse proxy server with the given configuration.

    Args:
        host: The hostname to bind to (default: "localhost")
        port: The port to bind to (default: 8000)
        serve_directory: Directory to serve files from
            (default: current directory)
        proxy_paths: List of paths to proxy (e.g., ["/api", "/graphql"])
        target_host: Target host for proxied requests
            (e.g., "https://api.example.com" or "http://localhost:5000")
        auth_headers: Dictionary of authentication headers to add to proxy
            requests (e.g., {"Authorization": "Bearer token"})
        daemon: Whether to run the server thread as a daemon (default: True)

    Returns:
        ProxyServer instance that can be used to stop the server
    """
    server = ProxyServer(host=host, port=port, serve_directory=serve_directory,
                        proxy_paths=proxy_paths, target_host=target_host,
                        auth_headers=auth_headers)
    server.start(daemon=daemon)
    return server


# Example usage and testing
if __name__ == "__main__":
    # Test the server with custom configuration
    server = start_proxy_server(
        host="localhost",
        port=8080,
        serve_directory=Path.cwd(),
        proxy_paths=["/api", "/graphql"],
        target_host="https://jsonplaceholder.typicode.com",
        daemon=False,
    )

    print("\nReverse proxy server is running...")
    print("Try accessing:")
    print("  - http://localhost:8080/ for local files")
    print("  - http://localhost:8080/api/posts for proxied content")
    print("\nPress Ctrl+C to stop the server")

    try:
        # Keep the main thread alive
        server.server_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.stop()
        print("Server stopped")
