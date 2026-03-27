#!/usr/bin/env bash
# deploy.sh — Remote SSH deployer for Nervos CKB Light Client
# Deploys ckb-light-client to any Linux machine over SSH (arm64 + amd64).
# Supports prebuilt binaries, build-from-source, and Knulli/handheld targets.
#
# Usage:
#   ./deploy.sh                       # interactive prompts
#   ./deploy.sh --host 192.168.1.50   # skip host prompt
#
# Part of ckb-access: https://github.com/toastmanAu/ckb-access

set -euo pipefail

VERSION="0.5.5-rc1"
REPO="nervosnetwork/ckb-light-client"
CONFIG_BASE="https://raw.githubusercontent.com/nervosnetwork/ckb-light-client/develop/config"
BINARY_NAME="ckb-light-client"

# ── Colours ─────────────────────────────────────────────────
BOLD="\033[1m"; RESET="\033[0m"; GREEN="\033[32m"; YELLOW="\033[33m"
RED="\033[31m"; CYAN="\033[36m"
step()  { echo -e "\n${BOLD}${CYAN}▶ $*${RESET}"; }
ok()    { echo -e "  ${GREEN}✓${RESET} $*"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET}  $*"; }
err()   { echo -e "  ${RED}✗${RESET} $*"; }
info()  { echo -e "  ${CYAN}ℹ${RESET} $*"; }

die() { err "$*"; exit 1; }

# ── Prerequisite check ──────────────────────────────────────
for cmd in ssh scp curl; do
  command -v "$cmd" &>/dev/null || die "$cmd is required but not found"
done

# Prefer ssh key auth; fall back to sshpass if needed
USE_SSHPASS=0
HAS_SSHPASS=0
command -v sshpass &>/dev/null && HAS_SSHPASS=1

# ── Banner ──────────────────────────────────────────────────
echo -e "${BOLD}"
echo "  ╔════════════════════════════════════════════════╗"
echo "  ║   CKB Light Client — Remote SSH Deployer      ║"
echo "  ║   arm64 + amd64 · Knulli/handheld support     ║"
echo "  ╚════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Parse CLI args ──────────────────────────────────────────
CLI_HOST="" CLI_USER="" CLI_PORT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) CLI_HOST="$2"; shift 2 ;;
    --user) CLI_USER="$2"; shift 2 ;;
    --port) CLI_PORT="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ── Interactive prompts ─────────────────────────────────────
step "Target Device"

if [[ -n "$CLI_HOST" ]]; then
  TARGET_HOST="$CLI_HOST"
  echo "  Host: $TARGET_HOST"
else
  read -rp "  Target IP or hostname: " TARGET_HOST
fi
[[ -z "$TARGET_HOST" ]] && die "Host is required"

if [[ -n "$CLI_USER" ]]; then
  TARGET_USER="$CLI_USER"
else
  read -rp "  SSH username [root]: " TARGET_USER
  TARGET_USER="${TARGET_USER:-root}"
fi

SSH_PORT="${CLI_PORT:-22}"
if [[ -z "$CLI_PORT" ]]; then
  read -rp "  SSH port [22]: " SSH_PORT
  SSH_PORT="${SSH_PORT:-22}"
fi

# Auth method
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -p $SSH_PORT"
SSH_CMD="ssh $SSH_OPTS ${TARGET_USER}@${TARGET_HOST}"
SCP_CMD="scp -P $SSH_PORT -o StrictHostKeyChecking=accept-new"

echo ""
info "Testing SSH auth..."
if [[ -n "${SSHPASS:-}" && "$HAS_SSHPASS" = "1" ]]; then
  # SSHPASS env var set — non-interactive password auth
  USE_SSHPASS=1
  SSH_CMD="sshpass -e ssh $SSH_OPTS ${TARGET_USER}@${TARGET_HOST}"
  SCP_CMD="sshpass -e scp -P $SSH_PORT -o StrictHostKeyChecking=accept-new"
  $SSH_CMD "echo ok" &>/dev/null || die "SSH auth failed (SSHPASS env)"
  ok "Password auth (SSHPASS env)"
