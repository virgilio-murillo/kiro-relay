# kiro-relay

Bidirectional relay server for coordinating kiro-cli agents across machines on a local network.

## Architecture

```
Mac (controller)                    Arch Laptop (worker)
┌─────────────┐                    ┌─────────────────┐
│ kiro-cli    │──PUT /tasks──────▶│                 │
│             │◀──POST /──────────│ kiro-cli worker │
│ relay server│◀──GET /tasks──────│ (polls every 5s)│
│ :9200       │──GET /files/──────▶│                 │
└─────────────┘                    └─────────────────┘
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Server info and endpoint list |
| GET | `/status` | Health check with stats |
| GET | `/tasks` | Poll pending tasks (clears queue) |
| GET | `/inbox?last=N` | Read last N received messages |
| GET | `/files` | List uploaded files |
| GET | `/files/<name>` | Download a file |
| PUT | `/tasks` | Enqueue a task for the worker |
| POST | `/` | Worker posts results back |
| POST | `/heartbeat` | Worker heartbeat |
| POST | `/files/<name>` | Upload a file |

## Usage

### Start the relay server (Mac)
```bash
python3 server.py  # listens on :9200
```

### Wake laptop and start worker
```bash
./wake-and-connect.sh
```

### Send a task
```bash
curl -X PUT http://localhost:9200/tasks \
  -H "Content-Type: application/json" \
  -d '{"content": "ls -la ~ && uname -a"}'
```

### Check results
```bash
curl -s http://localhost:9200/inbox?last=1 | python3 -m json.tool
```

## Setup

### Prerequisites
- SSH key auth from Mac to laptop
- Wake-on-LAN enabled in laptop BIOS
- `tmux` installed on laptop
- `kiro-cli` in PATH on laptop

### SSH Key Setup
```bash
ssh-copy-id rockhight@192.168.1.66
```
