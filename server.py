#!/usr/bin/env python3
"""kiro-relay: Bidirectional relay with long-polling."""
import json
import os
import hashlib
import threading
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
ACKS = {}
HEARTBEAT = {"last": None}

# Long-poll events
inbox_event = threading.Event()
tasks_event = threading.Event()


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
        params = parse_qs(urlparse(self.path).query)

        if path == "/tasks":
            # Long-poll: if no tasks, wait up to timeout seconds
            timeout = float(params.get("timeout", [0])[0])
            if not TASKS and timeout > 0:
                tasks_event.clear()
                tasks_event.wait(timeout=timeout)
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
                "acked_tasks": len(ACKS),
                "heartbeat": HEARTBEAT["last"],
            })

        elif path == "/inbox":
            last_n = int(params.get("last", [10])[0])
            self._respond(200, {"messages": INBOX[-last_n:]})

        elif path == "/inbox/wait":
            # Long-poll: block until new inbox message or timeout
            timeout = float(params.get("timeout", [30])[0])
            count_before = len(INBOX)
            inbox_event.clear()
            inbox_event.wait(timeout=timeout)
            new_msgs = INBOX[count_before:]
            self._respond(200, {"new": len(new_msgs) > 0, "messages": new_msgs})

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
                "GET /tasks?timeout=N", "GET /status", "GET /inbox?last=N",
                "GET /inbox/wait?timeout=N", "GET /files", "GET /files/<name>",
                "POST /", "POST /heartbeat", "POST /ack/<task_id>",
                "POST /files/<name>", "PUT /tasks",
            ]})

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/heartbeat":
            HEARTBEAT["last"] = datetime.now().isoformat()
            self._respond(200, {"status": "ok"})

        elif path.startswith("/ack/"):
            task_id = path[5:]
            ACKS[task_id] = datetime.now().isoformat()
            print(f"[ACK] {task_id}", flush=True)
            self._respond(200, {"status": "acked", "task_id": task_id})

        elif path.startswith("/files/"):
            filename = path[7:]
            data = self._read_body()
            filepath = FILES_DIR / filename
            filepath.write_bytes(data)
            md5 = hashlib.md5(data).hexdigest()
            print(f"[FILE] {filename} ({len(data)}B)", flush=True)
            self._respond(200, {"status": "stored", "filename": filename, "size": len(data), "md5": md5})

        else:
            body = json.loads(self._read_body().decode() or "{}")
            body["received_at"] = datetime.now().isoformat()
            INBOX.append(body)
            save_json(INBOX_FILE, INBOX)
            print(f"[IN] {body.get('type','?')}: {body.get('content','')[:100]}", flush=True)
            inbox_event.set()  # Wake up any long-pollers
            self._respond(200, {"status": "ok"})

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/tasks":
            body = json.loads(self._read_body().decode() or "{}")
            body["queued_at"] = datetime.now().isoformat()
            TASKS.append(body)
            save_json(TASKS_FILE, TASKS)
            print(f"[QUEUED] {body.get('id', 'no-id')}: {body.get('content','')[:80]}", flush=True)
            tasks_event.set()  # Wake up laptop long-poll
            self._respond(200, {"status": "queued", "pending": len(TASKS)})
        else:
            self._respond(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass


class ThreadedHTTPServer(HTTPServer):
    """Handle each request in a new thread for long-polling support."""
    def process_request(self, request, client_address):
        t = threading.Thread(target=self.process_request_thread, args=(request, client_address))
        t.daemon = True
        t.start()

    def process_request_thread(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9200))
    server = ThreadedHTTPServer(("0.0.0.0", port), Handler)
    print(f"[kiro-relay] Listening on 0.0.0.0:{port} (threaded, long-poll enabled)", flush=True)
    print(f"[kiro-relay] Data dir: {DATA_DIR}", flush=True)
    server.serve_forever()
