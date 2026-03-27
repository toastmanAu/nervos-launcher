"""
explorer.py — Block explorer screen
Scrollable tip header with full hashes, no truncation.
"""

import pygame
import time
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, get_font


class ExplorerPage(Page):

    FONT_SIZE = 12
    LABEL_SIZE = 10
    LINE_H = 18
    LABEL_H = 16
    SPACER_H = 10

    def __init__(self, app, rpc):
        super().__init__(app)
        self.rpc = rpc
        self.tip = None
        self.refresh_timer = 0
        self.scroll = 0
        self.lines = []  # list of (type, label, value, color)

    def on_enter(self):
        self._refresh()

    def update(self, dt):
        self.refresh_timer += dt
        if self.refresh_timer > 5000:
            self._refresh()
            self.refresh_timer = 0

    def _refresh(self):
        self.tip = self.rpc.tip_header()
        self._build_lines()

    def _build_lines(self):
        """Build display lines with smart wrapping for long values."""
        self.lines = []
        if not self.tip:
            self.lines.append(("text", "", "Waiting for light client...", COLORS["muted"]))
            return

        inner = self.tip.get("inner", self.tip)

        # Parse fields
        number = inner.get("number", "0x0")
        block_num = int(number, 16) if isinstance(number, str) else number
        block_hash = inner.get("hash", "—")
        parent = inner.get("parent_hash", "—")
        timestamp = inner.get("timestamp", "0x0")
        ts_val = int(timestamp, 16) if isinstance(timestamp, str) else timestamp
        epoch = inner.get("epoch", "0x0")
        nonce = inner.get("nonce", "0x0")
        compact_target = inner.get("compact_target", "—")
        txs_root = inner.get("transactions_root", "—")
        proposals = inner.get("proposals_hash", "—")
        dao = inner.get("dao", "—")

        # Format time
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts_val / 1000)) if ts_val > 0 else "—"

        # Parse epoch
        epoch_val = int(epoch, 16) if isinstance(epoch, str) else epoch
        epoch_number = epoch_val >> 40
        epoch_index = (epoch_val >> 24) & 0xFFFF
        epoch_length = epoch_val & 0xFFFFFF

        # Build lines — ("label", name, value, color) or ("spacer",)
        self._add_field("BLOCK", f"#{block_num:,}", COLORS["accent"])
        self._add_field("TIME", ts_str, COLORS["text"])
        self._add_field("EPOCH", f"{epoch_number} ({epoch_index}/{epoch_length})", COLORS["green"])
        self.lines.append(("spacer",))
        self._add_field("HASH", block_hash, COLORS["text"])
        self._add_field("PARENT", parent, COLORS["text"])
        self.lines.append(("spacer",))
        self._add_field("NONCE", str(nonce), COLORS["dim"])
        self._add_field("TARGET", str(compact_target), COLORS["dim"])
        self.lines.append(("spacer",))
        self._add_field("TXS ROOT", txs_root, COLORS["text"])
        self._add_field("PROPOSALS", proposals, COLORS["text"])
        self._add_field("DAO", dao, COLORS["text"])

    def _add_field(self, label, value, color):
        """Add a label + value, wrapping the value if needed."""
        self.lines.append(("label", label, "", COLORS["muted"]))
        # Wrap value based on available width
        # We'll calculate wrap during draw, store full value here
        self.lines.append(("value", "", value, color))

    @property
    def _content_top(self):
        return 36

    @property
    def _content_bottom(self):
        return 30

    def _get_layout(self, surface):
        w = surface.get_width()
        margin = int(w * 0.025)
        content_w = w - margin * 2
        return w, margin, content_w

    def _total_height(self, content_w):
        """Calculate total content height with wrapping."""
        font = get_font(self.FONT_SIZE)
        total = 0
        for line in self.lines:
            if line[0] == "spacer":
                total += self.SPACER_H
            elif line[0] == "label":
                total += self.LABEL_H
            elif line[0] == "value":
                value = line[2]
                # Calculate wrapped lines
                wrapped = self._wrap_text(value, font, content_w - 8)
                total += len(wrapped) * self.LINE_H
        return total

    def _wrap_text(self, text, font, max_w):
        """Wrap text into multiple lines that fit within max_w pixels."""
        if not text:
            return [""]
        if font.size(text)[0] <= max_w:
            return [text]

        lines = []
        while text:
            # Binary search for the longest fitting substring
            lo, hi = 1, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.size(text[:mid])[0] <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            if lo == 0:
                lo = 1  # at least one char
            lines.append(text[:lo])
            text = text[lo:]
        return lines

    def draw(self, surface):
        w, margin, content_w = self._get_layout(surface)
        h = surface.get_height()
        visible_h = h - self._content_top - self._content_bottom

        draw_status_bar(surface, "Explorer", "Tip Header")

        if not self.tip:
            draw_text(surface, "Waiting for light client...", margin, 60, COLORS["muted"], size=14)
            draw_nav_bar(surface, [("B", "Back"), ("A", "Refresh")])
            return

        font_val = get_font(self.FONT_SIZE)
        font_lbl = get_font(self.LABEL_SIZE, bold=True)

        # Render all lines with scroll offset
        y = self._content_top - self.scroll
        for line in self.lines:
            if line[0] == "spacer":
                if y + self.SPACER_H > self._content_top and y < h - self._content_bottom:
                    mid_y = y + self.SPACER_H // 2
                    if self._content_top < mid_y < h - self._content_bottom:
                        pygame.draw.line(surface, COLORS["border"],
                                         (margin, mid_y), (margin + content_w, mid_y))
                y += self.SPACER_H

            elif line[0] == "label":
                if self._content_top <= y < h - self._content_bottom:
                    draw_text(surface, line[1], margin, y, COLORS["muted"],
                              size=self.LABEL_SIZE, bold=True)
                y += self.LABEL_H

            elif line[0] == "value":
                value = line[2]
                color = line[3]
                wrapped = self._wrap_text(value, font_val, content_w - 8)
                for wline in wrapped:
                    if self._content_top <= y < h - self._content_bottom:
                        draw_text(surface, wline, margin + 4, y, color, size=self.FONT_SIZE)
                    y += self.LINE_H

        # Scroll indicator
        total_h = self._total_height(content_w)
        if total_h > visible_h:
            bar_area = visible_h
            bar_h = max(10, int((visible_h / total_h) * bar_area))
            bar_y = self._content_top + int((self.scroll / total_h) * bar_area)
            bar_y = max(self._content_top, min(bar_y, h - self._content_bottom - bar_h))
            pygame.draw.rect(surface, COLORS["dim"], (w - 4, bar_y, 3, bar_h), border_radius=2)

        draw_nav_bar(surface, [("B", "Back"), ("A", "Refresh"), ("D-pad", "Scroll")])

    def _max_scroll(self, surface):
        _, _, content_w = self._get_layout(surface)
        h = surface.get_height()
        visible_h = h - self._content_top - self._content_bottom
        total_h = self._total_height(content_w)
        return max(0, total_h - visible_h)

    def handle_input(self, event):
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up":
                self.scroll = max(0, self.scroll - 20)
            elif d == "down":
                self.scroll = min(self._max_scroll(self.app.screen), self.scroll + 20)
            return True

        if event.type == pygame.JOYBUTTONDOWN and event.dict.get("btn") == "a":
            self._refresh()
            self.scroll = 0
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.scroll = max(0, self.scroll - 20)
            elif event.key == pygame.K_DOWN:
                self.scroll = min(self._max_scroll(self.app.screen), self.scroll + 20)
            elif event.key == pygame.K_RETURN:
                self._refresh()
                self.scroll = 0
            return True

        return False
