"""
keyboard.py — On-screen gamepad keyboard
75% of screen when active, minimisable.
D-pad navigates grid, A selects char, B = backspace, L1/R1 = shift/symbols.
Reusable widget — any screen can invoke it.
"""

import pygame
from lib.ui import COLORS, draw_text, draw_box, get_font

# Character sets — L1/R1 cycles between them
CHARSETS = [
    {
        "name": "abc",
        "rows": [
            list("qwertyuiop"),
            list("asdfghjkl"),
            list("zxcvbnm"),
            ["SPACE", "⌫", "←", "→", "DONE"],
        ],
    },
    {
        "name": "ABC",
        "rows": [
            list("QWERTYUIOP"),
            list("ASDFGHJKL"),
            list("ZXCVBNM"),
            ["SPACE", "⌫", "←", "→", "DONE"],
        ],
    },
    {
        "name": "123",
        "rows": [
            list("1234567890"),
            list("!@#$%^&*()"),
            list("-_=+[]{}"),
            ["SPACE", "⌫", "←", "→", "DONE"],
        ],
    },
    {
        "name": "hex",
        "rows": [
            list("0123456789"),
            list("abcdef"),
            list("ABCDEF"),
            ["0x", "SPACE", "⌫", "←", "→", "DONE"],
        ],
    },
    {
        "name": "sym",
        "rows": [
            list("/\\|~`'\""),
            list(".,;:<>?"),
            list("{}[]()@#"),
            ["SPACE", "⌫", "←", "→", "DONE"],
        ],
    },
]


