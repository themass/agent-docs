"""Minimal OpenAI-compatible fake: streams a fixed reply for /v1/chat/completions."""
import json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPLY = "你好，我在。"

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass
    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        stream = req.get("stream", False)
        self.server.requests.append(req)
        if not stream:
            body = json.dumps({"id":"x","object":"chat.completion","created":int(time.time()),
                "model":req.get("model","fake"),"choices":[{"index":0,"finish_reason":"stop",
                "message":{"role":"assistant","content":REPLY}}],
                "usage":{"prompt_tokens":5,"completion_tokens":3,"total_tokens":8}}).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("content-length",str(len(body))); self.end_headers(); self.wfile.write(body); return
        self.send_response(200); self.send_header("content-type","text/event-stream"); self.end_headers()
        def chunk(delta, finish=None, usage=None):
            c = {"id":"x","object":"chat.completion.chunk","created":int(time.time()),
                 "model":req.get("model","fake"),"choices":[{"index":0,"delta":delta,"finish_reason":finish}]}
            if usage: c["usage"]=usage
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode()); self.wfile.flush()
        chunk({"role":"assistant","content":""})
        for ch in REPLY:
            chunk({"content":ch})
        chunk({}, "stop", {"prompt_tokens":5,"completion_tokens":len(REPLY),"total_tokens":5+len(REPLY)})
        self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()

def serve(port=18080):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.requests = []
    import threading; threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
