"""
editor.py — Reusable text editor widget with on-screen keyboard
Scrollable multi-line text viewer/editor. Any module can call it.

Usage:
    from lib.editor import TextEditorPage

    # In launcher.py:
    app.register_page("editor", TextEditorPage(app))

    # To open from any screen:
    editor = app.pages["editor"]
    editor.open(
        title="config.toml",
        content=file_contents,
        on_save=lambda text: save_file(path, text),
        read_only=False,
        syntax="toml",  # "toml", "json", "log", "plain"
        reset_fn=lambda: download_default_config(),  # optional reset button
    )
    app.navigate("editor")
"""

import pygame
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, get_font, draw_box
from lib.keyboard import OnScreenKeyboard


class TextEditorPage(Page):
    """
    Multi-line text viewer/editor with word wrapping,
    syntax highlighting, and on-screen keyboard for editing.
    """

    FONT_SIZE = 11
    LINE_HEIGHT = 14

    def __init__(self, app):
        super().__init__(app)
        self.title = ""
        self.lines = []         # wrapped display lines
        self.raw_lines = []     # original lines (for editing)
        self.scroll = 0
        self.cursor_line = 0    # which raw line is selected
        self.read_only = True
        self.syntax = "plain"
        self.on_save = None
        self.reset_fn = None
        self.modified = False
        self.message = ""
        self.message_timer = 0

        # Keyboard
        self.keyboard = OnScreenKeyboard()

        # Wrap cache
        self._wrap_map = []  # maps display line index → raw line index

    def open(self, title="", content="", on_save=None, read_only=True,
             syntax="plain", reset_fn=None):
        """Set up the editor with content."""
        self.title = title
        self.raw_lines = content.splitlines() if content else [""]
        self.scroll = 0
        self.cursor_line = 0
        self.read_only = read_only
        self.syntax = syntax
        self.on_save = on_save
        self.reset_fn = reset_fn
        self.modified = False
        self.message = ""
        self._rewrap()

    def _rewrap(self):
        """Wrap all lines for display."""
        font = get_font(self.FONT_SIZE)
        max_w = self.app.width - 32  # margins
        self.lines = []
        self._wrap_map = []

        for raw_idx, raw_line in enumerate(self.raw_lines):
            if not raw_line:
                self.lines.append("")
                self._wrap_map.append(raw_idx)
                continue

            # Word wrap
            remaining = raw_line
            while remaining:
                if font.size(remaining)[0] <= max_w:
                    self.lines.append(remaining)
                    self._wrap_map.append(raw_idx)
                    break
                # Find break point
                fit = len(remaining)
                while fit > 0 and font.size(remaining[:fit])[0] > max_w:
                    fit -= 1
                if fit == 0:
                    fit = 1
                self.lines.append(remaining[:fit])
                self._wrap_map.append(raw_idx)
                remaining = remaining[fit:]

    @property
    def _visible_lines(self):
        kb_offset = int(self.app.height * 0.75) if (self.keyboard.active and not self.keyboard.minimised) else 0
        return (self.app.height - 32 - 28 - kb_offset) // self.LINE_HEIGHT

    def _syntax_color(self, line):
        """Return color based on syntax type and line content."""
        stripped = line.strip()
        if self.syntax == "toml":
            if stripped.startswith("#"):
                return COLORS["muted"]
            if stripped.startswith("["):
                return COLORS["green"]
            if "=" in line and not stripped.startswith("#"):
                return COLORS["accent"]
        elif self.syntax == "json":
            if '"' in line and ':' in line:
                return COLORS["accent"]
            if stripped in ("{", "}", "[", "]", "},", "],"):
                return COLORS["dim"]
        elif self.syntax == "log":
            lower = stripped.lower()
            if "error" in lower or "panic" in lower:
                return COLORS["red"]
            if "warn" in lower:
                return COLORS["yellow"]
            if "info" in lower:
                return COLORS["muted"]
        return COLORS["text"]

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = ""

    def draw(self, surface):
        w = surface.get_width()
        h = surface.get_height()
        margin = int(w * 0.025)

        # Status bar
        mode = "EDIT" if not self.read_only else "VIEW"
        mod_indicator = " *" if self.modified else ""
        draw_status_bar(surface, f"{self.title}{mod_indicator}", mode)

        # Calculate visible area (shrinks when keyboard is open)
        vis = self._visible_lines
        content_h = vis * self.LINE_HEIGHT

        # Draw lines
        y = 34
        for i in range(self.scroll, min(self.scroll + vis, len(self.lines))):
            line = self.lines[i]
            raw_idx = self._wrap_map[i] if i < len(self._wrap_map) else -1
            color = self._syntax_color(line)

            # Highlight selected line (in edit mode)
            if not self.read_only and raw_idx == self.cursor_line:
                highlight = pygame.Rect(margin - 2, y - 1, w - margin * 2 + 4, self.LINE_HEIGHT)
                pygame.draw.rect(surface, COLORS["surface2"], highlight, border_radius=2)

            # Line number (subtle)
            if raw_idx >= 0:
                draw_text(surface, f"{raw_idx + 1:3d}", margin, y, COLORS["dim"], size=9)

            draw_text(surface, line, margin + 28, y, color, size=self.FONT_SIZE)
            y += self.LINE_HEIGHT

        # Scroll indicator
        total = len(self.lines)
        if total > vis:
            bar_area = content_h
            bar_h = max(10, int((vis / total) * bar_area))
            bar_y = 34 + int((self.scroll / max(1, total)) * bar_area)
            bar_y = max(34, min(bar_y, 34 + bar_area - bar_h))
            pygame.draw.rect(surface, COLORS["dim"], (w - 4, bar_y, 3, bar_h), border_radius=2)

        # Message toast
        if self.message:
            draw_text(surface, self.message, margin, h - 60, COLORS["green"], size=12)

        # Keyboard overlay
        self.keyboard.draw(surface)

        # Nav bar
        if self.keyboard.active:
            pass  # keyboard draws its own help
        elif self.read_only:
            draw_nav_bar(surface, [("B", "Back"), ("D-pad", "Scroll")])
        else:
            nav = [("B", "Back"), ("A", "Edit Line"), ("X", "Save")]
            if self.reset_fn:
                nav.append(("Y", "Reset"))
            draw_nav_bar(surface, nav)

    def handle_input(self, event):
        # Keyboard gets priority when active
        if self.keyboard.active:
            return self.keyboard.handle_input(event)

        # D-pad scroll
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up":
                if not self.read_only:
                    self.cursor_line = max(0, self.cursor_line - 1)
                    self._ensure_cursor_visible()
                else:
                    self.scroll = max(0, self.scroll - 3)
            elif d == "down":
                if not self.read_only:
                    self.cursor_line = min(len(self.raw_lines) - 1, self.cursor_line + 1)
                    self._ensure_cursor_visible()
                else:
                    self.scroll = min(max(0, len(self.lines) - self._visible_lines), self.scroll + 3)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.dict.get("btn", "")

            # A = edit selected line (if not read-only)
            if btn == "a" and not self.read_only:
                self._edit_current_line()
                return True

            # X = save
            if btn == "x" and not self.read_only:
                self._save()
                return True

            # Y = reset to default
            if btn == "y" and self.reset_fn:
                self._reset()
                return True

        # Keyboard fallback
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.scroll = max(0, self.scroll - 3)
            elif event.key == pygame.K_DOWN:
                self.scroll = min(max(0, len(self.lines) - self._visible_lines), self.scroll + 3)
            elif event.key == pygame.K_RETURN and not self.read_only:
                self._edit_current_line()
            return True

        return False

    def _ensure_cursor_visible(self):
        """Scroll to keep cursor line in view."""
        # Find first display line for this raw line
        for i, raw_idx in enumerate(self._wrap_map):
            if raw_idx == self.cursor_line:
                if i < self.scroll:
                    self.scroll = i
                elif i >= self.scroll + self._visible_lines:
                    self.scroll = i - self._visible_lines + 1
                break

    def _edit_current_line(self):
        """Open keyboard to edit the current line."""
        current_text = self.raw_lines[self.cursor_line] if self.cursor_line < len(self.raw_lines) else ""

        def on_done(new_text):
            self.raw_lines[self.cursor_line] = new_text
            self.modified = True
            self._rewrap()

        self.keyboard.open(
            initial_text=current_text,
            on_done=on_done,
            title=f"Line {self.cursor_line + 1}",
        )

    def _save(self):
        """Save the content."""
        if self.on_save:
            content = "\n".join(self.raw_lines)
            try:
                self.on_save(content)
                self.modified = False
                self.message = "Saved"
                self.message_timer = 2000
            except Exception as e:
                self.message = f"Save failed: {e}"
                self.message_timer = 3000

    def _reset(self):
        """Reset content to defaults."""
        if self.reset_fn:
            try:
                new_content = self.reset_fn()
                if new_content:
                    self.raw_lines = new_content.splitlines() if isinstance(new_content, str) else [""]
                    self.modified = False
                    self._rewrap()
                    self.scroll = 0
                    self.cursor_line = 0
                    self.message = "Reset to defaults"
                    self.message_timer = 2000
            except Exception as e:
                self.message = f"Reset failed: {e}"
                self.message_timer = 3000
