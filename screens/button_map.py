"""
button_map.py — First-boot button mapping screen
Prompts user to press each button/direction, saves mapping to data/buttons.json.
Supports buttons, hat (d-pad), and axis (thumbstick) inputs.
Runs automatically on first launch or if config is missing.
"""

import pygame
import json
import os
from lib.ui import Page, COLORS, draw_text, draw_text_centered, draw_box, get_font


# Items to map: (internal_name, display_prompt, input_type)
# input_type: "button" = joystick button, "direction" = hat/axis/button
ITEMS_TO_MAP = [
    ("up",     "Push  UP",                "direction"),
    ("down",   "Push  DOWN",              "direction"),
    ("left",   "Push  LEFT",              "direction"),
    ("right",  "Push  RIGHT",             "direction"),
    ("a",      "Press  A  (confirm)",     "button"),
    ("b",      "Press  B  (back)",        "button"),
    ("x",      "Press  X",               "button"),
    ("y",      "Press  Y",               "button"),
    ("l1",     "Press  L1  (shoulder)",   "button"),
    ("r1",     "Press  R1  (shoulder)",   "button"),
    ("select", "Press  SELECT",           "button"),
    ("start",  "Press  START",            "button"),
]

DEFAULT_CONFIG_PATH = "data/buttons.json"

# Axis threshold for registering a direction
AXIS_THRESHOLD = 0.6


def load_button_config(install_dir):
    """Load button mapping from file. Returns dict or None if not found."""
    path = os.path.join(install_dir, DEFAULT_CONFIG_PATH)
    try:
        with open(path) as f:
            config = json.load(f)
        # Validate it has all required keys
        required = {item[0] for item in ITEMS_TO_MAP}
        if required.issubset(config.keys()):
            return config
    except:
        pass
    return None


def save_button_config(install_dir, config):
    """Save button mapping to file."""
    path = os.path.join(install_dir, DEFAULT_CONFIG_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)


