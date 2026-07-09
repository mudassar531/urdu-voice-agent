"""
Health check HTTP server.
Serves /health, /network/topology, and /network/telephony endpoints.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from observability.network_topology import get_network_topology_snapshot

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler."""

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health" or parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        elif parsed.path == "/network/topology":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                limit = 100

            payload = get_network_topology_snapshot(limit=limit)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())
        elif parsed.path == "/network/telephony":
            from observability.telephony_latency import get_telephony_snapshot

            payload = get_telephony_snapshot()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())
        elif parsed.path == "/metrics":
            from observability.prometheus_metrics import get_metrics_output

            body, content_type = get_metrics_output()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress access logs


def start_health_server(port: int | None = None) -> None:
    """Start health check server in background thread."""
    if port is None:
        # Standalone worker deployment (no co-located token server claiming
        # $PORT): bind Render's assigned $PORT directly so the platform's
        # port-detection/health check passes. When co-located with the token
        # server (RUN_TOKEN_SERVER=1), that process already owns $PORT, so
        # fall back to HEALTH_PORT to avoid a bind conflict.
        run_token_server = os.getenv("RUN_TOKEN_SERVER", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        render_port = os.getenv("PORT")
        if not run_token_server and render_port:
            port = int(render_port)
        else:
            port = int(os.getenv("HEALTH_PORT", "8082"))

    def _run():
        try:
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            logger.info(
                f"Health server started on port {port} "
                "(/health, /metrics, /network/topology, /network/telephony)"
            )
            server.serve_forever()
        except Exception as e:
            logger.error(f"Health server failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