class OnScreenKeyboard:
    """
    On-screen keyboard widget for gamepad-only devices.

    Usage:
        kb = OnScreenKeyboard()
        kb.open(initial_text="hello", on_done=callback, title="Edit value")
        # In your page's draw(): kb.draw(surface)
        # In your page's handle_input(): if kb.active: kb.handle_input(event)
    """

    def __init__(self):
        self.active = False
        self.minimised = False
        self.text = ""
        self.cursor_pos = 0  # cursor position in text
        self.on_done = None  # callback(text) when DONE pressed
        self.on_cancel = None  # callback() when cancelled
        self.title = ""

        # Grid navigation
        self.charset_idx = 0
        self.row = 0
        self.col = 0

        # Animation
        self._slide_progress = 0.0  # 0=hidden, 1=full

    def open(self, initial_text="", on_done=None, on_cancel=None, title=""):
        """Open the keyboard with initial text."""
        self.active = True
        self.minimised = False
        self.text = initial_text
        self.cursor_pos = len(initial_text)
        self.on_done = on_done
        self.on_cancel = on_cancel
        self.title = title
        self.charset_idx = 0
        self.row = 0
        self.col = 0
        self._slide_progress = 1.0

    def close(self):
        """Close keyboard without calling callback."""
        self.active = False
        self._slide_progress = 0.0

    def toggle_minimise(self):
        """Toggle between full and minimised view."""
        self.minimised = not self.minimised

    @property
    def _charset(self):
        return CHARSETS[self.charset_idx % len(CHARSETS)]

    @property
    def _rows(self):
        return self._charset["rows"]

    @property
    def _current_key(self):
        rows = self._rows
        if 0 <= self.row < len(rows):
            row = rows[self.row]
            if 0 <= self.col < len(row):
                return row[self.col]
        return ""

    def draw(self, surface):
        """Draw the keyboard overlay. Call from your page's draw()."""
        if not self.active:
            return

        w = surface.get_width()
        h = surface.get_height()

        if self.minimised:
            self._draw_minimised(surface, w, h)
            return

        # Keyboard takes bottom 75% of screen
        kb_h = int(h * 0.75)
        kb_y = h - kb_h
        margin = int(w * 0.02)

        # Semi-transparent background
        overlay = pygame.Surface((w, kb_h), pygame.SRCALPHA)
        overlay.fill((10, 12, 15, 240))
        surface.blit(overlay, (0, kb_y))

        # Border line at top
        pygame.draw.line(surface, COLORS["accent"], (0, kb_y), (w, kb_y), 2)

        # Title + charset indicator
        y = kb_y + 6
        draw_text(surface, self.title or "Keyboard", margin, y, COLORS["accent"], size=11, bold=True)
        charset_name = self._charset["name"]
        cs_font = get_font(10, True)
        cs_w = cs_font.size(charset_name)[0]
        draw_text(surface, f"L1/R1: {charset_name}", w - cs_w - 60, y, COLORS["muted"], size=10)

        # Text input field with cursor
        y += 20
        field_rect = pygame.Rect(margin, y, w - margin * 2, 24)
        draw_box(surface, field_rect, fill=COLORS["surface2"], border=COLORS["border"])

        # Render text with cursor
        display_text = self.text[:self.cursor_pos] + "│" + self.text[self.cursor_pos:]
        draw_text(surface, display_text, margin + 6, y + 4, COLORS["text"], size=12,
                  max_width=w - margin * 2 - 12)

        # Character grid
        y += 32
        rows = self._rows
        key_padding = 3
        available_w = w - margin * 2

        for ri, row in enumerate(rows):
            # Calculate key width for this row
            total_special_w = 0
            normal_count = 0
            for key in row:
                if len(key) > 1:
                    total_special_w += get_font(11).size(key)[0] + 16
                else:
                    normal_count += 1

            if normal_count > 0:
                remaining_w = available_w - total_special_w - (len(row) - 1) * key_padding
                key_w = max(20, remaining_w // normal_count)
            else:
                key_w = 40

            # Center the row
            total_row_w = sum(
                (get_font(11).size(k)[0] + 16) if len(k) > 1 else key_w
                for k in row
            ) + (len(row) - 1) * key_padding
            x = margin + (available_w - total_row_w) // 2

            for ci, key in enumerate(row):
                if len(key) > 1:
                    this_w = get_font(11).size(key)[0] + 16
                else:
                    this_w = key_w

                key_h = 28
                rect = pygame.Rect(x, y, this_w, key_h)
                is_selected = (ri == self.row and ci == self.col)

                if is_selected:
                    pygame.draw.rect(surface, COLORS["accent"], rect, border_radius=4)
                    text_color = COLORS["bg"]
                else:
                    pygame.draw.rect(surface, COLORS["surface"], rect, border_radius=4)
                    pygame.draw.rect(surface, COLORS["border"], rect, width=1, border_radius=4)
                    text_color = COLORS["text"]

                # Center key label
                font = get_font(12 if len(key) == 1 else 10)
                label = key if key != "SPACE" else "___"
                tw = font.size(label)[0]
                draw_text(surface, label, x + (this_w - tw) // 2, y + 5,
                          text_color, size=12 if len(key) == 1 else 10)

                x += this_w + key_padding

            y += key_h + key_padding

        # Help bar
        y = h - 20
        draw_text(surface, "A:type  B:⌫  X:minimise  Y:cancel  L1/R1:charset",
                  margin, y, COLORS["dim"], size=9)

    def _draw_minimised(self, surface, w, h):
        """Draw minimised bar at bottom showing current text."""
        bar_h = 28
        bar_y = h - 28 - bar_h  # above nav bar
        margin = int(w * 0.02)

        pygame.draw.rect(surface, COLORS["surface"], (0, bar_y, w, bar_h))
        pygame.draw.line(surface, COLORS["accent"], (0, bar_y), (w, bar_y))

        draw_text(surface, f"KB: {self.text[:40]}{'...' if len(self.text) > 40 else ''}",
                  margin, bar_y + 6, COLORS["text"], size=11)
        draw_text(surface, "X:expand", w - 70, bar_y + 7, COLORS["muted"], size=10)

    def handle_input(self, event):
        """Handle input when keyboard is active. Returns True if consumed."""
        if not self.active:
            return False

        # D-pad navigation
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            rows = self._rows
            if d == "up":
                self.row = max(0, self.row - 1)
                self.col = min(self.col, len(rows[self.row]) - 1)
            elif d == "down":
                self.row = min(len(rows) - 1, self.row + 1)
                self.col = min(self.col, len(rows[self.row]) - 1)
            elif d == "left":
                self.col = max(0, self.col - 1)
            elif d == "right":
                self.col = min(len(rows[self.row]) - 1, self.col + 1)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.dict.get("btn", "")

            # A = type selected character
            if btn == "a":
                key = self._current_key
                if key == "DONE":
                    if self.on_done:
                        self.on_done(self.text)
                    self.close()
                elif key == "⌫":
                    if self.cursor_pos > 0:
                        self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                        self.cursor_pos -= 1
                elif key == "SPACE":
                    self.text = self.text[:self.cursor_pos] + " " + self.text[self.cursor_pos:]
                    self.cursor_pos += 1
                elif key == "←":
                    self.cursor_pos = max(0, self.cursor_pos - 1)
                elif key == "→":
                    self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
                elif key == "0x":
                    self.text = self.text[:self.cursor_pos] + "0x" + self.text[self.cursor_pos:]
                    self.cursor_pos += 2
                else:
                    self.text = self.text[:self.cursor_pos] + key + self.text[self.cursor_pos:]
                    self.cursor_pos += 1
                return True

            # B = backspace
            if btn == "b":
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                return True

            # X = minimise/expand
            if btn == "x":
                self.toggle_minimise()
                return True

            # Y = cancel
            if btn == "y":
                if self.on_cancel:
                    self.on_cancel()
                self.close()
                return True

            # L1 = prev charset
            if btn == "l1":
                self.charset_idx = (self.charset_idx - 1) % len(CHARSETS)
                self.row = min(self.row, len(self._rows) - 1)
                self.col = min(self.col, len(self._rows[self.row]) - 1)
                return True

            # R1 = next charset
            if btn == "r1":
                self.charset_idx = (self.charset_idx + 1) % len(CHARSETS)
                self.row = min(self.row, len(self._rows) - 1)
                self.col = min(self.col, len(self._rows[self.row]) - 1)
                return True

        # Keyboard fallback (desktop testing)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.close()
                return True
            elif event.key == pygame.K_RETURN:
                if self.on_done:
                    self.on_done(self.text)
                self.close()
                return True
            elif event.key == pygame.K_BACKSPACE:
                if self.cursor_pos > 0:
                    self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                    self.cursor_pos -= 1
                return True
            elif event.unicode and event.unicode.isprintable():
                self.text = self.text[:self.cursor_pos] + event.unicode + self.text[self.cursor_pos:]
                self.cursor_pos += 1
                return True

        return False
