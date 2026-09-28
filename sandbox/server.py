"""Local target service deployed from the verified image, with real HTTP traffic."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import policy

lock = threading.Lock()
posted = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):
        try:
            if self.path not in ("/payment", "/quote"):
                raise ValueError("Unknown endpoint")
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8192:
                raise ValueError("Request too large")
            data = json.loads(self.rfile.read(length))
            if self.path == "/quote":
                body=json.dumps({"fee_minor":policy.fee_minor(data["amount_minor"])}).encode()
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            key, amount = data["key"], data["amount_minor"]
            with lock:
                old = posted.get(key)
                should_post = policy.should_post(old["payload"] if old else None, str(amount))
                if should_post:
                    fee = policy.fee_minor(amount)
                    posted[key] = {"payload":str(amount), "fee_minor":fee, "postings":(old["postings"] if old else 0)+1}
                result = posted[key]
            body = json.dumps(result).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"error":str(e)[:100]}).encode()
            self.send_response(422)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("0.0.0.0",8080), Handler).serve_forever()
