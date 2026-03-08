import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.request import urlopen, Request
from urllib.error import URLError

from nodes.base import Node, MessageBus, Message, Question

log = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
# BACKEND_URL = "http://10.31.156.57:5000"
# BACKEND_URL = "https://superdevilishly-unhomely-carol.ngrok-free.dev"
# BACKEND_URL = "https://overstoutly-unimitated-kera.ngrok-free.dev"
BACKEND_URLS = [
    "http://10.31.156.57:5000",
    "https://superdevilishly-unhomely-carol.ngrok-free.dev",
    "https://overstoutly-unimitated-kera.ngrok-free.dev",
]


class APINode(Node):
    """Exposes a REST API for external clients to interact with the system."""

    def __init__(
        self, bus: MessageBus, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
    ):
        super().__init__("api", bus)
        self.host = host
        self.port = port
        self._state = "IDLE"
        self._last_transcription = ""
        self._backend_url: str | None = None

        self.subscribe("state/changed", self._on_state_changed)
        self.subscribe("state/transcription_text", self._on_transcription)
        self.subscribe("api/questions/random", self._on_questions_random)
        self.subscribe("api/submit", self._on_submit)
        self.subscribe("api/answers", self._on_answers)
        self.subscribe("api/similar", self._on_similar)

        node_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/status":
                    self._json_response(
                        200,
                        {
                            "state": node_ref._state,
                            "last_transcription": node_ref._last_transcription,
                        },
                    )
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
                        self._json_response(
                            400,
                            {
                                "error": "name must be 'base_down', 'base_up', or 'open_lid'"
                            },
                        )
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

    def _resolve_backend(self) -> str | None:
        if self._backend_url:
            return self._backend_url
        for url in BACKEND_URLS:
            try:
                urlopen(f"{url}/questions/random", timeout=3)
                self._backend_url = url
                log.info(f"[api] using backend: {url}")
                return url
            except (URLError, OSError):
                log.debug(f"[api] backend unreachable: {url}")
        log.error("[api] no reachable backend found")
        return None

    def _on_questions_random(self, msg: Message):
        base = self._resolve_backend()
        if not base:
            return
        try:
            resp = urlopen(f"{base}/questions/random", timeout=5)
            data = json.loads(resp.read())
            question = Question(id=data.get("id", 0), text=data.get("text", ""))
            log.info(f"[api] random question (id={question.id}): {question.text!r}")
            self.publish("api/questions/random/response", question)
        except (URLError, json.JSONDecodeError, OSError) as e:
            log.error(f"[api] failed to fetch random question: {e}")

    def _on_submit(self, msg: Message):
        base = self._resolve_backend()
        if not base:
            return
        question_id = msg.data["question_id"]
        payload = json.dumps(
            {
                "answer": msg.data["answer"],
                "uuid": msg.data["uuid"],
            }
        ).encode()
        url = f"{base}/questions/{question_id}/answers"
        try:
            req = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urlopen(req, timeout=3)
            log.info(
                f"[api] submitted answer for question {question_id}: {resp.status}"
            )
        except (URLError, OSError) as e:
            log.error(f"[api] failed to submit answer: {e}")

    def _on_answers(self, msg: Message):
        base = self._resolve_backend()
        if not base:
            return
        question_id = msg.data["question_id"]
        url = f"{base}/questions/{question_id}/answers"
        try:
            resp = urlopen(url, timeout=5)
            data = json.loads(resp.read())
            answers = [a.get("text", "") for a in data if isinstance(a, dict)]
            log.info(f"[api] fetched {len(answers)} answers for question {question_id}")
            self.publish("api/answers/response", answers)
        except (URLError, json.JSONDecodeError, OSError) as e:
            log.error(f"[api] failed to fetch answers: {e}")

    def _on_similar(self, msg: Message):
        base = self._resolve_backend()
        if not base:
            return
        question_id = msg.data["question_id"]
        uuid = msg.data["uuid"]
        url = f"{base}/questions/{question_id}/answers/{uuid}/similar"
        try:
            resp = urlopen(url, timeout=6)
            data = json.loads(resp.read())
            answer = data.get("answer", {}) if isinstance(data, dict) else {}
            text = answer.get("text", "") if isinstance(answer, dict) else ""
            log.info(f"[api] similar answer for question {question_id}: {text!r}")
            self.publish("api/similar/response", text)
        except (URLError, json.JSONDecodeError, OSError) as e:
            log.error(f"[api] failed to fetch similar answer: {e}")

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
