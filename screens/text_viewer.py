"""
text_viewer.py — Generic scrollable text viewer
Used by settings to show config files, logs, etc.
"""

import pygame
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, get_font


class TextViewerPage(Page):
    """Scrollable text viewer. Set content before navigating here."""

    FONT_SIZE = 11
    LINE_HEIGHT = 14

    def __init__(self, app):
        super().__init__(app)
        self.title = ""
        self.lines = []
        self.scroll = 0

    def set_content(self, title, text):
        self.title = title
        self.lines = text.splitlines()
        self.scroll = 0

    @property
    def visible_lines(self):
        return (480 - 32 - 28) // self.LINE_HEIGHT

    def draw(self, surface):
        draw_status_bar(surface, self.title, f"{len(self.lines)} lines")

        y = 34
        vis = self.visible_lines
        for i in range(self.scroll, min(self.scroll + vis, len(self.lines))):
            line = self.lines[i]
            color = COLORS["text"]
            # Simple syntax highlighting
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                color = COLORS["muted"]
            elif "=" in line and not line.strip().startswith("["):
                color = COLORS["accent"]
            elif stripped.startswith("["):
                color = COLORS["green"]
            elif "error" in line.lower() or "ERROR" in line:
                color = COLORS["red"]
            elif "warn" in line.lower() or "WARN" in line:
                color = COLORS["yellow"]
            elif "INFO" in line:
                color = COLORS["muted"]

            draw_text(surface, line, 8, y, color, size=self.FONT_SIZE,
                      max_width=surface.get_width() - 16)
            y += self.LINE_HEIGHT

        # Scroll indicator
        total = len(self.lines)
        if total > vis:
            bar_area = vis * self.LINE_HEIGHT
            bar_h = max(10, int((vis / total) * bar_area))
            bar_y = 34 + int((self.scroll / total) * bar_area)
            pygame.draw.rect(surface, COLORS["dim"], (636, bar_y, 3, bar_h), border_radius=2)

        draw_nav_bar(surface, [("B", "Back"), ("D-pad", "Scroll")])

    def handle_input(self, event):
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up": self.scroll = max(0, self.scroll - 3)
            elif d == "down": self.scroll = min(max(0, len(self.lines) - self.visible_lines), self.scroll + 3)
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: self.scroll = max(0, self.scroll - 3)
            elif event.key == pygame.K_DOWN: self.scroll = min(max(0, len(self.lines) - self.visible_lines), self.scroll + 3)
            return True

        return False