elif $SSH_CMD "echo ok" &>/dev/null; then
  ok "SSH key auth works"
elif [[ "$HAS_SSHPASS" = "1" ]]; then
  read -s -rp "  SSH password (key auth failed): " SSH_PASS
  echo ""
  USE_SSHPASS=1
  export SSHPASS="$SSH_PASS"
  SSH_CMD="sshpass -e ssh $SSH_OPTS ${TARGET_USER}@${TARGET_HOST}"
  SCP_CMD="sshpass -e scp -P $SSH_PORT -o StrictHostKeyChecking=accept-new"
  $SSH_CMD "echo ok" &>/dev/null || die "SSH auth failed — check credentials"
  ok "Password auth works"
else
  die "SSH key auth failed and sshpass not installed. Install sshpass or set up SSH keys."
fi

# ── Remote: detect arch ─────────────────────────────────────
step "Detecting Target"

REMOTE_ARCH=$($SSH_CMD "uname -m" 2>/dev/null)
REMOTE_OS=$($SSH_CMD "uname -s" 2>/dev/null)
REMOTE_MEM=$($SSH_CMD "awk '/MemTotal/{printf \"%.0f\", \$2/1024}' /proc/meminfo 2>/dev/null || echo unknown")
REMOTE_DISK=$($SSH_CMD "df -BM --output=avail / 2>/dev/null | tail -1 | tr -d ' M' || echo unknown")

case "$REMOTE_ARCH" in
  aarch64|arm64) TARGET_ARCH="arm64" ;;
  x86_64)        TARGET_ARCH="amd64" ;;
  *)             die "Unsupported architecture: $REMOTE_ARCH" ;;
esac

ok "Arch:   $TARGET_ARCH ($REMOTE_ARCH)"
ok "OS:     $REMOTE_OS"
ok "RAM:    ${REMOTE_MEM}MB"
ok "Disk:   ${REMOTE_DISK}MB free"

# Check if it's a Knulli/handheld
IS_KNULLI="n"
if $SSH_CMD "test -d /userdata/roms" &>/dev/null; then
  IS_KNULLI="y"
  info "Detected Knulli/EmulationStation device"
fi
read -rp "  Is this a Knulli/handheld? [${IS_KNULLI}]: " KNULLI_INPUT
IS_KNULLI="${KNULLI_INPUT:-$IS_KNULLI}"

# ── Install location ────────────────────────────────────────
step "Configuration"

if [[ "$IS_KNULLI" == "y" ]]; then
  DEFAULT_DIR="/userdata/ckb-light-client"
else
  REMOTE_HOME=$($SSH_CMD "echo \$HOME")
  DEFAULT_DIR="${REMOTE_HOME}/ckb-light-client"
fi

read -rp "  Install directory [$DEFAULT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

read -rp "  Network (mainnet/testnet) [testnet]: " NETWORK
NETWORK="${NETWORK:-testnet}"

read -rp "  RPC port [9000]: " RPC_PORT
RPC_PORT="${RPC_PORT:-9000}"

read -rp "  P2P port [8118]: " P2P_PORT
P2P_PORT="${P2P_PORT:-8118}"

echo ""
ok "Install dir: $INSTALL_DIR"
ok "Network:     $NETWORK"
ok "RPC port:    $RPC_PORT"
ok "P2P port:    $P2P_PORT"

# ── Binary acquisition ──────────────────────────────────────
step "Getting ckb-light-client v${VERSION}"

$SSH_CMD "mkdir -p ${INSTALL_DIR}/bin ${INSTALL_DIR}/data/store ${INSTALL_DIR}/data/network"

