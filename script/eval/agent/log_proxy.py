"""Transparent HTTP proxy in front of llama-server that appends every API exchange to a JSONL log.

One line per request to an API path: time, client address, User-Agent, method, path, status, latency, request
body (parsed JSON) and response body (parsed JSON, or the raw SSE text of a streamed response). The web UI's
static files pass through unlogged. Responses are re-sent chunked as they arrive, so streaming still streams.

    python script/eval/agent/log_proxy.py --listen 127.0.0.1:8080,<tailscale-ip>:8080 \\
        --upstream 127.0.0.1:8081 --log output/serve/<model>/calls.jsonl
"""

import argparse, http.client, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Setting =================================================
LOGGED = ("/v1/", "/apply-template", "/completion", "/tokenize", "/chat/completions")
HOP    = {"connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization", "host"}
LOCK   = threading.Lock()

# Functions ===============================================
def parse(raw: bytes):
    """JSON body as an object, anything else (SSE streams) as text."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw.decode("utf-8", "replace")


def make_handler(upstream: str, log_path: str):
    up_host, up_port = upstream.rsplit(":", 1)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def proxy(self):
            t0 = time.time()
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            up = http.client.HTTPConnection(up_host, int(up_port), timeout=3600)
            up.request(self.command, self.path, body=body or None,
                       headers={k: v for k, v in self.headers.items() if k.lower() not in HOP})
            resp = up.getresponse()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in HOP and k.lower() != "content-length":
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            chunks = []
            while True:
                try:
                    data = resp.read1(65536)
                except http.client.IncompleteRead as e:     # upstream died mid-stream: forward what came, then end
                    data = e.partial
                    if data:
                        chunks.append(data)
                        self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                    break
                if not data:
                    break
                chunks.append(data)
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            up.close()
            if self.path.startswith(LOGGED):
                rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t0)), "client": self.client_address[0],
                       "method": self.command, "path": self.path, "status": resp.status,
                       "latency_s": round(time.time() - t0, 3),
                       "headers": {"user-agent": self.headers.get("User-Agent", "")},
                       "request": parse(body) if body else None, "response": parse(b"".join(chunks))}
                with LOCK, open(log_path, "a") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        do_GET = do_POST = do_PUT = do_DELETE = do_OPTIONS = proxy

    return Handler


# Run =====================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--listen", required=True, help="comma-separated host:port list")
    ap.add_argument("--upstream", required=True, help="llama-server host:port")
    ap.add_argument("--log", required=True)
    a = ap.parse_args()
    handler = make_handler(a.upstream, a.log)
    for addr in a.listen.split(","):
        host, port = addr.rsplit(":", 1)
        s = ThreadingHTTPServer((host, int(port)), handler)
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
        print(f"listening on {addr} -> {a.upstream}, logging to {a.log}", flush=True)
    threading.Event().wait()
