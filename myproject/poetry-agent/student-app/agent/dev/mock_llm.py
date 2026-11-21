"""Mock OpenAI-compatible gateway for LOCAL walk-throughs only (stdlib, 127.0.0.1, no real model, no secrets).

    python dev/mock_llm.py                       # MOCK_LLM_PORT (default 8799)

Behaviour is chosen by MOCK_LLM_MODE (default "ok"):
  ok        rewords the scripted sentence, keeps only the given facts' ids in `uses`
  leak      returns a "fact" that is not in the context ("后来唐军收复了长安，安禄山被杀。" / a year)  -> reviewer must reject
  garbage   returns non-JSON text as the message content
  timeout   sleeps longer than the agent's primary timeout (MOCK_LLM_SLEEP, default 12 s)
  5xx       HTTP 503 with an error body
  empty     200 with an empty message

Every request body is appended as one JSON line to MOCK_LLM_LOG (default ./mock_llm_requests.jsonl next to this file),
so the poet-context check (A-10) can read what a model would have been sent. Streaming (`stream: true`) is supported:
the reply is sent as server-sent events with the same content.
"""
from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("MOCK_LLM_PORT", "8799"))
LOG = Path(os.environ.get("MOCK_LLM_LOG", HERE / "mock_llm_requests.jsonl"))


def reply_for(mode: str, body: dict) -> tuple[int, str]:
    user = body["messages"][-1]["content"]
    try:
        payload = json.loads(user)
    except ValueError:
        payload = {"script_say": "", "facts": []}
    facts = payload.get("facts", [])
    say = payload.get("script_say", "")
    ids = [f["id"] for f in facts]
    if mode == "ok":
        content = json.dumps({"say": say + (" 就是这样。" if say and len(say) < 60 else ""), "uses": ids}, ensure_ascii=False)
    elif mode == "leak":
        content = json.dumps({"say": "后来唐军收复了长安，安禄山在八年后被杀。", "uses": ids}, ensure_ascii=False)
    elif mode == "garbage":
        content = "我是一个乐于助人的模型，这里是你要的答案：<<<not json>>>"
    elif mode == "empty":
        content = ""
    else:
        content = ""
    return 200, content


class Handler(BaseHTTPRequestHandler):
    server_version = "mock-llm/0.1"

    def log_message(self, fmt, *args):  # quiet; the log file is the record
        pass

    def _send(self, status: int, data: bytes, ctype: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/v1/models"):
            self._send(200, json.dumps({"object": "list", "data": [{"id": "mock-model", "object": "model"}]}).encode())
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            return self._send(404, b'{"error":"not found"}')
        mode = os.environ.get("MOCK_LLM_MODE", "ok")
        length = int(self.headers.get("content-length", "0") or 0)
        raw = self.rfile.read(length)
        if self.headers.get("authorization", "") != f"Bearer {os.environ.get('MOCK_LLM_KEY', 'mock-key')}":
            return self._send(401, b'{"error":"bad key"}')
        try:
            body = json.loads(raw)
        except ValueError:
            return self._send(400, b'{"error":"bad json"}')
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": time.time(), "mode": mode, "model": body.get("model"), "body": body}, ensure_ascii=False) + "\n")
        if mode == "5xx":
            return self._send(503, b'{"error":{"message":"mock upstream unavailable"}}')
        if mode == "timeout":
            time.sleep(float(os.environ.get("MOCK_LLM_SLEEP", "12")))
        status, content = reply_for(mode, body)
        usage = {"prompt_tokens": max(1, len(raw) // 4), "completion_tokens": max(1, len(content) // 2)}
        if body.get("stream"):
            chunk = {"id": "mock", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
            done = {"id": "mock", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage}
            data = (f"data: {json.dumps(chunk, ensure_ascii=False)}\n\ndata: {json.dumps(done)}\n\ndata: [DONE]\n\n").encode()
            return self._send(200, data, "text/event-stream")
        out = {"id": "mock", "object": "chat.completion", "model": body.get("model"),
               "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}], "usage": usage}
        self._send(status, json.dumps(out, ensure_ascii=False).encode())


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"mock-llm listening on http://127.0.0.1:{PORT}/v1  mode={os.environ.get('MOCK_LLM_MODE', 'ok')}  log={LOG}", flush=True)
    srv.serve_forever()
