"""
install_progress.py — Live install/update progress screen
Shows scrolling log output from the installer with auto-scroll.
"""

import pygame
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, get_font


class InstallProgressPage(Page):
    """Displays live progress from a ProgressLog instance."""

    FONT_SIZE = 11
    LINE_HEIGHT = 14

    def __init__(self, app):
        super().__init__(app)
        self.progress = None  # set before navigating
        self.scroll_offset = 0  # 0 = auto-scroll (follow bottom)
        self.auto_scroll = True

    def set_progress(self, progress):
        self.progress = progress
        self.scroll_offset = 0
        self.auto_scroll = True

    @property
    def visible_lines(self):
        return (480 - 32 - 28) // self.LINE_HEIGHT

    def draw(self, surface):
        if not self.progress:
            return

        title = self.progress.title or "Installing"
        if self.progress.done:
            if self.progress.success:
                draw_status_bar(surface, title, "✓ Complete")
            else:
                draw_status_bar(surface, title, "✗ Failed")
        elif self.progress.busy:
            # Animated spinner
            frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            idx = (pygame.time.get_ticks() // 100) % len(frames)
            draw_status_bar(surface, title, f"{frames[idx]} Working...")
        else:
            draw_status_bar(surface, title, "")

        # Draw log lines
        lines = self.progress.get_lines()
        vis = self.visible_lines
        total = len(lines)

        if self.auto_scroll:
            start = max(0, total - vis)
        else:
            start = max(0, min(self.scroll_offset, total - vis))

        y = 34
        color_map = {
            "text":   COLORS["text"],
            "accent": COLORS["accent"],
            "green":  COLORS["green"],
            "yellow": COLORS["yellow"],
            "red":    COLORS["red"],
            "muted":  COLORS["muted"],
        }

        for i in range(start, min(start + vis, total)):
            text, color_name = lines[i]
            color = color_map.get(color_name, COLORS["text"])
            draw_text(surface, text, 8, y, color, size=self.FONT_SIZE,
                      max_width=surface.get_width() - 16)
            y += self.LINE_HEIGHT

        # Scroll indicator
        if total > vis:
            bar_area = vis * self.LINE_HEIGHT
            bar_h = max(10, int((vis / total) * bar_area))
            bar_y = 34 + int((start / max(1, total)) * bar_area)
            bar_y = min(bar_y, 34 + bar_area - bar_h)
            pygame.draw.rect(surface, COLORS["dim"], (636, bar_y, 3, bar_h), border_radius=2)

        # Nav
        if self.progress.done:
            draw_nav_bar(surface, [("B", "Back"), ("A", "Done")])
        else:
            draw_nav_bar(surface, [("D-pad", "Scroll")])

    def handle_input(self, event):
        # D-pad scroll
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up":
                self.auto_scroll = False
                self.scroll_offset = max(0, self.scroll_offset - 3)
            elif d == "down":
                lines = self.progress.get_lines() if self.progress else []
                max_scroll = max(0, len(lines) - self.visible_lines)
                self.scroll_offset = min(max_scroll, self.scroll_offset + 3)
                if self.scroll_offset >= max_scroll:
                    self.auto_scroll = True
            return True

        # B or A when done = go back
        if event.type == pygame.JOYBUTTONDOWN:
            if self.progress and self.progress.done:
                if event.button in (0, 1):  # A or B
                    self.app.go_back()
                    return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.auto_scroll = False
                self.scroll_offset = max(0, self.scroll_offset - 3)
            elif event.key == pygame.K_DOWN:
                lines = self.progress.get_lines() if self.progress else []
                max_scroll = max(0, len(lines) - self.visible_lines)
                self.scroll_offset = min(max_scroll, self.scroll_offset + 3)
                if self.scroll_offset >= max_scroll:
                    self.auto_scroll = True
            elif event.key in (pygame.K_RETURN, pygame.K_BACKSPACE):
                if self.progress and self.progress.done:
                    self.app.go_back()
            return True

        return False