# Check for prebuilt binary
PREBUILT_URL=""
case "$TARGET_ARCH" in
  amd64) PREBUILT_URL="https://github.com/${REPO}/releases/download/v${VERSION}/ckb-light-client_v${VERSION}-x86_64-linux.tar.gz" ;;
  arm64)
    ARM_URL="https://github.com/${REPO}/releases/download/v${VERSION}/ckb-light-client_v${VERSION}-aarch64-linux.tar.gz"
    if curl -fsI "$ARM_URL" &>/dev/null; then
      PREBUILT_URL="$ARM_URL"
    fi
    ;;
esac

BUILD_MODE=""
if [[ -n "$PREBUILT_URL" ]]; then
  info "Prebuilt binary available for $TARGET_ARCH"
  BUILD_MODE="download"
else
  warn "No prebuilt arm64 binary for v${VERSION}"
  echo ""
  echo "  Options:"
  echo "    1) Build from source on target (needs ~2GB RAM, 20-30 min on arm64)"
  echo "    2) Provide a pre-built binary from this machine"
  echo ""
  read -rp "  Choice [1]: " BUILD_CHOICE
  BUILD_CHOICE="${BUILD_CHOICE:-1}"
  case "$BUILD_CHOICE" in
    2) BUILD_MODE="scp" ;;
    *) BUILD_MODE="build" ;;
  esac
fi

case "$BUILD_MODE" in
  download)
    info "Downloading prebuilt binary on target..."
    $SSH_CMD "
      cd /tmp
      curl -fsSL -o ckb-light.tar.gz '${PREBUILT_URL}'
      tar -xzf ckb-light.tar.gz
      BIN=\$(find . -name 'ckb-light-client' -type f | head -1)
      cp \"\$BIN\" '${INSTALL_DIR}/bin/${BINARY_NAME}'
      chmod +x '${INSTALL_DIR}/bin/${BINARY_NAME}'
      rm -f ckb-light.tar.gz
    "
    ok "Binary installed from release"
    ;;

  scp)
    read -rp "  Path to ${BINARY_NAME} binary on this machine: " LOCAL_BIN
    [[ -f "$LOCAL_BIN" ]] || die "File not found: $LOCAL_BIN"
    info "Copying binary to target..."
    $SCP_CMD "$LOCAL_BIN" "${TARGET_USER}@${TARGET_HOST}:${INSTALL_DIR}/bin/${BINARY_NAME}"
    $SSH_CMD "chmod +x '${INSTALL_DIR}/bin/${BINARY_NAME}'"
    ok "Binary copied"
    ;;

  build)
    info "Building from source on target — this will take a while on arm64..."
    $SSH_CMD "
      # Install build deps
      if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq 2>/dev/null
        sudo apt-get install -y -qq build-essential pkg-config libssl-dev libclang-dev clang git curl 2>/dev/null
      elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y -q gcc gcc-c++ make pkgconfig openssl-devel clang git curl 2>/dev/null
      fi

      # Rust
      if ! command -v cargo >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --quiet --default-toolchain 1.92.0
        . \"\$HOME/.cargo/env\"
      fi

      # Clone + build
      TMP=\$(mktemp -d)
      git clone --depth=1 --branch 'v${VERSION}' 'https://github.com/${REPO}.git' \"\$TMP\" 2>&1 | tail -2
      cd \"\$TMP\"
      cargo build --release --bin ckb-light-client 2>&1 | grep -E 'Compiling|Finished|error' | tail -10
      cp target/release/ckb-light-client '${INSTALL_DIR}/bin/${BINARY_NAME}'
      chmod +x '${INSTALL_DIR}/bin/${BINARY_NAME}'
      cd /
      rm -rf \"\$TMP\"
      echo 'BUILD_OK'
    " 2>&1 | tail -15
    # Verify binary landed
    $SSH_CMD "test -x '${INSTALL_DIR}/bin/${BINARY_NAME}'" || die "Build failed — binary not found"
    ok "Built and installed from source"
    ;;
esac

