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

    # Persistent service paths (survives reboot on overlay FS)
    USERDATA_SERVICE = "/userdata/system/services/ckb_light"
    USERDATA_CUSTOM = "/userdata/system/custom.sh"
    SYSTEMD_SERVICE = "/etc/systemd/system/ckb-light.service"

    def _has_service(self):
        """Check if auto-start is configured (persistent across reboots)."""
        # Knulli/Batocera: /userdata/system/services/
        if os.path.exists(self.USERDATA_SERVICE):
            return True
        # Knulli/Batocera: custom.sh contains our entry
        try:
            with open(self.USERDATA_CUSTOM) as f:
                if "ckb-light" in f.read():
                    return True
        except:
            pass
        # Systemd (standard Linux)
        if os.path.exists(self.SYSTEMD_SERVICE):
            return True
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
        """Toggle auto-start. Uses persistent path that survives overlay FS reboots."""
        if self._has_service():
            self._disable_service()
        else:
            self._enable_service()
        self._rebuild_menu()

    def _enable_service(self):
        """Enable auto-start using the best available method."""
        try:
            # Method 1: Knulli/Batocera userdata services (preferred, persistent)
            if os.path.exists("/userdata/system") or os.path.exists("/userdata"):
                svc_dir = "/userdata/system/services"
                os.makedirs(svc_dir, exist_ok=True)

                script = f"""#!/bin/sh
# CKB Light Client auto-start (Nervos Launcher)
case "$1" in
  start)
    {self.install_dir}/start.sh
    ;;
  stop)
    {self.install_dir}/stop.sh
    ;;
esac
"""
                with open(self.USERDATA_SERVICE, "w") as f:
                    f.write(script)
                os.chmod(self.USERDATA_SERVICE, 0o755)

                # Enable via batocera-settings if available
                try:
                    subprocess.run(
                        ["batocera-settings-set", "system.services", "ckb_light"],
                        capture_output=True, timeout=5)
                except:
                    # Fallback: also add to custom.sh for older Knulli
                    custom = self.USERDATA_CUSTOM
                    existing = ""
                    try:
                        with open(custom) as f:
                            existing = f.read()
                    except:
                        pass
                    if "ckb-light" not in existing:
                        with open(custom, "a") as f:
                            f.write(f"\n# CKB Light Client auto-start\n{self.install_dir}/start.sh &\n")

                self._set_message("Boot service enabled (persistent)", COLORS["green"])
                return

            # Method 2: Systemd (standard Linux)
            if os.path.exists("/etc/systemd/system"):
                unit = f"""[Unit]
Description=CKB Light Client
After=network.target

[Service]
Type=forking
ExecStart={self.install_dir}/start.sh
ExecStop={self.install_dir}/stop.sh
WorkingDirectory={self.install_dir}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
                with open(self.SYSTEMD_SERVICE, "w") as f:
                    f.write(unit)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=5)
                subprocess.run(["systemctl", "enable", "ckb-light"], capture_output=True, timeout=5)
                self._set_message("Systemd service enabled", COLORS["green"])
                return

        except Exception as e:
            self._set_message(f"Error: {e}", COLORS["red"])

    def _disable_service(self):
        """Disable auto-start."""
        try:
            # Remove userdata service
            if os.path.exists(self.USERDATA_SERVICE):
                os.remove(self.USERDATA_SERVICE)

            # Remove from custom.sh
            try:
                with open(self.USERDATA_CUSTOM) as f:
                    lines = f.readlines()
                with open(self.USERDATA_CUSTOM, "w") as f:
                    skip_next = False
                    for line in lines:
                        if "CKB Light Client" in line or "ckb-light" in line:
                            skip_next = True
                            continue
                        if skip_next and line.strip().endswith("&"):
                            skip_next = False
                            continue
                        skip_next = False
                        f.write(line)
            except:
                pass

            # Disable systemd
            if os.path.exists(self.SYSTEMD_SERVICE):
                subprocess.run(["systemctl", "disable", "ckb-light"], capture_output=True, timeout=5)
                os.remove(self.SYSTEMD_SERVICE)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=5)

            # Try batocera-settings
            try:
                subprocess.run(["batocera-settings-set", "system.services", ""],
                               capture_output=True, timeout=5)
            except:
                pass

            self._set_message("Boot service disabled", COLORS["yellow"])
        except Exception as e:
            self._set_message(f"Error: {e}", COLORS["red"])

    def _view_config(self):
        """Open config.toml in the editor (editable with reset-to-default)."""
        config_path = os.path.join(self.install_dir, "config.toml")
        try:
            with open(config_path) as f:
                content = f.read()

            def save_config(text):
                with open(config_path, "w") as f:
                    f.write(text)

            def reset_config():
                import urllib.request
                network = self._read_network()
                if network == "unknown":
                    network = "testnet"
                url = f"https://raw.githubusercontent.com/nervosnetwork/ckb-light-client/develop/config/{network}.toml"
                with urllib.request.urlopen(url, timeout=15) as resp:
                    new_config = resp.read().decode()
                with open(config_path, "w") as f:
                    f.write(new_config)
                return new_config

            if "editor" in self.app.pages:
                self.app.pages["editor"].open(
                    title="config.toml",
                    content=content,
                    on_save=save_config,
                    read_only=False,
                    syntax="toml",
                    reset_fn=reset_config,
                )
                self.app.navigate("editor")
        except Exception as e:
            self._set_message(f"Error: {e}", COLORS["red"])

    def _view_log(self):
        """Open log in editor (read-only, log syntax highlighting)."""
        log_path = os.path.join(self.install_dir, "data", "ckb-light.log")
        try:
            with open(log_path) as f:
                lines = f.readlines()
            content = "".join(lines[-50:])  # last 50 lines
            if "editor" in self.app.pages:
                self.app.pages["editor"].open(
                    title="ckb-light.log",
                    content=content,
                    read_only=True,
                    syntax="log",
                )
                self.app.navigate("editor")
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
