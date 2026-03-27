"""
terminal.py — Mini terminal screen
X/Y toggle command categories. L1/R1 cycle within category.
Commands are user-editable via data/terminal-commands.json.
"""

import pygame
import subprocess
import threading
import json
import os
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, get_font
from lib.keyboard import OnScreenKeyboard


# Default command categories — saved to JSON on first run, user-editable after
DEFAULT_COMMANDS = {
    "RPC": [
        ["Tip Header", "curl -s -X POST http://127.0.0.1:9000/ -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"get_tip_header\",\"params\":[],\"id\":1}' | python3 -m json.tool"],
        ["Node Info", "curl -s -X POST http://127.0.0.1:9000/ -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"local_node_info\",\"params\":[],\"id\":1}' | python3 -m json.tool"],
        ["Peers", "curl -s -X POST http://127.0.0.1:9000/ -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"get_peers\",\"params\":[],\"id\":1}' | python3 -m json.tool"],
        ["Scripts", "curl -s -X POST http://127.0.0.1:9000/ -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"get_scripts\",\"params\":[],\"id\":1}' | python3 -m json.tool"],
        ["Peer Count", "curl -s -X POST http://127.0.0.1:9000/ -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"get_peers\",\"params\":[],\"id\":1}' | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get(\"result\",[])),\"peers\")'"],
        ["Block Number", "curl -s -X POST http://127.0.0.1:9000/ -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"get_tip_header\",\"params\":[],\"id\":1}' | python3 -c 'import sys,json;r=json.load(sys.stdin).get(\"result\",{});i=r.get(\"inner\",r);print(\"Block:\",int(i.get(\"number\",\"0x0\"),16))'"],
    ],
    "Service": [
        ["Status", "status.sh"],
        ["Start", "start.sh"],
        ["Stop", "stop.sh"],
        ["Log (last 30)", "tail -30 data/ckb-light.log"],
        ["Log (errors)", "grep -i 'error\\|warn\\|panic' data/ckb-light.log | tail -20"],
        ["Version", "bin/ckb-light-client --version"],
        ["Config", "cat config.toml"],
    ],
    "System": [
        ["CPU + Memory", "top -bn1 | head -8"],
        ["Memory", "free -m"],
        ["Disk", "df -h"],
        ["Processes", "ps aux --sort=-%mem | head -12"],
        ["Uptime", "uptime"],
        ["Kernel", "uname -a"],
        ["OS Info", "cat /etc/os-release 2>/dev/null | head -5"],
        ["Temperature", "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null && echo ' (millidegrees C)' || echo 'N/A'"],
    ],
    "Network": [
        ["IP Address", "ip addr show | grep 'inet ' | grep -v 127.0.0.1"],
        ["WiFi", "iwconfig 2>/dev/null | head -10 || echo 'No wireless'"],
        ["Routes", "ip route"],
        ["DNS", "cat /etc/resolv.conf"],
        ["Ports Listening", "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null | head -15"],
        ["Ping CKB Testnet", "ping -c 3 -W 2 18.217.146.65"],
        ["SSH Status", "pgrep sshd && echo 'SSH running' || echo 'SSH not running'"],
    ],
    "Install": [
        ["List Available", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;pm=PackageManager();pm.refresh();[print(f'{p[chr(110)+chr(97)+chr(109)+chr(101)]:20s} {p.get(chr(118)+chr(101)+chr(114)+chr(115)+chr(105)+chr(111)+chr(110),chr(63)):10s} {chr(9989) if p.get(chr(105)+chr(115)+chr(95)+chr(105)+chr(110)+chr(115)+chr(116)+chr(97)+chr(108)+chr(108)+chr(101)+chr(100)) else chr(11036)}  {p.get(chr(100)+chr(101)+chr(115)+chr(99)+chr(114)+chr(105)+chr(112)+chr(116)+chr(105)+chr(111)+chr(110),chr(45))}') for p in pm.list_available()]\""],
        ["Install jq", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('jq');[print(l[0]) for l in p.get_lines()]\""],
        ["Install micro", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('micro');[print(l[0]) for l in p.get_lines()]\""],
        ["Install yq", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('yq');[print(l[0]) for l in p.get_lines()]\""],
        ["Install ffmpeg (audio+h264)", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('ffmpeg-nervos');[print(l[0]) for l in p.get_lines()]\""],
        ["Install ffmpeg-full (70MB)", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('ffmpeg-full');[print(l[0]) for l in p.get_lines()]\""],
        ["Install btm", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('btm');[print(l[0]) for l in p.get_lines()]\""],
        ["Install duf", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('duf');[print(l[0]) for l in p.get_lines()]\""],
        ["Install curlie", "python3 -c \"import sys;sys.path.insert(0,'/userdata/ckb-light-client/nervos-launcher');from lib.packages import PackageManager;from lib.installer import ProgressLog;p=ProgressLog();pm=PackageManager(progress=p);pm.install('curlie');[print(l[0]) for l in p.get_lines()]\""],
        ["Installed Pkgs", "cat /userdata/ckb-light-client/packages/installed.json 2>/dev/null | python3 -m json.tool || echo 'No packages installed'"],
        ["Package bin dir", "ls -lh /userdata/ckb-light-client/packages/bin/ 2>/dev/null || echo 'No packages installed'"],
        ["Disk Free", "df -h /userdata"],
        ["Disk Usage (quick)", "du -sh /userdata/ckb-light-client/ 2>/dev/null; du -sh /userdata/roms/ 2>/dev/null; du -sh /userdata/saves/ 2>/dev/null"],
    ],
}

