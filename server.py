#!/usr/bin/env python3
"""kiro-relay: Bidirectional task relay with file transfer support."""
import json
import os
import base64
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DATA_DIR = Path(__file__).parent / "data"
FILES_DIR = DATA_DIR / "files"
INBOX_FILE = DATA_DIR / "inbox.json"
TASKS_FILE = DATA_DIR / "tasks.json"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)

def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

INBOX = load_json(INBOX_FILE, [])
TASKS = load_json(TASKS_FILE, [])
HEARTBEAT = {"last": None}


class Handler(BaseHTTPRequestHandler):
    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/tasks":
            pending = list(TASKS)
            TASKS.clear()
            save_json(TASKS_FILE, TASKS)
            self._respond(200, {"tasks": pending})
            if pending:
                print(f"[OUT] Delivered {len(pending)} task(s)", flush=True)

        elif path == "/status":
            self._respond(200, {
                "status": "alive",
                "inbox_count": len(INBOX),
                "pending_tasks": len(TASKS),
                "heartbeat": HEARTBEAT["last"],
            })

        elif path == "/inbox":
            params = parse_qs(urlparse(self.path).query)
            last_n = int(params.get("last", [10])[0])
            self._respond(200, {"messages": INBOX[-last_n:]})

        elif path.startswith("/files/"):
            filename = path[7:]
            filepath = FILES_DIR / filename
            if filepath.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                data = filepath.read_bytes()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._respond(404, {"error": "not found"})

        elif path == "/files":
            files = [f.name for f in FILES_DIR.iterdir() if f.is_file()]
            self._respond(200, {"files": files})

        else:
            self._respond(200, {"status": "alive", "endpoints": [
                "GET /tasks", "GET /status", "GET /inbox?last=N",
                "GET /files", "GET /files/<name>",
                "POST /", "POST /heartbeat", "POST /files/<name>",
                "PUT /tasks",
            ]})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/heartbeat":
            HEARTBEAT["last"] = datetime.now().isoformat()
            self._respond(200, {"status": "ok"})

        elif path.startswith("/files/"):
            filename = path[7:]
            data = self._read_body()
            filepath = FILES_DIR / filename
            filepath.write_bytes(data)
            md5 = hashlib.md5(data).hexdigest()
            print(f"[FILE] Received: {filename} ({len(data)} bytes, md5:{md5})", flush=True)
            self._respond(200, {"status": "stored", "filename": filename, "size": len(data), "md5": md5})

        else:
            body = json.loads(self._read_body().decode() or "{}")
            body["received_at"] = datetime.now().isoformat()
            INBOX.append(body)
            save_json(INBOX_FILE, INBOX)
            print(f"[IN] {body.get('type','?')}: {body.get('content','')[:150]}", flush=True)
            self._respond(200, {"status": "ok"})

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/tasks":
            body = json.loads(self._read_body().decode() or "{}")
            body["queued_at"] = datetime.now().isoformat()
            TASKS.append(body)
            save_json(TASKS_FILE, TASKS)
            print(f"[QUEUED] {body.get('content','')[:150]}", flush=True)
            self._respond(200, {"status": "queued", "pending": len(TASKS)})
        else:
            self._respond(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9200))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[kiro-relay] Listening on 0.0.0.0:{port}", flush=True)
    print(f"[kiro-relay] Data dir: {DATA_DIR}", flush=True)
    server.serve_forever()
