"""
ui.py — Core UI framework for Nervos Launcher
Provides theme, text rendering, menus, scrollable lists, and page management.
Designed for 640x480 handheld displays with gamepad input.
"""

import pygame

# ── Theme ────────────────────────────────────────────────────
COLORS = {
    "bg":       (10, 12, 15),
    "surface":  (17, 19, 26),
    "surface2": (24, 28, 35),
    "border":   (30, 36, 48),
    "accent":   (0, 200, 255),
    "green":    (0, 229, 160),
    "yellow":   (251, 191, 36),
    "red":      (248, 113, 113),
    "text":     (226, 232, 240),
    "muted":    (100, 116, 139),
    "dim":      (55, 65, 81),
}

# ── Font cache ───────────────────────────────────────────────
_font_cache = {}

def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        try:
            path = "/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSansMono.ttf"
            _font_cache[key] = pygame.font.Font(path, size)
        except:
            _font_cache[key] = pygame.font.SysFont("monospace", size, bold=bold)
    return _font_cache[key]


# ── Text drawing helpers ─────────────────────────────────────
def draw_text(surface, text, x, y, color=None, size=14, bold=False, max_width=None):
    """Draw text, optionally truncating with ellipsis if max_width set."""
    color = color or COLORS["text"]
    font = get_font(size, bold)
    if max_width:
        while font.size(text)[0] > max_width and len(text) > 3:
            text = text[:-4] + "..."
    rendered = font.render(text, True, color)
    surface.blit(rendered, (x, y))
    return rendered.get_rect(topleft=(x, y))


def draw_text_centered(surface, text, y, color=None, size=14, bold=False):
    color = color or COLORS["text"]
    font = get_font(size, bold)
    rendered = font.render(text, True, color)
    x = (surface.get_width() - rendered.get_width()) // 2
    surface.blit(rendered, (x, y))


# ── Box / Panel drawing ─────────────────────────────────────
def draw_box(surface, rect, fill=None, border=None, radius=6):
    fill = fill or COLORS["surface"]
    border = border or COLORS["border"]
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, width=1, border_radius=radius)


def draw_hline(surface, y, color=None, margin=16):
    color = color or COLORS["border"]
    pygame.draw.line(surface, color, (margin, y), (surface.get_width() - margin, y))


# ── Status bar (top) ─────────────────────────────────────────
def draw_status_bar(surface, title, right_text=""):
    bar = pygame.Rect(0, 0, surface.get_width(), 32)
    pygame.draw.rect(surface, COLORS["surface"], bar)
    pygame.draw.line(surface, COLORS["border"], (0, 31), (surface.get_width(), 31))
    draw_text(surface, title, 12, 7, COLORS["accent"], size=14, bold=True)
    if right_text:
        font = get_font(12)
        w = font.size(right_text)[0]
        draw_text(surface, right_text, surface.get_width() - w - 12, 9, COLORS["muted"], size=12)


# ── Nav bar (bottom) ─────────────────────────────────────────
def draw_nav_bar(surface, items):
    """items: list of (button_label, action_label) tuples"""
    bar_y = surface.get_height() - 28
    pygame.draw.rect(surface, COLORS["surface"], (0, bar_y, surface.get_width(), 28))
    pygame.draw.line(surface, COLORS["border"], (0, bar_y), (surface.get_width(), bar_y))
    x = 12
    for btn, label in items:
        draw_text(surface, btn, x, bar_y + 6, COLORS["accent"], size=11, bold=True)
        x += get_font(11, True).size(btn)[0] + 4
        draw_text(surface, label, x, bar_y + 6, COLORS["muted"], size=11)
        x += get_font(11).size(label)[0] + 16


