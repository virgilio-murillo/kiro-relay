# Arch Laptop Setup TODO

## 1. Rebuild MCP Server venvs (makes most agents work)

```bash
cd ~/.kiro/mcp-servers/mcp-proxy && python3 -m venv .venv && .venv/bin/pip install -e .
cd ~/.kiro/mcp-servers/kiro-investigation && python3 -m venv .venv && .venv/bin/pip install -e .
cd ~/.kiro/mcp-servers/kiro-agents && python3 -m venv .venv && .venv/bin/pip install -e .
cd ~/.kiro/mcp-servers/kiro-checkpoint && python3 -m venv .venv && .venv/bin/pip install -e .
cd ~/.kiro/mcp-servers/bible-tools && python3 -m venv .venv && .venv/bin/pip install -e .
```

## 2. Install daily S3 sync

```bash
# The script is already at ~/.local/bin/kiro-sync-from-s3
# Enable the timer:
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/kiro-sync.service << 'EOF'
[Unit]
Description=Sync kiro projects from S3
After=network-online.target
[Service]
Type=oneshot
ExecStart=/home/rockhight/.local/bin/kiro-sync-from-s3
EOF

cat > ~/.config/systemd/user/kiro-sync.timer << 'EOF'
[Unit]
Description=Daily kiro S3 sync
[Timer]
OnBootSec=2min
OnCalendar=daily
Persistent=true
[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable kiro-sync.timer
systemctl --user start kiro-sync.timer
```

## 3. Fix agent paths in mcp.json

The `mcp.json` settings file has Mac paths (`/Users/murivirg/...`). Update them:
```bash
sed -i 's|/Users/murivirg|/home/rockhight|g' ~/.kiro/settings/mcp.json
```

## 4. Note: chrome-tabs MCP won't work

It uses macOS AppleScript — skip it on Arch. Agents that need it: `bible-expert`, `generic-agent`.

## 5. Connect to Mac

```bash
sync-computers
# Select "Worker" → pick the Mac → interactive kiro-cli starts
```

## 6. Pending S3 uploads (run from Mac)

These timed out during initial sync — run from Mac when convenient:
```bash
aws s3 sync ~/.kiro/mcp-servers/bible-tools/ s3://kiro-backup-murivirg/kiro/mcp-servers/bible-tools/ --exclude ".venv/*" --exclude ".git/*"
aws s3 sync ~/work/github/mcp-knowledge-base/ s3://kiro-backup-murivirg/work/github/mcp-knowledge-base/ --exclude ".git/*"
aws s3 sync ~/work/anki/ s3://kiro-backup-murivirg/work/anki/ --exclude ".git/objects/*"
```
