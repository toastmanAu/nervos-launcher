"""
home.py — Dashboard screen
Shows sync status, peers, block height, and main menu navigation.
"""

import pygame
from lib.ui import Page, ScrollList, COLORS, draw_text, draw_text_centered
from lib.ui import draw_status_bar, draw_nav_bar, draw_box, draw_hline, get_font


class HomePage(Page):

    def __init__(self, app, poller):
        super().__init__(app)
        self.poller = poller

        self.menu = ScrollList([
            {"text": "Explorer",  "subtext": "Block info, headers",  "action": "explorer"},
            {"text": "Peers",     "subtext": "Connected nodes",      "action": "peers"},
            {"text": "Settings",  "subtext": "Service, config",      "action": "settings"},
            {"text": "Terminal",  "subtext": "System shell",         "action": "terminal"},
        ], item_height=36, visible_area_top=220, visible_area_bottom=32)

    def on_enter(self):
        self.poller.start()

    def draw(self, surface):
        s = self.poller.status
        w = surface.get_width()

        # Status bar
        alive = s.get("alive", False)
        status_text = "● ONLINE" if alive else "○ OFFLINE"
        status_color = COLORS["green"] if alive else COLORS["red"]
        draw_status_bar(surface, "Nervos Launcher", s.get("version", ""))

        # ── Dashboard cards ──────────────────────────────────
        y = 44

        # Block height (big number)
        block = s.get("block", 0)
        draw_text(surface, "BLOCK HEIGHT", 16, y, COLORS["muted"], size=11, bold=True)
        draw_text(surface, f"{block:,}", 16, y + 16, COLORS["accent"], size=28, bold=True)

        # Status indicator
        draw_text(surface, status_text, w - 100, y + 4, status_color, size=12, bold=True)

        y += 56
        draw_hline(surface, y)
        y += 8

        # Info grid
        margin = int(w * 0.025)
        content_w = w - margin * 2
        peers = s.get("peers", 0)
        node_id = s.get("node_id", "—")
        block_hash = s.get("block_hash", "—")

        # Inline fields (short values)
        draw_text(surface, "Peers", margin, y, COLORS["muted"], size=11)
        draw_text(surface, str(peers), margin + 70, y,
                  COLORS["green"] if peers > 0 else COLORS["red"], size=12)
        draw_text(surface, "Network", int(w * 0.35), y, COLORS["muted"], size=11)
        draw_text(surface, self._get_network(), int(w * 0.35) + 70, y, COLORS["text"], size=12)
        y += 20

        # Full-width fields (label above, value below — no cropping)
        draw_text(surface, "NODE ID", margin, y, COLORS["muted"], size=10, bold=True)
        y += 14
        draw_text(surface, node_id, margin, y, COLORS["muted"], size=11, max_width=content_w)
        y += 16

        draw_text(surface, "TIP HASH", margin, y, COLORS["muted"], size=10, bold=True)
        y += 14
        draw_text(surface, block_hash, margin, y, COLORS["muted"], size=11, max_width=content_w)
        y += 16

        y += 8
        draw_hline(surface, y)
        y += 8

        # Menu label
        draw_text(surface, "MENU", 16, y, COLORS["muted"], size=11, bold=True)

        # Menu
        self.menu.area_top = y + 18
        self.menu.draw(surface)

        # Nav bar
        draw_nav_bar(surface, [("A", "Select"), ("START", "—"), ("SELECT", "Terminal")])

    def handle_input(self, event):
        # D-pad
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up":
                self.menu.move(-1)
            elif d == "down":
                self.menu.move(1)
            return True

        # Button actions via mapped names
        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.dict.get("btn", "")
            if btn == "a":
                selected = self.menu.get_selected()
                if selected and "action" in selected:
                    if selected["action"] in self.app.pages:
                        self.app.navigate(selected["action"])
                return True
            if btn == "select":
                if "terminal" in self.app.pages:
                    self.app.navigate("terminal")
                return True

        # Keyboard fallback
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.menu.move(-1)
            elif event.key == pygame.K_DOWN:
                self.menu.move(1)
            elif event.key == pygame.K_RETURN:
                selected = self.menu.get_selected()
                if selected and "action" in selected:
                    if selected["action"] in self.app.pages:
                        self.app.navigate(selected["action"])
            return True

        return False

    def _get_network(self):
        """Try to determine network from config or node info."""
        # Will be populated from settings/config later
        return getattr(self.app, "network", "testnet")