class ButtonMapPage(Page):
    """Interactive button mapping screen. Steps through each input."""

    def __init__(self, app, install_dir, on_complete=None):
        super().__init__(app)
        self.install_dir = install_dir
        self.on_complete = on_complete
        self.mapping = {}
        self.step = 0
        self.cooldown = 0
        self.flash_timer = 0
        self.done = False
        self.countdown = 0

    def on_enter(self):
        self.mapping = {}
        self.step = 0
        self.done = False
        self.cooldown = 300
        self.countdown = 1500

    def update(self, dt):
        if self.cooldown > 0:
            self.cooldown -= dt
        if self.countdown > 0:
            self.countdown -= dt
        if self.flash_timer > 0:
            self.flash_timer -= dt

    def draw(self, surface):
        w = surface.get_width()
        h = surface.get_height()

        # Header
        draw_text_centered(surface, "BUTTON MAPPING", 30, COLORS["accent"], size=20, bold=True)
        draw_text_centered(surface, "Configure your controls for Nervos Launcher", 58, COLORS["muted"], size=12)

        # Progress dots
        dot_y = 90
        dot_spacing = 24
        total = len(ITEMS_TO_MAP)
        start_x = (w - (total * dot_spacing)) // 2
        for i in range(total):
            x = start_x + i * dot_spacing
            if i < self.step:
                pygame.draw.circle(surface, COLORS["green"], (x, dot_y), 5)
            elif i == self.step and not self.done:
                pulse = abs((pygame.time.get_ticks() % 1000) - 500) / 500.0
                color = (int(pulse * 200), int(200 - pulse * 50), int(255 - pulse * 55))
                pygame.draw.circle(surface, color, (x, dot_y), 7)
            else:
                pygame.draw.circle(surface, COLORS["dim"], (x, dot_y), 4)

        if self.countdown > 0:
            draw_text_centered(surface, "Get ready...", h // 2 - 20, COLORS["text"], size=18)
            return

        if self.done:
            self._draw_summary(surface)
            return

        # Current prompt
        if self.step < len(ITEMS_TO_MAP):
            name, prompt, input_type = ITEMS_TO_MAP[self.step]

            box_y = 120
            box = pygame.Rect(40, box_y, w - 80, 80)
            border = COLORS["yellow"] if input_type == "direction" else COLORS["accent"]
            draw_box(surface, box, fill=COLORS["surface2"], border=border)
            draw_text_centered(surface, prompt, box_y + 25, COLORS["text"], size=22, bold=True)

            hint = "D-pad, stick, or button" if input_type == "direction" else "Button only"
            draw_text_centered(surface, f"Step {self.step + 1}/{total}  —  {hint}", box_y + 58, COLORS["muted"], size=11)

            # Show mapped items so far
            y = 220
            draw_text(surface, "Mapped:", 40, y, COLORS["muted"], size=11)
            y += 18
            col = 0
            for mapped_name, mapping in self.mapping.items():
                cx = 40 + (col * 200)
                draw_text(surface, mapped_name.upper(), cx, y, COLORS["green"], size=11)
                draw_text(surface, self._describe_mapping(mapping), cx + 60, y, COLORS["muted"], size=11)
                col += 1
                if col >= 3:
                    col = 0
                    y += 16

            if self.flash_timer > 0:
                draw_text_centered(surface, "Got it!", h - 55, COLORS["green"], size=16, bold=True)

    def _draw_summary(self, surface):
        w = surface.get_width()
        h = surface.get_height()

        draw_text_centered(surface, "MAPPING COMPLETE", 120, COLORS["green"], size=18, bold=True)

        y = 155
        for name, mapping in self.mapping.items():
            draw_text(surface, f"  {name.upper()}", 100, y, COLORS["text"], size=13)
            draw_text(surface, f"→  {self._describe_mapping(mapping)}", 220, y, COLORS["accent"], size=13)
            y += 20

        draw_text_centered(surface, "Press any button to continue", h - 45, COLORS["muted"], size=12)

    def _describe_mapping(self, mapping):
        """Human-readable description of a mapping entry."""
        t = mapping.get("type", "")
        if t == "button":
            return f"btn {mapping['id']}"
        elif t == "hat":
            return f"hat {mapping['value']}"
        elif t == "axis":
            direction = "+" if mapping["direction"] > 0 else "-"
            return f"axis {mapping['id']}{direction}"
        return str(mapping)

    def handle_input(self, event):
        if self.countdown > 0:
            return True

        if self.cooldown > 0:
            # Absorb but don't register
            return True

        if self.done:
            # Any button after completion = save and continue
            if event.type in (pygame.JOYBUTTONDOWN, pygame.KEYDOWN):
                self._finish()
            return True

        if self.step >= len(ITEMS_TO_MAP):
            return False

        name, prompt, input_type = ITEMS_TO_MAP[self.step]

        # ── Button press ──
        if event.type == pygame.JOYBUTTONDOWN:
            mapping = {"type": "button", "id": event.button}
            if not self._is_duplicate(mapping):
                return self._register(mapping)
            return True

        # ── Hat (d-pad) motion ──
        if event.type == pygame.JOYHATMOTION and input_type == "direction":
            x, y = event.value
            if x != 0 or y != 0:
                mapping = {"type": "hat", "hat": event.hat, "value": list(event.value)}
                if not self._is_duplicate(mapping):
                    return self._register(mapping)
            return True

        # ── Axis (thumbstick) motion ──
        if event.type == pygame.JOYAXISMOTION and input_type == "direction":
            if abs(event.value) > AXIS_THRESHOLD:
                direction = 1 if event.value > 0 else -1
                mapping = {"type": "axis", "id": event.axis, "direction": direction}
                if not self._is_duplicate(mapping):
                    return self._register(mapping)
            return True

        # ── Keyboard fallback (desktop testing) ──
        if event.type == pygame.KEYDOWN:
            key_map = {
                pygame.K_UP: ("hat", [0, 1]), pygame.K_DOWN: ("hat", [0, -1]),
                pygame.K_LEFT: ("hat", [-1, 0]), pygame.K_RIGHT: ("hat", [1, 0]),
                pygame.K_z: ("button", 0), pygame.K_x: ("button", 1),
                pygame.K_a: ("button", 2), pygame.K_s: ("button", 3),
                pygame.K_q: ("button", 4), pygame.K_w: ("button", 5),
                pygame.K_TAB: ("button", 6), pygame.K_RETURN: ("button", 7),
            }
            if event.key in key_map:
                t, val = key_map[event.key]
                if t == "hat":
                    mapping = {"type": "hat", "hat": 0, "value": val}
                else:
                    mapping = {"type": "button", "id": val}
                return self._register(mapping)

        return False

    def _is_duplicate(self, mapping):
        """Check if this exact mapping is already assigned."""
        for existing in self.mapping.values():
            if existing == mapping:
                return True
        return False

    def _register(self, mapping):
        name = ITEMS_TO_MAP[self.step][0]
        self.mapping[name] = mapping
        self.step += 1
        self.cooldown = 300
        self.flash_timer = 400

        if self.step >= len(ITEMS_TO_MAP):
            self.done = True
            self.cooldown = 500

        return True

    def _finish(self):
        save_button_config(self.install_dir, self.mapping)
        self.app.button_map = self.mapping
        if self.on_complete:
            self.on_complete(self.mapping)
        else:
            self.app.go_home()
