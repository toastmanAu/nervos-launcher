#!/usr/bin/env bash
# verify.sh — Remote CKB Light Client verification & report generator
# Connects to a deployed light client via SSH, runs health checks,
# and saves a markdown report LOCALLY (not on the remote device).
#
# Usage:
#   ./verify.sh --host 192.168.68.110 --user root
#   ./verify.sh                                      # interactive
#
# Reports saved to: tested/<hostname>_<date>.md

set -euo pipefail

BOLD="\033[1m"; RESET="\033[0m"; GREEN="\033[32m"; YELLOW="\033[33m"
RED="\033[31m"; CYAN="\033[36m"
step()  { echo -e "\n${BOLD}${CYAN}▶ $*${RESET}"; }
ok()    { echo -e "  ${GREEN}✓${RESET} $*"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
err()   { echo -e "  ${RED}✗${RESET} $*"; }
info()  { echo -e "  ${CYAN}ℹ${RESET} $*"; }
die()   { err "$*"; exit 1; }

# ── Parse args ──────────────────────────────────────────────
CLI_HOST="" CLI_USER="" CLI_PORT="" CLI_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) CLI_HOST="$2"; shift 2 ;;
    --user) CLI_USER="$2"; shift 2 ;;
    --port) CLI_PORT="$2"; shift 2 ;;
    --dir)  CLI_DIR="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ── Banner ──────────────────────────────────────────────────
echo -e "${BOLD}"
echo "  ╔════════════════════════════════════════════════╗"
echo "  ║   CKB Light Client — Verification Report      ║"
echo "  ╚════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Interactive prompts ─────────────────────────────────────
if [[ -z "$CLI_HOST" ]]; then
  read -rp "  Target IP or hostname: " CLI_HOST
fi
[[ -z "$CLI_HOST" ]] && die "Host is required"
TARGET_HOST="$CLI_HOST"

if [[ -z "$CLI_USER" ]]; then
  read -rp "  SSH username [root]: " CLI_USER
fi
TARGET_USER="${CLI_USER:-root}"
SSH_PORT="${CLI_PORT:-22}"

# Default install locations to check
INSTALL_DIRS=("${CLI_DIR:-}" "/userdata/ckb-light-client" "\$HOME/ckb-light-client" "\$HOME/.ckb-light-testnet" "\$HOME/.ckb-light-mainnet")

# ── SSH setup ───────────────────────────────────────────────
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -p $SSH_PORT"
SSH_CMD="ssh $SSH_OPTS ${TARGET_USER}@${TARGET_HOST}"

HAS_SSHPASS=0
command -v sshpass &>/dev/null && HAS_SSHPASS=1
USE_SSHPASS=0

step "Connecting to ${TARGET_USER}@${TARGET_HOST}"
if [[ -n "${SSHPASS:-}" && "$HAS_SSHPASS" = "1" ]]; then
  # SSHPASS env var already set (non-interactive / scripted usage)
  SSH_CMD="sshpass -e ssh $SSH_OPTS ${TARGET_USER}@${TARGET_HOST}"
  $SSH_CMD "echo ok" &>/dev/null || die "SSH auth failed (SSHPASS env)"
  ok "Password auth (SSHPASS env)"
elif $SSH_CMD "echo ok" &>/dev/null; then
  ok "SSH key auth"
elif [[ "$HAS_SSHPASS" = "1" ]]; then
  read -s -rp "  SSH password: " SSH_PASS; echo ""
  export SSHPASS="$SSH_PASS"
  SSH_CMD="sshpass -e ssh $SSH_OPTS ${TARGET_USER}@${TARGET_HOST}"
  $SSH_CMD "echo ok" &>/dev/null || die "SSH auth failed"
  ok "Password auth"
else
  die "SSH key auth failed and sshpass not installed"
fi

# ── Find install directory ──────────────────────────────────
step "Locating light client"
INSTALL_DIR=""
for dir in "${INSTALL_DIRS[@]}"; do
  [[ -z "$dir" ]] && continue
  if $SSH_CMD "test -x ${dir}/bin/ckb-light-client" &>/dev/null; then
    INSTALL_DIR="$dir"
    break
  fi
done

if [[ -z "$INSTALL_DIR" ]]; then
  # Try finding it
  INSTALL_DIR=$($SSH_CMD "dirname \$(dirname \$(which ckb-light-client 2>/dev/null || find / -name ckb-light-client -type f 2>/dev/null | head -1))" 2>/dev/null || true)
fi

[[ -z "$INSTALL_DIR" ]] && die "Could not find ckb-light-client on target"
ok "Found: $INSTALL_DIR"

# ── Collect data ────────────────────────────────────────────
step "Collecting system info"

TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
DATE_SHORT=$(date '+%Y-%m-%d')
HOSTNAME=$($SSH_CMD "hostname" 2>/dev/null || echo "$TARGET_HOST")
ARCH=$($SSH_CMD "uname -m" 2>/dev/null || echo "unknown")
KERNEL=$($SSH_CMD "uname -r" 2>/dev/null || echo "unknown")
OS_NAME=$($SSH_CMD "cat /etc/os-release 2>/dev/null | grep '^PRETTY_NAME' | cut -d= -f2 | tr -d '\"'" 2>/dev/null || echo "unknown")
TOTAL_RAM=$($SSH_CMD "awk '/MemTotal/{printf \"%.0f\", \$2/1024}' /proc/meminfo" 2>/dev/null || echo "?")
FREE_RAM=$($SSH_CMD "awk '/MemAvailable/{printf \"%.0f\", \$2/1024}' /proc/meminfo" 2>/dev/null || echo "?")
DISK_TOTAL=$($SSH_CMD "df -BM --output=size / 2>/dev/null | tail -1 | tr -d ' M'" 2>/dev/null || echo "?")
DISK_AVAIL=$($SSH_CMD "df -BM --output=avail / 2>/dev/null | tail -1 | tr -d ' M'" 2>/dev/null || echo "?")

ok "Host:    $HOSTNAME ($ARCH)"
ok "OS:      $OS_NAME"
ok "Kernel:  $KERNEL"
ok "RAM:     ${FREE_RAM}MB free / ${TOTAL_RAM}MB total"
ok "Disk:    ${DISK_AVAIL}MB free / ${DISK_TOTAL}MB total"

# ── Binary info ─────────────────────────────────────────────
step "Binary check"

VERSION=$($SSH_CMD "${INSTALL_DIR}/bin/ckb-light-client --version 2>&1 | head -1" 2>/dev/null || echo "unknown")
BINARY_SIZE=$($SSH_CMD "du -m ${INSTALL_DIR}/bin/ckb-light-client 2>/dev/null | cut -f1" 2>/dev/null || echo "?")
ok "Version: $VERSION"
ok "Size:    ${BINARY_SIZE}MB"

# ── Process check ───────────────────────────────────────────
step "Process check"

PID=$($SSH_CMD "cat ${INSTALL_DIR}/data/ckb-light.pid 2>/dev/null" 2>/dev/null || echo "")
RUNNING="no"
PROC_RSS="—"
PROC_CPU="—"
if [[ -n "$PID" ]] && $SSH_CMD "kill -0 $PID" &>/dev/null; then
  RUNNING="yes (PID $PID)"
  PROC_RSS=$($SSH_CMD "ps -o rss= -p $PID 2>/dev/null | awk '{printf \"%.1f\", \$1/1024}'" 2>/dev/null || echo "?")
  PROC_CPU=$($SSH_CMD "ps -o %cpu= -p $PID" 2>/dev/null | tr -d ' ' || echo "?")
  ok "Running: PID $PID — ${PROC_RSS}MB RSS, ${PROC_CPU}% CPU"
else
  warn "Not running"
fi

# ── Config check ────────────────────────────────────────────
step "Config check"

NETWORK=$($SSH_CMD "grep '^chain' ${INSTALL_DIR}/config.toml 2>/dev/null | head -1 | sed 's/.*= *\"//' | sed 's/\"//' " 2>/dev/null || echo "unknown")
RPC_ADDR=$($SSH_CMD "grep 'listen_address' ${INSTALL_DIR}/config.toml 2>/dev/null | tail -1 | sed 's/.*= *\"//' | sed 's/\"//' " 2>/dev/null || echo "unknown")
ok "Network: $NETWORK"
ok "RPC:     $RPC_ADDR"

# ── RPC tests ───────────────────────────────────────────────
step "RPC tests"

RPC_HOST="127.0.0.1"
RPC_PORT_NUM=$(echo "$RPC_ADDR" | grep -oE '[0-9]+$' || echo "9000")

rpc_call() {
  $SSH_CMD "curl -sf -m 5 -X POST http://${RPC_HOST}:${RPC_PORT_NUM}/ \
    -H 'Content-Type: application/json' \
    -d '{\"jsonrpc\":\"2.0\",\"method\":\"$1\",\"params\":[$2],\"id\":1}'" 2>/dev/null || echo '{"error":"timeout"}'
}

# Test 1: local_node_info
NODE_INFO=$(rpc_call "local_node_info" "")
NODE_ID=$(echo "$NODE_INFO" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("result",{}).get("node_id",""))' 2>/dev/null || echo "")
NODE_VER=$(echo "$NODE_INFO" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("result",{}).get("version",""))' 2>/dev/null || echo "")
RPC_NODE_INFO="FAIL"
if [[ -n "$NODE_ID" ]]; then
  RPC_NODE_INFO="PASS"
  ok "local_node_info: $NODE_VER (${NODE_ID:0:12}...)"
else
  err "local_node_info: no response"
fi

# Test 2: get_tip_header
TIP_INFO=$(rpc_call "get_tip_header" "")
TIP_NUMBER=$(echo "$TIP_INFO" | python3 -c 'import sys,json; r=json.load(sys.stdin).get("result",{}); print(int(r.get("inner",{}).get("number","0x0"),16))' 2>/dev/null || echo "0")
TIP_HASH=$(echo "$TIP_INFO" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("result",{}).get("inner",{}).get("hash","")[:16])' 2>/dev/null || echo "")
RPC_TIP="FAIL"
if [[ "$TIP_NUMBER" != "0" ]]; then
  RPC_TIP="PASS"
  ok "get_tip_header: block $TIP_NUMBER (${TIP_HASH}...)"