# ── Config file ─────────────────────────────────────────────
step "Generating config"

# Fetch upstream config for correct bootnodes
UPSTREAM_CONFIG="$(curl -fsSL "${CONFIG_BASE}/${NETWORK}.toml" 2>/dev/null || true)"
BOOTNODES=""
if [[ -n "$UPSTREAM_CONFIG" ]]; then
  BOOTNODES="$(echo "$UPSTREAM_CONFIG" | awk '/^bootnodes/,/^\]/' | head -40)"
fi

$SSH_CMD "cat > '${INSTALL_DIR}/config.toml'" << TOML
chain = "${NETWORK}"

[store]
path = "data/store"

[network]
path = "data/network"
listen_addresses = ["/ip4/0.0.0.0/tcp/${P2P_PORT}"]
${BOOTNODES}

max_peers = 125
max_outbound_peers = 8
ping_interval_secs = 120
ping_timeout_secs = 1200
connect_outbound_interval_secs = 15
upnp = false
discovery_local_address = false
bootnode_mode = false

[rpc]
listen_address = "127.0.0.1:${RPC_PORT}"
TOML
ok "Config: ${INSTALL_DIR}/config.toml (${NETWORK})"

# ── Wrapper scripts ─────────────────────────────────────────
step "Generating scripts"

# start.sh
$SSH_CMD "cat > '${INSTALL_DIR}/start.sh' && chmod +x '${INSTALL_DIR}/start.sh'" << 'WRAPPER'
#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Starting CKB light client..."
RUST_LOG=info,ckb_light_client=info \
  nohup "$DIR/bin/ckb-light-client" run --config-file "$DIR/config.toml" \
  >> "$DIR/data/ckb-light.log" 2>&1 &
echo "PID: $!"
echo "$!" > "$DIR/data/ckb-light.pid"
echo "Log: $DIR/data/ckb-light.log"
WRAPPER
ok "start.sh (background with nohup)"

# stop.sh
$SSH_CMD "cat > '${INSTALL_DIR}/stop.sh' && chmod +x '${INSTALL_DIR}/stop.sh'" << 'WRAPPER'
#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/data/ckb-light.pid"
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Stopped (PID $PID)"
    rm -f "$PID_FILE"
  else
    echo "Not running (stale PID $PID)"
    rm -f "$PID_FILE"
  fi
else
  pkill -f ckb-light-client 2>/dev/null && echo "Stopped" || echo "Not running"
fi
WRAPPER
ok "stop.sh"

# status.sh
$SSH_CMD "cat > '${INSTALL_DIR}/status.sh' && chmod +x '${INSTALL_DIR}/status.sh'" << WRAPPER
#!/bin/sh
DIR="\$(cd "\$(dirname "\$0")" && pwd)"
PID_FILE="\$DIR/data/ckb-light.pid"

# Process check
if [ -f "\$PID_FILE" ] && kill -0 \$(cat "\$PID_FILE") 2>/dev/null; then
  echo "● Running (PID \$(cat "\$PID_FILE"))"
else
  echo "○ Not running"
fi

# RPC check
echo ""
echo "=== Tip Header (sync progress) ==="
curl -s -X POST http://127.0.0.1:${RPC_PORT}/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"get_tip_header","params":[],"id":1}' 2>/dev/null \
  | python3 -m json.tool 2>/dev/null || echo "(RPC not responding)"

echo ""
echo "=== Node Info ==="
curl -s -X POST http://127.0.0.1:${RPC_PORT}/ \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"local_node_info","params":[],"id":1}' 2>/dev/null \
  | python3 -c 'import sys,json; d=json.load(sys.stdin)["result"]; print(f"Node ID: {d[\"node_id\"]}"); print(f"Peers:   {len(d.get(\"connections\",[]))}"); print(f"Version: {d[\"version\"]}")' 2>/dev/null || echo "(RPC not responding)"
WRAPPER
ok "status.sh"

