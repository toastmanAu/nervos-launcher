#!/bin/sh
# Nervos Launcher — self-bootstrapping EmulationStation port
# Drop this file in /userdata/roms/ports/ (or any ports directory) and it handles the rest.
# Auto-detects and installs Python3 + pygame if missing.

INSTALL_DIR=/userdata/ckb-light-client
LAUNCHER_DIR=$INSTALL_DIR/nervos-launcher
REPO_URL="https://github.com/toastmanAu/nervos-launcher/archive/refs/heads/main.tar.gz"

# ── Detect install path ─────────────────────────────────────
# If /userdata doesn't exist (not a gaming OS), use home dir
if [ ! -d "/userdata" ]; then
  INSTALL_DIR="$HOME/ckb-light-client"
  LAUNCHER_DIR="$INSTALL_DIR/nervos-launcher"
fi

# ── Check Python3 ───────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 not found. Attempting install..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-pip
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --noconfirm python python-pip
  elif command -v opkg >/dev/null 2>&1; then
    opkg update && opkg install python3
  else
    echo "ERROR: Cannot install Python3 — no package manager found."
    echo "Please install Python 3.8+ manually and try again."
    echo "Press any key..."
    read -n 1
    exit 1
  fi
fi

# ── Check pygame ────────────────────────────────────────────
if ! python3 -c "import pygame" 2>/dev/null; then
  echo "pygame not found. Attempting install..."

  # Method 1: apt (Debian/Ubuntu/ArkOS/Armbian)
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y -qq python3-pygame 2>/dev/null || \
    python3 -m pip install pygame 2>/dev/null

  # Method 2: pip (generic fallback)
  elif command -v pip3 >/dev/null 2>&1; then
    pip3 install pygame

  elif python3 -m pip --version >/dev/null 2>&1; then
    python3 -m pip install pygame

  # Method 3: pacman (SteamOS/Arch)
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --noconfirm python-pygame 2>/dev/null || \
    python3 -m pip install pygame 2>/dev/null

  else
    echo "WARNING: Could not install pygame automatically."
    echo "Try: pip3 install pygame"
  fi

  # Verify
  if ! python3 -c "import pygame" 2>/dev/null; then
    echo "ERROR: pygame is required but could not be installed."
    echo "Install manually: pip3 install pygame (or python3 -m pip install pygame)"
    echo "Press any key..."
    read -n 1
    exit 1
  fi
  echo "pygame installed."
fi

# ── Download Nervos Launcher ────────────────────────────────
if [ ! -f "$LAUNCHER_DIR/launcher.py" ]; then
  echo "Downloading Nervos Launcher..."
  mkdir -p "$INSTALL_DIR"
  cd /tmp
  curl -fsSL -o nl.tar.gz "$REPO_URL"
  tar -xzf nl.tar.gz
  mkdir -p "$LAUNCHER_DIR"
  cp -r nervos-launcher-main/launcher.py nervos-launcher-main/lib nervos-launcher-main/screens nervos-launcher-main/assets "$LAUNCHER_DIR/"
  # Also copy packages.json for the package manager
  cp nervos-launcher-main/packages.json "$LAUNCHER_DIR/" 2>/dev/null
  rm -rf nl.tar.gz nervos-launcher-main
  echo "Nervos Launcher installed."
fi

# ── Launch ──────────────────────────────────────────────────
cd "$INSTALL_DIR"
python3 "$LAUNCHER_DIR/launcher.py"

if [ $? -ne 0 ]; then
  echo ""
  echo "Nervos Launcher exited with an error."
  echo "Check: python3 -c 'import pygame; print(pygame.ver)'"
  echo "Press any key..."
  read -n 1
fi
