#!/usr/bin/env bash
# kiro-relay: Wake Arch laptop, SSH in, start kiro-cli worker in tmux
set -e

LAPTOP_MAC="34:41:5d:5c:33:e3"
LAPTOP_IP="192.168.1.66"
LAPTOP_USER="rockhight"
RELAY_URL="http://192.168.1.76:9200"
TMUX_SESSION="kiro-worker"

WORKER_PROMPT='You are a remote worker agent. Poll for tasks continuously.

PROTOCOL:
- Poll: curl -s '"$RELAY_URL"'/tasks (every 5 seconds)
- Return results: curl -X POST '"$RELAY_URL"' -H "Content-Type: application/json" -d "{\"type\":\"result\",\"content\":\"<output>\"}"
- Heartbeat: curl -X POST '"$RELAY_URL"'/heartbeat (every 30s)
- Upload files: curl -X POST '"$RELAY_URL"'/files/<filename> --data-binary @<filepath>
- Download files: curl -s '"$RELAY_URL"'/files/<filename> -o <filepath>

BEHAVIOR:
- Poll every 5 seconds. Never stop.
- Execute tasks fully and autonomously. POST results back.
- Send heartbeat every 30 seconds.
- Never ask for clarification. Do your best and report.
- You have full access to this machine.

START NOW.'

echo "[1/4] Sending Wake-on-LAN to $LAPTOP_MAC..."
wakeonlan "$LAPTOP_MAC" 2>/dev/null || python3 -c "
import socket, struct
mac = '$LAPTOP_MAC'.replace(':','')
data = b'\xff'*6 + bytes.fromhex(mac)*16
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
s.sendto(data, ('255.255.255.255', 9))
print('WoL packet sent')
"

echo "[2/4] Waiting for laptop to come online..."
for i in $(seq 1 60); do
    if ssh -o ConnectTimeout=2 -o BatchMode=yes "$LAPTOP_USER@$LAPTOP_IP" "echo ok" &>/dev/null; then
        echo "  Laptop is up!"
        break
    fi
    sleep 2
    echo -n "."
done

echo "[3/4] Starting kiro-cli worker in tmux session '$TMUX_SESSION'..."
ssh "$LAPTOP_USER@$LAPTOP_IP" "
    tmux has-session -t $TMUX_SESSION 2>/dev/null && tmux kill-session -t $TMUX_SESSION
    tmux new-session -d -s $TMUX_SESSION \"kiro-cli chat --agent kiro-developer \\\"$WORKER_PROMPT\\\"\"
"

echo "[4/4] Done. Worker is running in tmux session '$TMUX_SESSION' on $LAPTOP_IP"
echo "  To view: ssh $LAPTOP_USER@$LAPTOP_IP -t 'tmux attach -t $TMUX_SESSION'"