# test-rpc.sh
$SSH_CMD "cat > '${INSTALL_DIR}/test-rpc.sh' && chmod +x '${INSTALL_DIR}/test-rpc.sh'" << WRAPPER
#!/bin/sh
echo "=== CKB Light Client RPC Tests ==="
RPC="http://127.0.0.1:${RPC_PORT}"

echo ""
echo "1. local_node_info"
curl -s -X POST \$RPC -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"local_node_info","params":[],"id":1}' | python3 -m json.tool 2>/dev/null || echo "FAIL"

echo ""
echo "2. get_tip_header (sync progress)"
curl -s -X POST \$RPC -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"get_tip_header","params":[],"id":1}' | python3 -m json.tool 2>/dev/null || echo "FAIL"

echo ""
echo "3. get_peers"
curl -s -X POST \$RPC -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"get_peers","params":[],"id":1}' | python3 -c 'import sys,json; peers=json.load(sys.stdin).get("result",[]); print(f"{len(peers)} peers connected")' 2>/dev/null || echo "FAIL"

echo ""
echo "=== Tests complete ==="
WRAPPER
ok "test-rpc.sh"

# ── Knulli / EmulationStation integration ───────────────────
if [[ "$IS_KNULLI" == "y" ]]; then
  step "Knulli Integration"

  $SSH_CMD "mkdir -p /userdata/roms/ports"
  $SSH_CMD "cat > /userdata/roms/ports/Nervos-Launcher.sh && chmod +x /userdata/roms/ports/Nervos-Launcher.sh" << KNULLI
#!/bin/sh
echo "=== Nervos CKB Light Client ==="
echo ""
cd "${INSTALL_DIR}"

# Start if not running
if ! pgrep -f ckb-light-client >/dev/null 2>&1; then
  echo "Starting light client..."
  ./start.sh
  sleep 3
fi

