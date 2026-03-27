"""
explorer.py — Block explorer screen
Shows tip header details, epoch info, and block data.
"""

import pygame
import time
from lib.ui import Page, COLORS, draw_text, draw_status_bar, draw_nav_bar, draw_hline


class ExplorerPage(Page):

    def __init__(self, app, rpc):
        super().__init__(app)
        self.rpc = rpc
        self.tip = None
        self.refresh_timer = 0

    def on_enter(self):
        self._refresh()

    def update(self, dt):
        self.refresh_timer += dt
        if self.refresh_timer > 5000:  # refresh every 5s
            self._refresh()
            self.refresh_timer = 0

    def _refresh(self):
        self.tip = self.rpc.tip_header()

    def draw(self, surface):
        draw_status_bar(surface, "Explorer", "Tip Header")
        w = surface.get_width()

        if not self.tip:
            draw_text(surface, "Waiting for light client...", 16, 60, COLORS["muted"], size=14)
            draw_nav_bar(surface, [("B", "Back"), ("A", "Refresh")])
            return

        inner = self.tip.get("inner", self.tip)
        y = 44

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
        if ts_val > 0:
            ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts_val / 1000))
        else:
            ts_str = "—"

        # Parse epoch
        epoch_val = int(epoch, 16) if isinstance(epoch, str) else epoch
        epoch_number = epoch_val >> 40
        epoch_index = (epoch_val >> 24) & 0xFFFF
        epoch_length = epoch_val & 0xFFFFFF

        fields = [
            ("Block", f"#{block_num:,}", COLORS["accent"]),
            ("Time", ts_str, COLORS["text"]),
            ("Epoch", f"{epoch_number} ({epoch_index}/{epoch_length})", COLORS["green"]),
            ("", "", None),  # spacer
            ("Hash", block_hash, COLORS["muted"]),
            ("Parent", parent[:32] + "...", COLORS["muted"]),
            ("Nonce", str(nonce), COLORS["dim"]),
            ("Target", str(compact_target), COLORS["dim"]),
            ("", "", None),
            ("Txs Root", txs_root[:32] + "...", COLORS["muted"]),
            ("Proposals", proposals[:32] + "...", COLORS["muted"]),
            ("DAO", dao[:32] + "...", COLORS["muted"]),
        ]

        for label, value, color in fields:
            if not label:
                y += 6
                draw_hline(surface, y, margin=12)
                y += 6
                continue
            draw_text(surface, label, 16, y, COLORS["muted"], size=11)
            draw_text(surface, value, 110, y, color or COLORS["text"], size=12,
                      max_width=w - 126)
            y += 20

        draw_nav_bar(surface, [("B", "Back"), ("A", "Refresh")])

    def handle_input(self, event):
        if event.type == pygame.JOYBUTTONDOWN and event.dict.get("btn") == "a":
            self._refresh()
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._refresh()
            return True
        return False