COMMANDS_FILE = "data/terminal-commands.json"


def load_commands(install_dir):
    """Load user-editable commands from JSON, or create defaults."""
    path = os.path.join(install_dir, COMMANDS_FILE)
    try:
        with open(path) as f:
            return json.load(f)
    except:
        pass
    # Write defaults
    save_commands(install_dir, DEFAULT_COMMANDS)
    return DEFAULT_COMMANDS


def save_commands(install_dir, commands):
    path = os.path.join(install_dir, COMMANDS_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(commands, f, indent=2)


def reset_commands(install_dir):
    """Reset commands to defaults."""
    save_commands(install_dir, DEFAULT_COMMANDS)
    return DEFAULT_COMMANDS


class TerminalPage(Page):
    """Mini terminal with categorized quick commands and scrollback buffer."""

    MAX_LINES = 200
    FONT_SIZE = 11
    LINE_HEIGHT = 14

    def __init__(self, app, install_dir="/userdata/ckb-light-client"):
        super().__init__(app)
        self.install_dir = install_dir
        self.lines = [
            ("Nervos Launcher Terminal", COLORS["accent"]),
            ("X/Y: category  L1/R1: command  A: run", COLORS["muted"]),
            ("", COLORS["text"]),
        ]
        self.scroll_offset = 0
        self.input_buffer = ""
        self.history = []
        self.history_idx = -1
        self.busy = False
        self.keyboard = OnScreenKeyboard()

        # Load commands
        self.commands = load_commands(install_dir)
        self.cat_names = list(self.commands.keys())
        self.cat_idx = 0
        self.cmd_idx = 0

    def on_enter(self):
        self.scroll_offset = 0
        # Reload commands in case user edited the JSON
        self.commands = load_commands(self.install_dir)
        self.cat_names = list(self.commands.keys())

    @property
    def _current_category(self):
        if self.cat_names:
            return self.cat_names[self.cat_idx % len(self.cat_names)]
        return ""

    @property
    def _current_commands(self):
        return self.commands.get(self._current_category, [])

    @property
    def _current_cmd(self):
        cmds = self._current_commands
        if cmds and 0 <= self.cmd_idx < len(cmds):
            return cmds[self.cmd_idx]
        return ["", ""]

    @property
    def visible_lines(self):
        return (self.app.height - 32 - 28 - 42) // self.LINE_HEIGHT

    def _add_line(self, text, color=None):
        color = color or COLORS["text"]
        font = get_font(self.FONT_SIZE)
        max_w = self.app.width - 16
        while text:
            fit = len(text)
            while fit > 0 and font.size(text[:fit])[0] > max_w:
                fit -= 1
            if fit == 0:
                fit = 1
            self.lines.append((text[:fit], color))
            text = text[fit:]

        if len(self.lines) > self.MAX_LINES:
            self.lines = self.lines[-self.MAX_LINES:]
        self.scroll_offset = 0

    def _run_cmd(self, cmd):
        if self.busy:
            return
        self.busy = True
        self._add_line(f"$ {cmd}", COLORS["accent"])
        self.history.append(cmd)
        self.history_idx = -1

        def _exec():
            try:
                if cmd.endswith(".sh") and "/" not in cmd:
                    full_cmd = f"cd {self.install_dir} && ./{cmd}"
                else:
                    full_cmd = cmd
                result = subprocess.run(
                    full_cmd, shell=True,
                    capture_output=True, text=True, timeout=300,
                    cwd=self.install_dir
                )
                for line in result.stdout.splitlines():
                    self._add_line(line)
                for line in result.stderr.splitlines():
                    self._add_line(line, COLORS["yellow"])
                if result.returncode != 0:
                    self._add_line(f"[exit {result.returncode}]", COLORS["red"])
            except subprocess.TimeoutExpired:
                self._add_line("[timeout — 15s limit]", COLORS["red"])
            except Exception as e:
                self._add_line(f"[error: {e}]", COLORS["red"])
            finally:
                self._add_line("", COLORS["text"])
                self.busy = False

        threading.Thread(target=_exec, daemon=True).start()

    def draw(self, surface):
        w = surface.get_width()
        h = surface.get_height()
        margin = int(w * 0.015)

        draw_status_bar(surface, "Terminal", f"[{self._current_category}]")

        # Output area
        y_start = 34
        y_end = h - 28 - 40
        vis = (y_end - y_start) // self.LINE_HEIGHT

        total = len(self.lines)
        bottom_idx = total - self.scroll_offset
        top_idx = max(0, bottom_idx - vis)

        y = y_start
        for i in range(top_idx, min(bottom_idx, total)):
            text, color = self.lines[i]
            draw_text(surface, text, margin, y, color, size=self.FONT_SIZE)
            y += self.LINE_HEIGHT

        # Scroll indicator
        if total > vis:
            bar_area = y_end - y_start
            bar_h = max(10, int((vis / total) * bar_area))
            bar_pos = y_start + int(((total - self.scroll_offset - vis) / total) * bar_area)
            bar_pos = max(y_start, min(bar_pos, y_end - bar_h))
            pygame.draw.rect(surface, COLORS["dim"], (w - 4, bar_pos, 3, bar_h), border_radius=2)

        # ── Category tabs + command preview ──────────────────
        preview_y = h - 28 - 38
        pygame.draw.rect(surface, COLORS["surface"], (0, preview_y, w, 20))
        pygame.draw.line(surface, COLORS["border"], (0, preview_y), (w, preview_y))

        tab_x = margin
        for i, cat in enumerate(self.cat_names):
            is_active = (i == self.cat_idx % len(self.cat_names))
            color = COLORS["accent"] if is_active else COLORS["dim"]
            draw_text(surface, cat, tab_x, preview_y + 4, color, size=9, bold=is_active)
            tab_x += get_font(9, is_active).size(cat)[0] + 8

        # Current command name on right
        cmd_name = self._current_cmd[0]
        if cmd_name:
            font = get_font(10)
            cw = font.size(cmd_name)[0]
            draw_text(surface, cmd_name, w - cw - margin, preview_y + 4, COLORS["green"], size=10)

        # ── Input line ───────────────────────────────────────
        input_y = h - 28 - 18
        pygame.draw.rect(surface, COLORS["surface2"], (0, input_y, w, 18))

        if self.busy:
            prompt = "  [running...]"
        elif self.input_buffer:
            prompt = f"$ {self.input_buffer}"
        else:
            prompt = f"$ {cmd_name}" if cmd_name else "$ "

        cursor = "█" if not self.busy and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        pcolor = COLORS["accent"] if self.input_buffer or self.busy else COLORS["muted"]
        draw_text(surface, prompt + cursor, margin, input_y + 2, pcolor, size=self.FONT_SIZE)

        # Keyboard overlay
        self.keyboard.draw(surface)

        if not self.keyboard.active:
            draw_nav_bar(surface, [("A", "Run"), ("X/Y", "Cat"), ("L1/R1", "Cmd"), ("SEL", "Edit"), ("ST", "Keyboard")])

    def _open_keyboard(self):
        """Open on-screen keyboard for typing custom commands."""
        def on_done(text):
            if text.strip():
                self.input_buffer = text.strip()
                self._run_cmd(self.input_buffer)
                self.input_buffer = ""

        self.keyboard.open(
            initial_text=self.input_buffer,
            on_done=on_done,
            title="Type command",
        )

    def handle_input(self, event):
        # Keyboard gets priority when active
        if self.keyboard.active:
            return self.keyboard.handle_input(event)

        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up":
                self.scroll_offset = min(self.scroll_offset + 3, max(0, len(self.lines) - self.visible_lines))
            elif d == "down":
                self.scroll_offset = max(0, self.scroll_offset - 3)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.dict.get("btn", "")

            if btn == "a":
                if self.input_buffer:
                    self._run_cmd(self.input_buffer)
                    self.input_buffer = ""
                else:
                    cmd = self._current_cmd
                    if cmd and cmd[1]:
                        self._run_cmd(cmd[1])
                return True

            # Start = open keyboard to type custom command
            if btn == "start":
                self._open_keyboard()
                return True

            if btn == "x":
                if self.cat_names:
                    self.cat_idx = (self.cat_idx + 1) % len(self.cat_names)
                    self.cmd_idx = 0
                return True

            if btn == "y":
                if self.cat_names:
                    self.cat_idx = (self.cat_idx - 1) % len(self.cat_names)
                    self.cmd_idx = 0
                return True

            if btn == "l1":
                cmds = self._current_commands
                if cmds:
                    self.cmd_idx = (self.cmd_idx - 1) % len(cmds)
                return True

            if btn == "r1":
                cmds = self._current_commands
                if cmds:
                    self.cmd_idx = (self.cmd_idx + 1) % len(cmds)
                return True

            # Select = edit terminal commands JSON
            if btn == "select":
                self._open_command_editor()
                return True

        # Keyboard fallback
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.input_buffer:
                    self._run_cmd(self.input_buffer)
                    self.input_buffer = ""
                else:
                    cmd = self._current_cmd
                    if cmd and cmd[1]:
                        self._run_cmd(cmd[1])
            elif event.key == pygame.K_UP:
                self.scroll_offset = min(self.scroll_offset + 3, max(0, len(self.lines) - self.visible_lines))
            elif event.key == pygame.K_DOWN:
                self.scroll_offset = max(0, self.scroll_offset - 3)
            elif event.key == pygame.K_TAB:
                if self.cat_names:
                    self.cat_idx = (self.cat_idx + 1) % len(self.cat_names)
                    self.cmd_idx = 0
            elif event.key == pygame.K_BACKSPACE:
                self.input_buffer = self.input_buffer[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.input_buffer += event.unicode
            return True

        return False

    def _open_command_editor(self):
        """Open terminal commands JSON in the editor."""
        cmd_path = os.path.join(self.install_dir, COMMANDS_FILE)
        try:
            content = json.dumps(self.commands, indent=2)

            def save_commands_from_editor(text):
                try:
                    new_cmds = json.loads(text)
                    save_commands(self.install_dir, new_cmds)
                    self.commands = new_cmds
                    self.cat_names = list(self.commands.keys())
                    self.cat_idx = 0
                    self.cmd_idx = 0
                    self._add_line("Commands updated from editor", COLORS["green"])
                except json.JSONDecodeError as e:
                    self._add_line(f"Invalid JSON: {e}", COLORS["red"])

            def reset_commands_fn():
                from screens.terminal import DEFAULT_COMMANDS
                save_commands(self.install_dir, DEFAULT_COMMANDS)
                self.commands = DEFAULT_COMMANDS
                self.cat_names = list(self.commands.keys())
                self.cat_idx = 0
                self.cmd_idx = 0
                self._add_line("Commands reset to defaults", COLORS["green"])
                return json.dumps(DEFAULT_COMMANDS, indent=2)

            if "editor" in self.app.pages:
                self.app.pages["editor"].open(
                    title="Terminal Commands",
                    content=content,
                    on_save=save_commands_from_editor,
                    read_only=False,
                    syntax="json",
                    reset_fn=reset_commands_fn,
                )
                self.app.navigate("editor")
        except Exception as e:
            self._add_line(f"Error opening editor: {e}", COLORS["red"])
