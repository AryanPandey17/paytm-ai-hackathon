"""Verifies the LLM fallback chain: exhausted provider -> next provider -> offline rules."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app import llm


def _server(port: int, status: int, body: dict):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("content-length", 0)))
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *a):
            pass

    s = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def test_fallback_chain():
    _server(9101, 429, {"error": {"message": "quota exceeded"}})
    _server(9102, 200, {"choices": [{"message": {"content": "<think>x</think>hello from backup"}}]})
    llm.ORDER[:] = ["sarvam", "gemini", "rules"]
    llm.PROVIDERS["sarvam"].url, llm.PROVIDERS["sarvam"].key = "http://127.0.0.1:9101", "k1"
    llm.PROVIDERS["gemini"].url, llm.PROVIDERS["gemini"].key = "http://127.0.0.1:9102", "k2"

    r = asyncio.run(llm.chat([{"role": "user", "content": "hi"}], rules=lambda: "rules"))
    assert r.provider == "gemini" and r.text == "hello from backup" and r.fallback_used
    st = {s["name"]: s for s in llm.status()}
    assert st["sarvam"]["state"].startswith("cooldown")

    # second call skips the exhausted provider directly
    r2 = asyncio.run(llm.chat([{"role": "user", "content": "hi"}], rules=lambda: "rules"))
    assert r2.provider == "gemini" and not r2.fallback_used

    # everything down -> offline rules
    llm.PROVIDERS["gemini"].url = "http://127.0.0.1:9199"  # nothing listening
    r3 = asyncio.run(llm.chat([{"role": "user", "content": "hi"}], rules=lambda: "rules"))
    assert r3.provider == "rules" and r3.text == "rules"
