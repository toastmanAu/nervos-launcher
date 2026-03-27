"""
terminal.py — Mini terminal screen
Runs shell commands and displays output with scrollback.
"""

import pygame
import subprocess
import threading
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, get_font


class TerminalPage(Page):
    """Mini terminal with command history and scrollback buffer."""

    MAX_LINES = 200
    FONT_SIZE = 11
    LINE_HEIGHT = 14

    def __init__(self, app, install_dir="/userdata/ckb-light-client"):
        super().__init__(app)
        self.install_dir = install_dir
        self.lines = [
            ("Nervos Launcher Terminal", COLORS["accent"]),
            ("Type commands. D-pad to scroll. B to exit.", COLORS["muted"]),
            ("", COLORS["text"]),
        ]
        self.scroll_offset = 0  # 0 = bottom (most recent)
        self.input_buffer = ""
        self.history = []
        self.history_idx = -1
        self.busy = False

        # Pre-built quick commands
        self.quick_cmds = [
            "status.sh",
            "status.sh",
            "start.sh",
            "stop.sh",
            "test-rpc.sh",
            "curl -sf https://api.github.com/repos/nervosnetwork/ckb-light-client/releases/latest | python3 -c 'import sys,json;r=json.load(sys.stdin);print(r[\"tag_name\"],\"-\",len(r[\"assets\"]),\"assets\")'",
            "top -bn1 | head -8",
            "df -h",
            "free -m",
        ]
        self.quick_idx = 0

    def on_enter(self):
        self.scroll_offset = 0

    @property
    def visible_lines(self):
        return (480 - 32 - 28 - 24) // self.LINE_HEIGHT  # status bar, nav bar, input line

    def _add_line(self, text, color=None):
        color = color or COLORS["text"]
        # Wrap long lines
        font = get_font(self.FONT_SIZE)
        max_w = 640 - 16
        while text:
            # Find how much fits
            fit = len(text)
            while fit > 0 and font.size(text[:fit])[0] > max_w:
                fit -= 1
            if fit == 0:
                fit = 1
            self.lines.append((text[:fit], color))
            text = text[fit:]

        # Trim scrollback
        if len(self.lines) > self.MAX_LINES:
            self.lines = self.lines[-self.MAX_LINES:]

        # Auto-scroll to bottom
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
                # Resolve relative commands to install dir
                if cmd.endswith(".sh") and "/" not in cmd:
                    full_cmd = f"cd {self.install_dir} && ./{cmd}"
                else:
                    full_cmd = cmd
                result = subprocess.run(
                    full_cmd, shell=True,
                    capture_output=True, text=True, timeout=15,
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
        draw_status_bar(surface, "Terminal", "Quick: L1/R1")

        # Output area
        y_start = 34
        y_end = 480 - 28 - 24  # leave room for input + nav
        vis = self.visible_lines

        # Calculate which lines to show
        total = len(self.lines)
        bottom_idx = total - self.scroll_offset
        top_idx = max(0, bottom_idx - vis)

        y = y_start
        for i in range(top_idx, min(bottom_idx, total)):
            text, color = self.lines[i]
            draw_text(surface, text, 8, y, color, size=self.FONT_SIZE)
            y += self.LINE_HEIGHT

        # Scroll indicator
        if total > vis:
            bar_area = y_end - y_start
            bar_h = max(10, int((vis / total) * bar_area))
            bar_pos = y_start + int(((total - self.scroll_offset - vis) / total) * bar_area)
            bar_pos = max(y_start, min(bar_pos, y_end - bar_h))
            pygame.draw.rect(surface, COLORS["dim"], (636, bar_pos, 3, bar_h), border_radius=2)

        # Input line
        input_y = 480 - 28 - 22
        pygame.draw.rect(surface, COLORS["surface"], (0, input_y, 640, 22))
        pygame.draw.line(surface, COLORS["border"], (0, input_y), (640, input_y))

        prompt = f"$ {self.input_buffer}"
        if self.busy:
            prompt = "  [running...]"
        cursor = "█" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        draw_text(surface, prompt + cursor, 8, input_y + 3, COLORS["accent"], size=self.FONT_SIZE)

        # Quick command hint
        if not self.busy and not self.input_buffer:
            hint = f"L1/R1: {self.quick_cmds[self.quick_idx]}"
            font = get_font(self.FONT_SIZE)
            hw = font.size(hint)[0]
            draw_text(surface, hint, 640 - hw - 8, input_y + 3, COLORS["dim"], size=self.FONT_SIZE)

        draw_nav_bar(surface, [("B", "Back"), ("A", "Run"), ("L1/R1", "Quick Cmd")])

    def handle_input(self, event):
        # D-pad scroll
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up":
                self.scroll_offset = min(self.scroll_offset + 3, max(0, len(self.lines) - self.visible_lines))
            elif d == "down":
                self.scroll_offset = max(0, self.scroll_offset - 3)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            # A = run quick command or input
            if event.dict.get("btn") == "a":
                if self.input_buffer:
                    self._run_cmd(self.input_buffer)
                    self.input_buffer = ""
                else:
                    self._run_cmd(self.quick_cmds[self.quick_idx])
                return True
            # L1 = prev quick cmd
            if event.dict.get("btn") == "l1":
                self.quick_idx = (self.quick_idx - 1) % len(self.quick_cmds)
                return True
            # R1 = next quick cmd
            if event.dict.get("btn") == "r1":
                self.quick_idx = (self.quick_idx + 1) % len(self.quick_cmds)
                return True
            # X = clear output
            if event.dict.get("btn") == "x":
                self.lines = [("(cleared)", COLORS["muted"])]
                self.scroll_offset = 0
                return True
            # Y = history
            if event.dict.get("btn") == "y":
                if self.history:
                    self.history_idx = (self.history_idx + 1) % len(self.history)
                    self.input_buffer = self.history[-(self.history_idx + 1)]
                return True

        # Keyboard (desktop testing)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.input_buffer:
                    self._run_cmd(self.input_buffer)
                    self.input_buffer = ""
                else:
                    self._run_cmd(self.quick_cmds[self.quick_idx])
            elif event.key == pygame.K_UP:
                self.scroll_offset = min(self.scroll_offset + 3, max(0, len(self.lines) - self.visible_lines))
            elif event.key == pygame.K_DOWN:
                self.scroll_offset = max(0, self.scroll_offset - 3)
            elif event.key == pygame.K_TAB:
                self.quick_idx = (self.quick_idx + 1) % len(self.quick_cmds)
            elif event.key == pygame.K_DELETE:
                self.input_buffer = ""
            elif event.key in (pygame.K_BACKSPACE,):
                self.input_buffer = self.input_buffer[:-1]
            elif event.unicode and event.unicode.isprintable():
                self.input_buffer += event.unicode
            return True

        return False
