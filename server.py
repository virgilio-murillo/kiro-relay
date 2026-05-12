#!/usr/bin/env python3
"""kiro-relay v3: Instant M2M communication via long-polling."""
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
HISTORY_FILE = DATA_DIR / "task_history.json"

DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)

def load_json(path, default):
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except (json.JSONDecodeError, OSError):
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

INBOX = load_json(INBOX_FILE, [])
TASKS = load_json(TASKS_FILE, [])
TASK_HISTORY = load_json(HISTORY_FILE, [])
HEARTBEAT = {"last": None}

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
            # Non-destructive peek. Never blocks, never steals.
            self._respond(200, {"tasks": []})

        elif path == "/status":
            self._respond(200, {
                "status": "alive",
                "inbox_count": len(INBOX),
                "pending_tasks": len(TASKS),
                "heartbeat": HEARTBEAT["last"],
                "history_count": len(TASK_HISTORY),
            })

        elif path == "/inbox":
            last_n = int(params.get("last", [10])[0])
            self._respond(200, {"messages": INBOX[-last_n:]})

        elif path == "/inbox/wait":
            # Long-poll: blocks until new message arrives or timeout
            timeout = float(params.get("timeout", [60])[0])
            count_before = len(INBOX)
            inbox_event.clear()
            inbox_event.wait(timeout=timeout)
            new_msgs = INBOX[count_before:]
            self._respond(200, {"new": len(new_msgs) > 0, "messages": new_msgs})

        elif path == "/history":
            last_n = int(params.get("last", [10])[0])
            self._respond(200, {"tasks": TASK_HISTORY[-last_n:]})

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
            self._respond(200, {"relay": "kiro-relay v3", "info": "M2M instant relay"})

    def do_POST(self):
        path = urlparse(self.path).path
        params = parse_qs(urlparse(self.path).query)

        if path == "/claim":
            # Worker long-poll: blocks until task available, then returns it
            timeout = float(params.get("timeout", [60])[0])
            if not TASKS and timeout > 0:
                tasks_event.clear()
                tasks_event.wait(timeout=timeout)
            if TASKS:
                task = TASKS.pop(0)
                save_json(TASKS_FILE, TASKS)
                task["delivered_at"] = datetime.now().isoformat()
                TASK_HISTORY.append(task)
                save_json(HISTORY_FILE, TASK_HISTORY[-200:])
                print(f"[CLAIMED] {task.get('id','?')}: {task.get('content','')[:80]}", flush=True)
                self._respond(200, {"task": task})
            else:
                self._respond(200, {"task": None})

        elif path == "/heartbeat":
            HEARTBEAT["last"] = datetime.now().isoformat()
            self._respond(200, {"status": "ok"})

        elif path == "/result":
            # Worker posts result — accepts multipart-like: task_id + content
            body = json.loads(self._read_body().decode() or "{}")
            body["received_at"] = datetime.now().isoformat()
            INBOX.append(body)
            save_json(INBOX_FILE, INBOX[-500:])
            print(f"[RESULT] {body.get('task_id','?')}: {body.get('content','')[:100]}", flush=True)
            inbox_event.set()
            self._respond(200, {"status": "ok"})

        elif path.startswith("/files/"):
            filename = path[7:]
            data = self._read_body()
            filepath = FILES_DIR / filename
            filepath.write_bytes(data)
            md5 = hashlib.md5(data).hexdigest()
            print(f"[FILE] {filename} ({len(data)}B)", flush=True)
            self._respond(200, {"stored": filename, "size": len(data), "md5": md5})

        else:
            # Generic message to inbox
            body = json.loads(self._read_body().decode() or "{}")
            body["received_at"] = datetime.now().isoformat()
            INBOX.append(body)
            save_json(INBOX_FILE, INBOX[-500:])
            print(f"[IN] {body.get('type','?')}: {body.get('content','')[:100]}", flush=True)
            inbox_event.set()
            self._respond(200, {"status": "ok"})

    def do_PUT(self):
        path = urlparse(self.path).path
        if path == "/tasks":
            body = json.loads(self._read_body().decode() or "{}")
            task_id = body.get("id", f"task-{len(TASK_HISTORY)+len(TASKS)+1}")
            body["id"] = task_id
            body["queued_at"] = datetime.now().isoformat()
            TASKS.append(body)
            save_json(TASKS_FILE, TASKS)
            print(f"[QUEUED] {task_id}: {body.get('content','')[:80]}", flush=True)
            tasks_event.set()
            self._respond(200, {"status": "queued", "id": task_id, "pending": len(TASKS)})
        else:
            self._respond(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass


class ThreadedHTTPServer(HTTPServer):
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
    print(f"[kiro-relay v3] http://0.0.0.0:{port}", flush=True)
    print(f"[kiro-relay v3] POST /claim?timeout=60 — worker long-poll (instant delivery)", flush=True)
    print(f"[kiro-relay v3] GET /inbox/wait?timeout=60 — controller long-poll (instant results)", flush=True)
    server.serve_forever()
