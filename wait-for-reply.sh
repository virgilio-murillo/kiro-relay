#!/usr/bin/env bash
# Wait for a new message from the laptop using long-polling.
# Usage: ./wait-for-reply [timeout_seconds]
TIMEOUT="${1:-60}"
RELAY="http://localhost:9200"

RESULT=$(curl -s "$RELAY/inbox/wait?timeout=$TIMEOUT")
NEW=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('new', False))")

if [ "$NEW" = "True" ]; then
    echo "$RESULT" | python3 -m json.tool
else
    echo "(no new messages within ${TIMEOUT}s)"
fi