# ── Scrollable list ──────────────────────────────────────────
class ScrollList:
    """A paginated, scrollable list with cursor selection."""

    def __init__(self, items, item_height=28, visible_area_top=36, visible_area_bottom=56):
        self.items = items  # list of dicts: {text, subtext?, color?, action?}
        self.item_height = item_height
        self.cursor = 0
        self.scroll_offset = 0
        self.area_top = visible_area_top
        self.area_bottom = visible_area_bottom

    @property
    def visible_count(self):
        return (480 - self.area_top - self.area_bottom) // self.item_height

    def move(self, delta):
        if not self.items:
            return
        self.cursor = max(0, min(len(self.items) - 1, self.cursor + delta))
        # Keep cursor in visible window
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + self.visible_count:
            self.scroll_offset = self.cursor - self.visible_count + 1

    def get_selected(self):
        if self.items and 0 <= self.cursor < len(self.items):
            return self.items[self.cursor]
        return None

    def update_items(self, items):
        self.items = items
        self.cursor = min(self.cursor, max(0, len(items) - 1))
        self.scroll_offset = min(self.scroll_offset, max(0, len(items) - self.visible_count))

    def draw(self, surface):
        w = surface.get_width()
        margin = int(w * 0.025)  # 2.5% side margin
        content_w = w - margin * 2

        y = self.area_top
        vis = self.visible_count
        for i in range(self.scroll_offset, min(self.scroll_offset + vis, len(self.items))):
            item = self.items[i]
            rect = pygame.Rect(margin, y, content_w, self.item_height - 2)
            is_selected = (i == self.cursor)

            if is_selected:
                pygame.draw.rect(surface, COLORS["surface2"], rect, border_radius=4)
                pygame.draw.rect(surface, COLORS["accent"], rect, width=1, border_radius=4)

            text_x = margin + int(content_w * 0.02)
            color = item.get("color", COLORS["text"])

            if "subtext" in item and item["subtext"]:
                # Text on left, subtext on right — split at 70/30
                text_w = int(content_w * 0.68)
                draw_text(surface, item["text"], text_x, y + 4, color, size=13,
                          max_width=text_w)
                st_font = get_font(11)
                st_w = st_font.size(item["subtext"])[0]
                draw_text(surface, item["subtext"],
                          margin + content_w - st_w - int(content_w * 0.02), y + 6,
                          item.get("subcolor", COLORS["muted"]), size=11)
            else:
                # Full width text
                draw_text(surface, item["text"], text_x, y + 4, color, size=13,
                          max_width=content_w - int(content_w * 0.04))

            y += self.item_height

        # Scroll indicator
        if len(self.items) > vis:
            total = len(self.items)
            bar_h = max(20, int((vis / total) * (vis * self.item_height)))
            bar_y = self.area_top + int((self.scroll_offset / total) * (vis * self.item_height))
            pygame.draw.rect(surface, COLORS["dim"],
                             (surface.get_width() - 4, bar_y, 3, bar_h), border_radius=2)


# ── Page base class ──────────────────────────────────────────
class Page:
    """Base class for all screens. Subclass and override update/draw/handle_input."""

    def __init__(self, app):
        self.app = app  # reference to main App for navigation

    def on_enter(self):
        """Called when this page becomes active."""
        pass

    def on_exit(self):
        """Called when leaving this page."""
        pass

    def update(self, dt):
        """Called every frame. dt = milliseconds since last frame."""
        pass

    def draw(self, surface):
        """Draw this page to the surface."""
        pass

    def handle_input(self, event):
        """Handle a pygame event. Return True if consumed."""
        return False


