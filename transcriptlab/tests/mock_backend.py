"""A CPU-only mock of an OpenAI-compatible /v1/completions server (vLLM-style fields), for end-to-end tests.

Each request gets one edit call in the requested format. Whether that call carries the look-alike closer slip (the
backtick that ends a string instead of the real delimiter) is a deterministic function of the prompt, so a test can
check that the frozen judge flags exactly the slipped calls the mock emitted.
"""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

S = '<|"|>'


def slipped(prompt) -> bool:
    raw = json.dumps(prompt) if not isinstance(prompt, str) else prompt
    return int(hashlib.sha1(raw.encode()).hexdigest()[:8], 16) % 3 == 0


def completion(fmt: str, bad: bool) -> tuple[str, int | None]:
    """-> (text, stop_reason). Gemma: the server stops on <tool_call|> (token 49) and does not echo it."""
    if fmt == "gemma4":
        old = f"{S}x = 1`," if bad else f"{S}x = 1{S},"
        return (f"<|channel>thought\nEdit the assignment.<channel|><|tool_call>call:edit_file{{file_path:{S}src/a.py{S},"
                f"old_string:{old}new_string:{S}x = 2{S}}}", 49)
    old = '"x = 1`, ' if bad else '"x = 1", '
    return ('<think>\nEdit the assignment.\n</think>\n\n<tool_call>\n{"name": "edit_file", "arguments": '
            '{"file_path": "src/a.py", "old_string": ' + old + '"new_string": "x = 2"}}\n</tool_call>', None)


class MockServer:
    def __init__(self, fmt: str = "gemma4", served: str = "mock", max_model_len: int = 32768):
        self.fmt, self.served, self.max_model_len = fmt, served, max_model_len
        self.log: list[dict] = []
        self._lock = threading.Lock()
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _json(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    return self._json(200, {"object": "list", "data": [{"id": outer.served, "max_model_len": outer.max_model_len}]})
                self._json(404, {"error": "not found"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                if not self.path.rstrip("/").endswith("/completions"):
                    return self._json(404, {"error": "not found"})
                bad = slipped(body.get("prompt"))
                text, stop = completion(outer.fmt, bad)
                with outer._lock:
                    outer.log.append({"bad": bad, "stream": bool(body.get("stream")), "seed": body.get("seed")})
                usage = {"prompt_tokens": 1, "completion_tokens": 40, "total_tokens": 41}
                if not body.get("stream"):
                    return self._json(200, {"object": "text_completion", "choices": [
                        {"index": 0, "text": text, "finish_reason": "stop", "stop_reason": stop}], "usage": usage})
                self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
                for ch in ({"choices": [{"index": 0, "text": text, "finish_reason": None}]},
                           {"choices": [{"index": 0, "text": "", "finish_reason": "stop", "stop_reason": stop}]},
                           {"choices": [], "usage": usage}):
                    self.wfile.write(f"data: {json.dumps(ch)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}/v1"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
