"""
settings.py — Service management and configuration
Start/stop light client, toggle boot service, view config.
"""

import pygame
import subprocess
import os
from lib.ui import Page, ScrollList, COLORS, draw_text, draw_status_bar, draw_nav_bar, draw_hline
from lib.installer import LightClientInstaller, ProgressLog


class SettingsPage(Page):

    def __init__(self, app, rpc, install_dir="/userdata/ckb-light-client"):
        super().__init__(app)
        self.rpc = rpc
        self.install_dir = install_dir
        self.installer = LightClientInstaller(install_dir)
        self.message = ""
        self.message_color = COLORS["text"]
        self.message_timer = 0
        self._installing = False

        self.menu = ScrollList([], item_height=32, visible_area_top=80, visible_area_bottom=32)
        self._wait_for_install = False
        self._rebuild_menu()

    def on_enter(self):
        self._rebuild_menu()

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = ""
        # Refresh menu after install completes
        if self._wait_for_install and self.installer.progress.done:
            self._wait_for_install = False
            self._installing = False
            self._rebuild_menu()
            if self.installer.progress.success:
                self._set_message("Install complete", COLORS["green"])
            else:
                self._set_message("Install failed — check progress log", COLORS["red"])

    def _rebuild_menu(self):
        running = self._is_running()
        service = self._has_service()

        items = [
            {
                "text": "Stop Light Client" if running else "Start Light Client",
                "subtext": "● Running" if running else "○ Stopped",
                "subcolor": COLORS["green"] if running else COLORS["red"],
                "action": "toggle_service",
            },
            {
                "text": "Disable Boot Service" if service else "Enable Boot Service",
                "subtext": "auto-start on boot",
                "action": "toggle_boot",
            },
            {
                "text": "Install / Update Light Client",
                "subtext": self._install_status(),
                "subcolor": COLORS["green"] if self._binary_exists() else COLORS["yellow"],
                "action": "install_update",
            },
            {"text": "", "subtext": "", "action": None},  # divider
            {
                "text": "View Config",
                "subtext": "config.toml",
                "action": "view_config",
            },
            {
                "text": "View Log (last 20 lines)",
                "subtext": "ckb-light.log",
                "action": "view_log",
            },
            {
                "text": "Network Info",
                "subtext": self._read_network(),
                "action": None,
            },
            {
                "text": "Install Dir",
                "subtext": self.install_dir,
                "subcolor": COLORS["muted"],
                "action": None,
            },
            {
                "text": "RPC Port",
                "subtext": self._read_rpc_port(),
                "action": None,
            },
        ]
        self.menu.update_items(items)

    def _is_running(self):
        pid_file = os.path.join(self.install_dir, "data", "ckb-light.pid")
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except:
            return False

    def _binary_exists(self):
        return os.path.isfile(os.path.join(self.install_dir, "bin", "ckb-light-client"))

    def _install_status(self):
        if self._binary_exists():
            try:
                result = subprocess.run(
                    [os.path.join(self.install_dir, "bin", "ckb-light-client"), "--version"],
                    capture_output=True, text=True, timeout=5)
                ver = result.stdout.strip().split()[-1] if result.stdout else "installed"
                return f"v{ver}" if not ver.startswith("v") else ver
            except:
                return "installed"
        return "not installed"

    def _has_service(self):
        """Check if an init script or cron entry exists for auto-start."""
        # Check common locations
        for path in ["/etc/init.d/S99ckb-light", "/etc/init.d/ckb-light"]:
            if os.path.exists(path):
                return True
        # Check crontab
        try:
            result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=3)
            if "ckb-light" in result.stdout:
                return True
        except:
            pass
        return False

    def _read_network(self):
        config_path = os.path.join(self.install_dir, "config.toml")
        try:
            with open(config_path) as f:
                for line in f:
                    if line.strip().startswith("chain"):
                        return line.split("=")[1].strip().strip('"')
        except:
            pass
        return "unknown"

    def _read_rpc_port(self):
        config_path = os.path.join(self.install_dir, "config.toml")
        try:
            with open(config_path) as f:
                for line in f:
                    if "listen_address" in line and "rpc" not in line[:10]:
                        continue
                    if "listen_address" in line:
                        return line.split("=")[1].strip().strip('"')
        except:
            pass
        return "127.0.0.1:9000"

    def _set_message(self, text, color=None, duration=3000):
        self.message = text
        self.message_color = color or COLORS["text"]
        self.message_timer = duration

    def _toggle_service(self):
        if self._is_running():
            # Stop
            try:
                subprocess.run([os.path.join(self.install_dir, "stop.sh")],
                               capture_output=True, timeout=5)
                self._set_message("Light client stopped", COLORS["yellow"])
            except Exception as e:
                self._set_message(f"Error: {e}", COLORS["red"])
        else:
            # Start
            try:
                subprocess.run([os.path.join(self.install_dir, "start.sh")],
                               capture_output=True, timeout=5)
                self._set_message("Light client started", COLORS["green"])
            except Exception as e:
                self._set_message(f"Error: {e}", COLORS["red"])
        self._rebuild_menu()

    def _toggle_boot(self):
        """Create or remove an init.d script for auto-start on Knulli/Buildroot."""
        init_script = "/etc/init.d/S99ckb-light"
        if self._has_service():
            try:
                os.remove(init_script)
                self._set_message("Boot service disabled", COLORS["yellow"])
            except Exception as e:
                self._set_message(f"Error: {e}", COLORS["red"])
        else:
            try:
                script = f"""#!/bin/sh
# CKB Light Client auto-start
case "$1" in
  start)
    {self.install_dir}/start.sh
    ;;
  stop)
    {self.install_dir}/stop.sh
    ;;
  *)
    echo "Usage: $0 {{start|stop}}"
    exit 1
    ;;
esac
"""
                with open(init_script, "w") as f:
                    f.write(script)
                os.chmod(init_script, 0o755)
                self._set_message("Boot service enabled", COLORS["green"])
            except Exception as e:
                self._set_message(f"Error: {e}", COLORS["red"])
        self._rebuild_menu()

    def _view_config(self):
        """Navigate to a text viewer showing the config file."""
        config_path = os.path.join(self.install_dir, "config.toml")
        try:
            with open(config_path) as f:
                content = f.read()
            if "text_viewer" in self.app.pages:
                self.app.pages["text_viewer"].set_content("config.toml", content)
                self.app.navigate("text_viewer")
        except Exception as e:
            self._set_message(f"Error: {e}", COLORS["red"])

    def _view_log(self):
        """Navigate to text viewer showing last 20 lines of log."""
        log_path = os.path.join(self.install_dir, "data", "ckb-light.log")
        try:
            with open(log_path) as f:
                lines = f.readlines()
            content = "".join(lines[-20:])
            if "text_viewer" in self.app.pages:
                self.app.pages["text_viewer"].set_content("ckb-light.log (last 20)", content)
                self.app.navigate("text_viewer")
        except Exception as e:
            self._set_message(f"Error: {e}", COLORS["red"])

    def draw(self, surface):
        draw_status_bar(surface, "Settings", "")
        w = surface.get_width()

        # ── Service status indicator panel ────────────────────
        y = 36
        panel = pygame.Rect(8, y, w - 16, 38)
        running = self._is_running()
        installed = self._binary_exists()
        service = self._has_service()

        bg = COLORS["surface"]
        pygame.draw.rect(surface, bg, panel, border_radius=6)
        border_color = COLORS["green"] if running else COLORS["border"]
        pygame.draw.rect(surface, border_color, panel, width=1, border_radius=6)

        # Status dot + text
        dot_color = COLORS["green"] if running else COLORS["red"] if installed else COLORS["yellow"]
        pygame.draw.circle(surface, dot_color, (24, y + 19), 5)

        if running:
            draw_text(surface, "Light Client Running", 36, y + 4, COLORS["green"], size=13, bold=True)
        elif installed:
            draw_text(surface, "Light Client Stopped", 36, y + 4, COLORS["red"], size=13, bold=True)
        else:
            draw_text(surface, "Light Client Not Installed", 36, y + 4, COLORS["yellow"], size=13, bold=True)

        # Sub-info
        tags = []
        if installed:
            tags.append(self._install_status())
        if service:
            tags.append("boot: on")
        else:
            tags.append("boot: off")
        if running:
            tags.append(self._read_network())
        draw_text(surface, " · ".join(tags), 36, y + 21, COLORS["muted"], size=10)

        self.menu.draw(surface)

        # Message toast
        if self.message:
            y = surface.get_height() - 60
            draw_text(surface, self.message, 16, y, self.message_color, size=13)

        draw_nav_bar(surface, [("B", "Back"), ("A", "Select"), ("D-pad", "Scroll")])

    def handle_input(self, event):
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up": self.menu.move(-1)
            elif d == "down": self.menu.move(1)
            return True

        if event.type == pygame.JOYBUTTONDOWN and event.dict.get("btn") == "a":
            return self._activate_selected()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: self.menu.move(-1)
            elif event.key == pygame.K_DOWN: self.menu.move(1)
            elif event.key == pygame.K_RETURN: return self._activate_selected()
            return True

        return False

    def _activate_selected(self):
        selected = self.menu.get_selected()
        if not selected or not selected.get("action"):
            return False
        action = selected["action"]
        if action == "toggle_service":
            self._toggle_service()
        elif action == "toggle_boot":
            self._toggle_boot()
        elif action == "view_config":
            self._view_config()
        elif action == "view_log":
            self._view_log()
        elif action == "install_update":
            self._install_update()
        return True

    def _install_update(self):
        """Launch install with live progress screen."""
        if self.installer.progress.busy:
            return
        # Navigate to progress screen and start install
        if "install_progress" in self.app.pages:
            progress_page = self.app.pages["install_progress"]
            progress_page.set_progress(self.installer.progress)
            self.app.navigate("install_progress")
            network = self._read_network()
            if network == "unknown":
                network = "testnet"  # default for fresh installs
            self.installer.install_async(network)
            self._installing = True

            # Rebuild menu when install finishes (checked in update)
            self._wait_for_install = True
