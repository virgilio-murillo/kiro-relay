#!/usr/bin/env bash
# kiro-motd — Shows useful commands on terminal startup
# Source this from your shell rc file

_kiro_motd() {
    local CYAN='\033[36m'
    local GREEN='\033[32m'
    local YELLOW='\033[33m'
    local DIM='\033[2m'
    local BOLD='\033[1m'
    local RESET='\033[0m'

    echo ""
    echo -e "${BOLD}${CYAN}── Quick Commands ──${RESET}"
    echo -e "  ${GREEN}sync-computers${RESET}        Connect to another machine (TUI)"
    echo -e "  ${GREEN}nsync-gui${RESET}             Password manager (TUI)"
    echo -e "  ${GREEN}kiro-cli chat${RESET}         Start AI assistant"
    echo -e "  ${GREEN}kiro-cli chat -a${RESET}      AI with all tools trusted"
    echo ""
    echo -e "${DIM}── Relay (if sync-computers is running) ──${RESET}"
    echo -e "  ${YELLOW}curl -s http://192.168.1.76:9200/status${RESET}   Check relay"
    echo -e "  ${YELLOW}curl -s http://192.168.1.76:9200/inbox?last=3${RESET}  Recent results"
    echo ""
}

_kiro_motd
