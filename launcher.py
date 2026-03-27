#!/usr/bin/env python3
"""
Nervos Launcher — CKB Light Client companion app for handhelds
A pygame-based port for Knulli/EmulationStation devices.

Screens:
  - Home:      Dashboard with sync status, peers, block height
  - Explorer:  Tip header details, epoch info
  - Peers:     Connected peers list
  - Settings:  Start/stop service, boot toggle, config/log viewer
  - Terminal:  Mini shell with quick commands and scrollback

Navigation:
  D-pad     Scroll / navigate menus
  A         Select / confirm / run command
  B         Back
  Start     Home
  Select    Terminal shortcut
  L1/R1     Cycle quick commands (terminal)
  X         Clear terminal
  Y         Command history (terminal)
"""

import os
import sys

# Add parent dir to path for lib imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.ui import App
from lib.rpc import LightClientRPC, StatusPoller
from screens.home import HomePage
from screens.explorer import ExplorerPage
from screens.peers import PeersPage, PeerDetailPage
from screens.settings import SettingsPage
from screens.terminal import TerminalPage
from screens.text_viewer import TextViewerPage
from screens.install_progress import InstallProgressPage
from screens.button_map import ButtonMapPage, load_button_config


def find_install_dir():
    """Find the light client install directory."""
    candidates = [
        "/userdata/ckb-light-client",
        os.path.expanduser("~/ckb-light-client"),
        os.path.expanduser("~/.ckb-light-testnet"),
        os.path.expanduser("~/.ckb-light-mainnet"),
    ]
    for d in candidates:
        if os.path.exists(os.path.join(d, "bin", "ckb-light-client")):
            return d
    return candidates[0]  # default


def read_rpc_port(install_dir):
    """Read RPC port from config.toml."""
    config = os.path.join(install_dir, "config.toml")
    try:
        with open(config) as f:
            in_rpc = False
            for line in f:
                if line.strip() == "[rpc]":
                    in_rpc = True
                    continue
                if in_rpc and "listen_address" in line:
                    addr = line.split("=")[1].strip().strip('"')
                    return addr
                if line.strip().startswith("[") and in_rpc:
                    break
    except:
        pass
    return "127.0.0.1:9000"


def read_network(install_dir):
    """Read network from config.toml."""
    config = os.path.join(install_dir, "config.toml")
    try:
        with open(config) as f:
            for line in f:
                if line.strip().startswith("chain"):
                    return line.split("=")[1].strip().strip('"')
    except:
        pass
    return "testnet"


def main():
    install_dir = find_install_dir()
    rpc_addr = read_rpc_port(install_dir)
    rpc_url = f"http://{rpc_addr}"

    rpc = LightClientRPC(rpc_url)
    poller = StatusPoller(rpc, interval=3.0)

    app = App(width=640, height=480, fps=30)
    app.network = read_network(install_dir)

    # Register pages
    app.register_page("home",        HomePage(app, poller))
    app.register_page("explorer",    ExplorerPage(app, rpc))
    app.register_page("peers",       PeersPage(app, rpc))
    app.register_page("peer_detail", PeerDetailPage(app))
    app.register_page("settings",    SettingsPage(app, rpc, install_dir))
    app.register_page("terminal",    TerminalPage(app, install_dir))
    app.register_page("text_viewer", TextViewerPage(app))
    app.register_page("install_progress", InstallProgressPage(app))
    app.register_page("button_map", ButtonMapPage(app, install_dir,
                       on_complete=lambda m: app.go_home()))

    # Check for button config — show mapping screen on first boot
    btn_config = load_button_config(install_dir)
    if btn_config:
        app.button_map = btn_config
        app.navigate("home")
    else:
        # First boot — must map buttons before anything else
        app.navigate("button_map")

    # Run
    try:
        app.run()
    finally:
        poller.stop()


if __name__ == "__main__":
    main()