else
  warn "get_tip_header: block 0 (still initializing)"
  RPC_TIP="INIT"
fi

# Test 3: get_peers
PEERS_INFO=$(rpc_call "get_peers" "")
PEER_COUNT=$(echo "$PEERS_INFO" | python3 -c 'import sys,json; print(len(json.load(sys.stdin).get("result",[])))' 2>/dev/null || echo "0")
RPC_PEERS="FAIL"
if [[ "$PEER_COUNT" -gt 0 ]]; then
  RPC_PEERS="PASS"
  ok "get_peers: $PEER_COUNT connected"
else
  warn "get_peers: 0 connected"
fi

# ── Data directory size ─────────────────────────────────────
DATA_SIZE=$($SSH_CMD "du -sm ${INSTALL_DIR}/data/ 2>/dev/null | cut -f1" 2>/dev/null || echo "?")
LOG_SIZE=$($SSH_CMD "du -sm ${INSTALL_DIR}/data/ckb-light.log 2>/dev/null | cut -f1" 2>/dev/null || echo "0")

# ── Generate report ─────────────────────────────────────────
step "Generating report"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TESTED_DIR="${SCRIPT_DIR}/tested"
mkdir -p "$TESTED_DIR"

SAFE_HOST=$(echo "$HOSTNAME" | tr -cs 'a-zA-Z0-9_-' '_')
REPORT_FILE="${TESTED_DIR}/${SAFE_HOST}_${DATE_SHORT}.md"

# Overall status
OVERALL="PASS"
[[ "$RUNNING" == "no" ]] && OVERALL="FAIL"
[[ "$RPC_NODE_INFO" == "FAIL" ]] && OVERALL="FAIL"
[[ "$PEER_COUNT" == "0" ]] && OVERALL="WARN"

cat > "$REPORT_FILE" << REPORT
# CKB Light Client — Verification Report

**Status:** ${OVERALL}
**Date:** ${TIMESTAMP}
**Tester:** $(whoami)@$(hostname)

## Target Device

| Field | Value |
|-------|-------|
| Hostname | ${HOSTNAME} |
| IP | ${TARGET_HOST} |
| Architecture | ${ARCH} |
| OS | ${OS_NAME} |
| Kernel | ${KERNEL} |
| Total RAM | ${TOTAL_RAM}MB |
| Available RAM | ${FREE_RAM}MB |
| Disk Total | ${DISK_TOTAL}MB |
| Disk Available | ${DISK_AVAIL}MB |

## Light Client

| Field | Value |
|-------|-------|
| Version | ${VERSION} |
| Node Version | ${NODE_VER} |
| Binary Size | ${BINARY_SIZE}MB |
| Install Dir | ${INSTALL_DIR} |
| Network | ${NETWORK} |
| RPC Address | ${RPC_ADDR} |

## Process

| Field | Value |
|-------|-------|
| Running | ${RUNNING} |
| RSS Memory | ${PROC_RSS}MB |
| CPU Usage | ${PROC_CPU}% |
| Data Dir Size | ${DATA_SIZE}MB |
| Log Size | ${LOG_SIZE}MB |

## RPC Tests

| Test | Result | Detail |
|------|--------|--------|
| local_node_info | ${RPC_NODE_INFO} | Node ID: ${NODE_ID:-—} |
| get_tip_header | ${RPC_TIP} | Block: ${TIP_NUMBER} |
| get_peers | ${RPC_PEERS} | ${PEER_COUNT} peers |

## Node Identity

\`\`\`
Node ID: ${NODE_ID:-—}
\`\`\`
REPORT

ok "Report saved: $REPORT_FILE"

# ── Print summary ───────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════${RESET}"
if [[ "$OVERALL" == "PASS" ]]; then
  echo -e "${BOLD}${GREEN}  ✓ VERIFICATION PASSED${RESET}"
elif [[ "$OVERALL" == "WARN" ]]; then
  echo -e "${BOLD}${YELLOW}  ⚠ VERIFICATION PASSED (with warnings)${RESET}"
else
  echo -e "${BOLD}${RED}  ✗ VERIFICATION FAILED${RESET}"
fi
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Device:${RESET}  ${HOSTNAME} (${ARCH})"
echo -e "  ${BOLD}Version:${RESET} ${NODE_VER:-${VERSION}}"
echo -e "  ${BOLD}Network:${RESET} ${NETWORK}"
echo -e "  ${BOLD}Block:${RESET}   ${TIP_NUMBER}"
echo -e "  ${BOLD}Peers:${RESET}   ${PEER_COUNT}"
echo -e "  ${BOLD}RAM:${RESET}     ${PROC_RSS}MB RSS"
echo -e "  ${BOLD}Report:${RESET}  ${REPORT_FILE}"
echo ""
