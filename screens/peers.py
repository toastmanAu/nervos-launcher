"""
peers.py — Connected peers list + detail view
List shows peer IDs, press A to see full detail for selected peer.
"""

import pygame
from lib.ui import Page, ScrollList, COLORS, draw_text, draw_status_bar, draw_nav_bar, draw_hline


class PeersPage(Page):

    def __init__(self, app, rpc):
        super().__init__(app)
        self.rpc = rpc
        self.peer_list = ScrollList([], item_height=30, visible_area_top=44, visible_area_bottom=32)
        self.raw_peers = []
        self.refresh_timer = 0

    def on_enter(self):
        self._refresh()

    def update(self, dt):
        self.refresh_timer += dt
        if self.refresh_timer > 10000:
            self._refresh()
            self.refresh_timer = 0

    def _refresh(self):
        self.raw_peers = self.rpc.peers() or []
        items = []
        for p in self.raw_peers:
            node_id = p.get("node_id", "—")
            items.append({
                "text": node_id,  # full ID, draw() handles fitting
                "color": COLORS["text"],
            })
        self.peer_list.update_items(items)

    def draw(self, surface):
        w = surface.get_width()
        margin = int(w * 0.025)  # 2.5% margin
        content_w = w - margin * 2

        draw_status_bar(surface, "Peers", f"{len(self.raw_peers)} connected")

        if not self.peer_list.items:
            draw_text(surface, "No peers connected", margin, 60, COLORS["muted"], size=14)
        else:
            # Custom draw with full-width IDs
            y = self.peer_list.area_top
            vis = self.peer_list.visible_count
            offset = self.peer_list.scroll_offset
            items = self.peer_list.items

            for i in range(offset, min(offset + vis, len(items))):
                item = items[i]
                is_sel = (i == self.peer_list.cursor)
                item_h = self.peer_list.item_height - 2
                rect = pygame.Rect(margin, y, content_w, item_h)

                if is_sel:
                    pygame.draw.rect(surface, COLORS["surface2"], rect, border_radius=4)
                    pygame.draw.rect(surface, COLORS["accent"], rect, width=1, border_radius=4)

                draw_text(surface, item["text"], margin + 8, y + 6,
                          item.get("color", COLORS["text"]), size=12,
                          max_width=content_w - 16)

                y += self.peer_list.item_height

            # Scroll indicator
            total = len(items)
            if total > vis:
                bar_area = vis * self.peer_list.item_height
                bar_h = max(10, int((vis / total) * bar_area))
                bar_y = self.peer_list.area_top + int((offset / total) * bar_area)
                pygame.draw.rect(surface, COLORS["dim"],
                                 (w - 4, bar_y, 3, bar_h), border_radius=2)

        draw_nav_bar(surface, [("B", "Back"), ("A", "Detail"), ("D-pad", "Scroll")])

    def handle_input(self, event):
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up": self.peer_list.move(-1)
            elif d == "down": self.peer_list.move(1)
            return True

        if event.type == pygame.JOYBUTTONDOWN and event.dict.get("btn") == "a":
            idx = self.peer_list.cursor
            if 0 <= idx < len(self.raw_peers):
                if "peer_detail" in self.app.pages:
                    self.app.pages["peer_detail"].set_peer(self.raw_peers[idx])
                    self.app.navigate("peer_detail")
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: self.peer_list.move(-1)
            elif event.key == pygame.K_DOWN: self.peer_list.move(1)
            elif event.key == pygame.K_RETURN:
                idx = self.peer_list.cursor
                if 0 <= idx < len(self.raw_peers):
                    if "peer_detail" in self.app.pages:
                        self.app.pages["peer_detail"].set_peer(self.raw_peers[idx])
                        self.app.navigate("peer_detail")
            return True

        return False


