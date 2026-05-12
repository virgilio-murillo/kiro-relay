#!/bin/bash
# kiro-sync-from-s3 — Pull latest from S3 backup
# Install: copy to ~/.local/bin/kiro-sync-from-s3
export PATH="/home/rockhight/.local/bin:$PATH"
BUCKET="s3://kiro-backup-murivirg"
echo "[kiro-sync] $(date) — Starting S3 pull..."
aws s3 sync $BUCKET/kiro/agents/ ~/.kiro/agents/ --quiet
aws s3 sync $BUCKET/kiro/steering/ ~/.kiro/steering/ --quiet
aws s3 sync $BUCKET/kiro/settings/ ~/.kiro/settings/ --quiet
for server in agent-metrics bible-tools chrome-tabs kiro-agents kiro-checkpoint kiro-investigation mcp-proxy; do
    aws s3 sync $BUCKET/kiro/mcp-servers/$server/ ~/.kiro/mcp-servers/$server/ --quiet
done
for proj in alarm-despertador bible-expert bible bookmark-merge correspondences findings scripts truth-seeking-debate; do
    aws s3 sync $BUCKET/work/$proj/ ~/work/$proj/ --quiet
done
for repo in dotfiles mcp-knowledge-base kiro-config kiro-pulse aws-samples kiro-mcp-servers; do
    aws s3 sync $BUCKET/work/github/$repo/ ~/work/github/$repo/ --quiet
done
echo "[kiro-sync] $(date) — Done."
