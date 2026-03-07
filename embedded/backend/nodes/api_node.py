import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.request import urlopen, Request
from urllib.error import URLError

from nodes.base import Node, MessageBus, Message

log = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


class APINode(Node):
    """Exposes a REST API for external clients to interact with the system."""

    def __init__(self, bus: MessageBus, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        super().__init__("api", bus)
        self.host = host
        self.port = port
        self._state = "IDLE"
        self._last_transcription = ""

        self.subscribe("state/changed", self._on_state_changed)
        self.subscribe("state/transcription_text", self._on_transcription)
        self.subscribe("api/questions/random", self._on_questions_random)

        node_ref = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/status":
                    self._json_response(200, {
                        "state": node_ref._state,
                        "last_transcription": node_ref._last_transcription,
                    })
                else:
                    self._json_response(404, {"error": "not found"})

            def do_POST(self):
                if self.path == "/speak":
                    body = self._read_body()
                    text = body.get("text", "")
                    if not text:
                        self._json_response(400, {"error": "missing 'text' field"})
                        return
                    node_ref.publish("tts/speak", text)
                    self._json_response(200, {"status": "ok"})

                elif self.path == "/button":
                    body = self._read_body()
                    name = body.get("name", "")
                    if name not in ("base_down", "base_up", "open_lid"):
                        self._json_response(400, {"error": "name must be 'base_down', 'base_up', or 'open_lid'"})
                        return
                    node_ref.publish("serial/trigger_button", {"name": name})
                    self._json_response(200, {"status": "ok"})

                else:
                    self._json_response(404, {"error": "not found"})

            def _read_body(self) -> dict:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {}

            def _json_response(self, code: int, data: dict):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def log_message(self, fmt, *args):
                log.info(f"[api] {fmt % args}")

        self._handler_class = Handler

    def _on_questions_random(self, msg: Message):
        try:
            resp = urlopen("http://10.31.156.57:5000/questions/random", timeout=5)
            data = json.loads(resp.read())
            text = data.get("text", "") if isinstance(data, dict) else str(data)
            log.info(f"[api] random question: {text!r}")
            self.publish("api/questions/random/response", text)
        except (URLError, json.JSONDecodeError, OSError) as e:
            log.error(f"[api] failed to fetch random question: {e}")

    def _on_state_changed(self, msg: Message):
        self._state = msg.data["to"].name

    def _on_transcription(self, msg: Message):
        self._last_transcription = msg.data

    def _run(self):
        server = HTTPServer((self.host, self.port), self._handler_class)
        server.timeout = 0.5
        log.info(f"[api] HTTP server listening on {self.host}:{self.port}")
        while self._running:
            server.handle_request()
        server.server_close()