./status.sh
echo ""
echo "Press any key to return to EmulationStation..."
read -n 1
KNULLI
  ok "Launcher: /userdata/roms/ports/Nervos-Launcher.sh"

  # Try to add ES system entry
  $SSH_CMD "
    ES_FILE='/userdata/system/configs/emulationstation/es_systems.yml'
    if [ -f \"\$ES_FILE\" ] && ! grep -q 'Nervos' \"\$ES_FILE\" 2>/dev/null; then
      cat >> \"\$ES_FILE\" << 'ESEOF'

nervos:
  name:      Nervos Launcher
  extensions: .sh
  path:      /userdata/roms/ports
  platform:  pc
  emulators:
    ports:
      default: \"Nervos-Launcher\"
ESEOF
      echo 'ES_ADDED'
    fi
  " 2>/dev/null | grep -q ES_ADDED && ok "Added to EmulationStation systems" || info "ES systems entry: add manually if needed"
fi

# ── Optional: systemd service ───────────────────────────────
HAS_SYSTEMD=$($SSH_CMD "command -v systemctl >/dev/null 2>&1 && echo 1 || echo 0")
if [[ "$HAS_SYSTEMD" == "1" && "$IS_KNULLI" != "y" ]]; then
  step "Systemd Service"
  read -rp "  Install systemd service for auto-start? [Y/n]: " WANT_SERVICE
  WANT_SERVICE="${WANT_SERVICE:-Y}"

  if [[ "$WANT_SERVICE" =~ ^[Yy] ]]; then
    $SSH_CMD "
      if [ \"\$(id -u)\" = '0' ]; then
        SFILE='/etc/systemd/system/ckb-light.service'
      else
        mkdir -p \"\$HOME/.config/systemd/user\"
        SFILE=\"\$HOME/.config/systemd/user/ckb-light.service\"
      fi
      cat > \"\$SFILE\" << 'SVCEOF'
[Unit]
Description=CKB Light Client (${NETWORK})
After=network.target

[Service]
Environment=RUST_LOG=info,ckb_light_client=info
ExecStart=${INSTALL_DIR}/bin/${BINARY_NAME} run --config-file ${INSTALL_DIR}/config.toml
WorkingDirectory=${INSTALL_DIR}
Restart=on-failure
RestartSec=10
StandardOutput=append:${INSTALL_DIR}/data/ckb-light.log
StandardError=append:${INSTALL_DIR}/data/ckb-light.log

[Install]
WantedBy=multi-user.target
SVCEOF
      if [ \"\$(id -u)\" = '0' ]; then
        systemctl daemon-reload
      else
        systemctl --user daemon-reload
      fi
      echo 'SERVICE_OK'
    " 2>/dev/null | grep -q SERVICE_OK && ok "systemd service installed: ckb-light" || warn "Service install failed"
  fi
fi

# ── Post-deploy smoke test ──────────────────────────────────
step "Smoke Test"
read -rp "  Start light client and test RPC? [Y/n]: " DO_SMOKE
DO_SMOKE="${DO_SMOKE:-Y}"

if [[ "$DO_SMOKE" =~ ^[Yy] ]]; then
  info "Starting on target..."
  $SSH_CMD "${INSTALL_DIR}/start.sh" 2>/dev/null

  printf "  Waiting for RPC"
  SMOKE_PASS=0
  for i in $(seq 1 20); do
    sleep 1
    printf "."
    RESULT=$($SSH_CMD "curl -sf -X POST http://127.0.0.1:${RPC_PORT}/ \
      -H 'Content-Type: application/json' \
      -d '{\"jsonrpc\":\"2.0\",\"method\":\"local_node_info\",\"params\":[],\"id\":1}'" 2>/dev/null || true)
    if echo "$RESULT" | grep -q '"node_id"' 2>/dev/null; then
      SMOKE_PASS=1
      break
    fi
  done
  echo ""

  if [[ "$SMOKE_PASS" == "1" ]]; then
    ok "Smoke test passed — light client is running"
    NODE_ID=$(echo "$RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["node_id"])' 2>/dev/null || echo "unknown")
    ok "Node ID: $NODE_ID"
  else
    warn "RPC not responding yet — may need more time to start"
    info "Check: ssh ${TARGET_USER}@${TARGET_HOST} '${INSTALL_DIR}/status.sh'"
  fi

  # Stop after smoke test
  $SSH_CMD "${INSTALL_DIR}/stop.sh" &>/dev/null
  info "Stopped after test — start with: ssh ${TARGET_USER}@${TARGET_HOST} '${INSTALL_DIR}/start.sh'"
fi

# ── Summary ─────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}${GREEN}  Deployment Complete!${RESET}"
echo -e "${BOLD}${GREEN}════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  ${BOLD}Target:${RESET}      ${TARGET_USER}@${TARGET_HOST}"
echo -e "  ${BOLD}Arch:${RESET}        ${TARGET_ARCH}"
echo -e "  ${BOLD}Install dir:${RESET} ${INSTALL_DIR}"
echo -e "  ${BOLD}Network:${RESET}     ${NETWORK}"
echo -e "  ${BOLD}RPC:${RESET}         127.0.0.1:${RPC_PORT}"
echo ""
echo -e "  ${BOLD}Commands (on target via SSH):${RESET}"
echo -e "    ${INSTALL_DIR}/start.sh       Start daemon"
echo -e "    ${INSTALL_DIR}/stop.sh        Stop daemon"
echo -e "    ${INSTALL_DIR}/status.sh      Sync progress + node info"
echo -e "    ${INSTALL_DIR}/test-rpc.sh    Full RPC test suite"
echo ""
if [[ "$IS_KNULLI" == "y" ]]; then
  echo -e "  ${BOLD}Knulli:${RESET} Reboot or refresh ES → look for 'Nervos Launcher' in Ports"
  echo ""
fi
echo "  Re-run this script for additional devices or updates."
echo ""