# ── App (page manager) ───────────────────────────────────────
class App:
    """Main application — manages pages, input, and the game loop."""

    def __init__(self, width=640, height=480, fps=30):
        pygame.init()
        pygame.mouse.set_visible(False)

        # Try fullscreen on framebuffer, fall back to windowed
        try:
            self.screen = pygame.display.set_mode((width, height), pygame.FULLSCREEN)
        except:
            self.screen = pygame.display.set_mode((width, height))

        pygame.display.set_caption("Nervos Launcher")
        self.clock = pygame.time.Clock()
        self.fps = fps
        self.running = True
        self.width = width
        self.height = height

        # Page management
        self.pages = {}       # name -> Page instance
        self.page_stack = []  # navigation stack
        self.current_page = None

        # Joystick
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
        else:
            self.joystick = None

        # Button mapping (loaded from data/buttons.json after first-boot config)
        self.button_map = {}  # name -> button_id, e.g. {"a": 0, "b": 1, ...}
        self._held_buttons = set()  # track currently held buttons for combos

        # D-pad repeat
        self._dpad_held = {}
        self._dpad_repeat_delay = 400  # ms before first repeat
        self._dpad_repeat_rate = 120   # ms between repeats

    def register_page(self, name, page):
        self.pages[name] = page

    def navigate(self, name):
        """Push current page and navigate to a new one."""
        if self.current_page:
            self.current_page.on_exit()
            self.page_stack.append(self.current_page)
        self.current_page = self.pages[name]
        self.current_page.on_enter()

    def go_back(self):
        """Pop the page stack."""
        if self.page_stack:
            if self.current_page:
                self.current_page.on_exit()
            self.current_page = self.page_stack.pop()
            self.current_page.on_enter()

    def go_home(self):
        """Clear stack and go to first registered page."""
        if self.current_page:
            self.current_page.on_exit()
        self.page_stack.clear()
        first = list(self.pages.keys())[0]
        self.current_page = self.pages[first]
        self.current_page.on_enter()

    def run(self):
        while self.running:
            dt = self.clock.tick(self.fps)
            now = pygame.time.get_ticks()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break

                # Track held buttons for combo detection
                if event.type == pygame.JOYBUTTONDOWN:
                    self._held_buttons.add(event.button)
                elif event.type == pygame.JOYBUTTONUP:
                    self._held_buttons.discard(event.button)

                # Check Select+Start exit combo
                select_map = self.button_map.get("select", {})
                start_map = self.button_map.get("start", {})
                if select_map.get("type") == "button" and start_map.get("type") == "button":
                    if {select_map["id"], start_map["id"]}.issubset(self._held_buttons):
                        self.running = False
                        break

                # ── Resolve mapped directions from any input type ──
                active_dirs = set()

                if event.type == pygame.JOYHATMOTION:
                    x, y = event.value
                    # Check which mapped directions match this hat
                    for dname in ("up", "down", "left", "right"):
                        m = self.button_map.get(dname, {})
                        if m.get("type") == "hat" and m.get("value") == list(event.value):
                            active_dirs.add(dname)

                if event.type == pygame.JOYAXISMOTION:
                    for dname in ("up", "down", "left", "right"):
                        m = self.button_map.get(dname, {})
                        if m.get("type") == "axis" and m.get("id") == event.axis:
                            if m["direction"] > 0 and event.value > 0.5:
                                active_dirs.add(dname)
                            elif m["direction"] < 0 and event.value < -0.5:
                                active_dirs.add(dname)

                # Also check if a button is mapped as a direction
                if event.type == pygame.JOYBUTTONDOWN:
                    for dname in ("up", "down", "left", "right"):
                        m = self.button_map.get(dname, {})
                        if m.get("type") == "button" and m.get("id") == event.button:
                            active_dirs.add(dname)

                # Fire d-pad events for newly active directions
                for d in active_dirs:
                    if d not in self._dpad_held:
                        self._dpad_held[d] = {"next_fire": now + self._dpad_repeat_delay}
                        self._fire_dpad(d)

                # Clear released directions on hat neutral
                if event.type == pygame.JOYHATMOTION and event.value == (0, 0):
                    for d in list(self._dpad_held.keys()):
                        m = self.button_map.get(d, {})
                        if m.get("type") == "hat":
                            self._dpad_held.pop(d, None)

                # Clear released directions on axis return to center
                if event.type == pygame.JOYAXISMOTION and abs(event.value) < 0.3:
                    for d in list(self._dpad_held.keys()):
                        m = self.button_map.get(d, {})
                        if m.get("type") == "axis" and m.get("id") == event.axis:
                            self._dpad_held.pop(d, None)

                # Clear released button-as-direction
                if event.type == pygame.JOYBUTTONUP:
                    for d in list(self._dpad_held.keys()):
                        m = self.button_map.get(d, {})
                        if m.get("type") == "button" and m.get("id") == event.button:
                            self._dpad_held.pop(d, None)

                # ── Forward raw hat/axis events to current page ──
                # (needed for button mapping screen to capture d-pad/stick)
                if event.type in (pygame.JOYHATMOTION, pygame.JOYAXISMOTION):
                    if self.current_page:
                        self.current_page.handle_input(event)

                # ── Button handling via configurable map ──
                if event.type == pygame.JOYBUTTONDOWN:
                    btn_name = self.get_button_name(event.button)
                    if btn_name == "b":
                        self.go_back()
                    elif btn_name == "start":
                        self.go_home()
                    elif self.current_page:
                        event.dict["btn"] = btn_name
                        self.current_page.handle_input(event)

                # Keyboard fallback (for testing on desktop)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.go_back()
                    elif self.current_page:
                        self.current_page.handle_input(event)

            # D-pad repeat
            for d, state in list(self._dpad_held.items()):
                if now >= state["next_fire"]:
                    self._fire_dpad(d)
                    state["next_fire"] = now + self._dpad_repeat_rate

            # Update + draw
            if self.current_page:
                self.current_page.update(dt)
                self.screen.fill(COLORS["bg"])
                self.current_page.draw(self.screen)

            pygame.display.flip()

        pygame.quit()

    def get_button_name(self, button_id):
        """Resolve a pygame button ID to our internal name using the button map."""
        for name, mapping in self.button_map.items():
            if isinstance(mapping, dict):
                if mapping.get("type") == "button" and mapping.get("id") == button_id:
                    return name
            elif mapping == button_id:
                # Legacy format (plain int)
                return name
        return None

    def _active_dpad_dirs(self, x, y):
        dirs = []
        if y > 0: dirs.append("up")
        if y < 0: dirs.append("down")
        if x < 0: dirs.append("left")
        if x > 0: dirs.append("right")
        return dirs

    def _fire_dpad(self, direction):
        if self.current_page:
            # Create a synthetic event
            evt = pygame.event.Event(pygame.USEREVENT, {"dpad": direction})
            self.current_page.handle_input(evt)