class PeerDetailPage(Page):
    """Full detail view for a single peer."""

    def __init__(self, app):
        super().__init__(app)
        self.peer = {}
        self.scroll = 0
        self.lines = []

    def set_peer(self, peer_data):
        self.peer = peer_data
        self.scroll = 0
        self._build_lines()

    def _build_lines(self):
        p = self.peer
        self.lines = []

        self.lines.append(("NODE ID", COLORS["muted"], True))
        self.lines.append((p.get("node_id", "—"), COLORS["accent"], False))
        self.lines.append(("", None, False))

        version = p.get("version", "")
        if version:
            self.lines.append(("VERSION", COLORS["muted"], True))
            self.lines.append((version, COLORS["text"], False))
            self.lines.append(("", None, False))

        # Addresses
        addresses = p.get("addresses", [])
        if addresses:
            self.lines.append(("ADDRESSES", COLORS["muted"], True))
            for addr in addresses:
                a = addr if isinstance(addr, str) else addr.get("address", str(addr))
                self.lines.append((a, COLORS["text"], False))
            self.lines.append(("", None, False))

        # Connected duration
        connected = p.get("connected_duration", "")
        if connected:
            self.lines.append(("CONNECTED", COLORS["muted"], True))
            # Convert from hex ms to readable
            try:
                ms = int(connected, 16) if isinstance(connected, str) else connected
                secs = ms // 1000
                mins = secs // 60
                hrs = mins // 60
                if hrs > 0:
                    self.lines.append((f"{hrs}h {mins % 60}m", COLORS["green"], False))
                elif mins > 0:
                    self.lines.append((f"{mins}m {secs % 60}s", COLORS["green"], False))
                else:
                    self.lines.append((f"{secs}s", COLORS["green"], False))
            except:
                self.lines.append((str(connected), COLORS["text"], False))
            self.lines.append(("", None, False))

        # Protocols
        protocols = p.get("protocols", [])
        if protocols:
            self.lines.append(("PROTOCOLS", COLORS["muted"], True))
            for proto in protocols:
                if isinstance(proto, dict):
                    pid = proto.get("id", "")
                    pver = proto.get("version", "")
                    self.lines.append((f"  {pid}: {pver}", COLORS["dim"], False))
                else:
                    self.lines.append((f"  {proto}", COLORS["dim"], False))
            self.lines.append(("", None, False))

        # Is outbound
        is_out = p.get("is_outbound")
        if is_out is not None:
            self.lines.append(("DIRECTION", COLORS["muted"], True))
            self.lines.append(("Outbound" if is_out else "Inbound", COLORS["text"], False))

    @property
    def visible_lines(self):
        return (self.app.height - 32 - 28) // 18

    def draw(self, surface):
        w = surface.get_width()
        h = surface.get_height()
        margin = int(w * 0.025)
        content_w = w - margin * 2

        draw_status_bar(surface, "Peer Detail", "")

        y = 38
        vis = self.visible_lines
        total = len(self.lines)

        for i in range(self.scroll, min(self.scroll + vis, total)):
            text, color, is_label = self.lines[i]
            if not text:
                y += 6
                continue
            if is_label:
                draw_text(surface, text, margin, y, color or COLORS["muted"], size=10, bold=True)
                y += 16
            else:
                draw_text(surface, text, margin, y, color or COLORS["text"], size=13,
                          max_width=content_w)
                y += 18

        # Scroll indicator
        if total > vis:
            bar_area = vis * 18
            bar_h = max(10, int((vis / total) * bar_area))
            bar_y = 38 + int((self.scroll / max(1, total)) * bar_area)
            bar_y = min(bar_y, 38 + bar_area - bar_h)
            pygame.draw.rect(surface, COLORS["dim"], (636, bar_y, 3, bar_h), border_radius=2)

        draw_nav_bar(surface, [("B", "Back"), ("D-pad", "Scroll")])

    def handle_input(self, event):
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up": self.scroll = max(0, self.scroll - 2)
            elif d == "down": self.scroll = min(max(0, len(self.lines) - self.visible_lines), self.scroll + 2)
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: self.scroll = max(0, self.scroll - 2)
            elif event.key == pygame.K_DOWN: self.scroll = min(max(0, len(self.lines) - self.visible_lines), self.scroll + 2)
            return True

        return False
