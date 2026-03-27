"""
fileman.py — Lightweight file manager widget
Browse directories, select files/folders, create dirs.
Reusable by any screen — recorder, config editor, module installer, etc.

Usage:
    from lib.fileman import FileManagerPage

    # Register once:
    app.register_page("fileman", FileManagerPage(app))

    # Open from any screen:
    app.pages["fileman"].open(
        start_path="/userdata/",
        mode="dir",          # "dir" = select directory, "file" = select file
        title="Choose output folder",
        on_select=lambda path: set_output_dir(path),
        filter_ext=[".mp4", ".png"],  # optional file filter
    )
    app.navigate("fileman")
"""

import pygame
import os
from lib.ui import Page, ScrollList, COLORS, draw_text, draw_status_bar, draw_nav_bar, draw_box, get_font


class FileManagerPage(Page):
    """Gamepad-navigable file browser."""

    def __init__(self, app):
        super().__init__(app)
        self.current_path = "/"
        self.mode = "dir"  # "dir" or "file"
        self.title = "File Manager"
        self.on_select = None
        self.filter_ext = []
        self.entries = []
        self.menu = ScrollList([], item_height=26, visible_area_top=70, visible_area_bottom=32)
        self.message = ""
        self.message_timer = 0

    def open(self, start_path="/", mode="dir", title="File Manager",
             on_select=None, filter_ext=None):
        """Configure and open the file manager."""
        self.current_path = os.path.abspath(start_path)
        self.mode = mode
        self.title = title
        self.on_select = on_select
        self.filter_ext = filter_ext or []
        self.message = ""
        self._refresh()

    def on_enter(self):
        self._refresh()

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = ""

    def _refresh(self):
        """Scan current directory and build menu items."""
        self.entries = []
        items = []

        # Parent directory (unless at root)
        if self.current_path != "/":
            items.append({
                "text": "📁 ..",
                "subtext": "parent",
                "color": COLORS["accent"],
                "action": "parent",
                "path": os.path.dirname(self.current_path),
            })

        # If mode is "dir", add a "Select this folder" option
        if self.mode == "dir":
            items.append({
                "text": "✓ Select this folder",
                "subtext": "",
                "color": COLORS["green"],
                "action": "select_dir",
                "path": self.current_path,
            })

        try:
            raw_entries = sorted(os.listdir(self.current_path))
        except PermissionError:
            items.append({
                "text": "Permission denied",
                "color": COLORS["red"],
                "action": None,
            })
            self.menu.update_items(items)
            return

        # Directories first
        dirs = []
        files = []
        for name in raw_entries:
            if name.startswith("."):
                continue  # skip hidden
            full = os.path.join(self.current_path, name)
            try:
                if os.path.isdir(full):
                    dirs.append(name)
                elif os.path.isfile(full):
                    if self.filter_ext:
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in self.filter_ext:
                            continue
                    files.append(name)
            except:
                continue

        for d in dirs:
            full = os.path.join(self.current_path, d)
            try:
                count = len(os.listdir(full))
                sub = f"{count} items"
            except:
                sub = ""
            items.append({
                "text": f"📁 {d}",
                "subtext": sub,
                "color": COLORS["accent"],
                "action": "enter",
                "path": full,
            })

        for f in files:
            full = os.path.join(self.current_path, f)
            try:
                size = os.path.getsize(full)
                if size > 1024 * 1024:
                    sub = f"{size / (1024 * 1024):.1f}MB"
                elif size > 1024:
                    sub = f"{size / 1024:.0f}KB"
                else:
                    sub = f"{size}B"
            except:
                sub = ""

            ext = os.path.splitext(f)[1].lower()
            icon = self._file_icon(ext)
            items.append({
                "text": f"{icon} {f}",
                "subtext": sub,
                "color": COLORS["text"],
                "action": "select_file" if self.mode == "file" else "info",
                "path": full,
            })

        if not dirs and not files:
            items.append({
                "text": "(empty)",
                "color": COLORS["muted"],
                "action": None,
            })

        self.menu.update_items(items)

    def _file_icon(self, ext):
        icons = {
            ".mp4": "🎬", ".avi": "🎬", ".mkv": "🎬", ".webm": "🎬",
            ".png": "📷", ".jpg": "📷", ".jpeg": "📷", ".bmp": "📷",
            ".py": "🐍", ".sh": "⚡", ".json": "📋", ".toml": "⚙️",
            ".txt": "📄", ".md": "📄", ".log": "📄",
            ".zip": "📦", ".tar": "📦", ".gz": "📦",
        }
        return icons.get(ext, "📄")

    def draw(self, surface):
        w = surface.get_width()
        margin = int(w * 0.025)
        content_w = w - margin * 2

        draw_status_bar(surface, self.title, self.mode)

        # Current path bar
        y = 34
        path_rect = pygame.Rect(margin, y, content_w, 28)
        draw_box(surface, path_rect, fill=COLORS["surface2"], border=COLORS["border"])
        # Truncate path from the left if too long
        display_path = self.current_path
        font = get_font(11)
        while font.size(display_path)[0] > content_w - 16 and len(display_path) > 10:
            display_path = "..." + display_path[4:]
        draw_text(surface, display_path, margin + 8, y + 6, COLORS["text"], size=11)

        self.menu.draw(surface)

        if self.message:
            draw_text(surface, self.message, margin, surface.get_height() - 58,
                      COLORS["green"], size=12)

        nav = [("B", "Back"), ("A", "Open")]
        if self.mode == "dir":
            nav.append(("X", "New Folder"))
        draw_nav_bar(surface, nav)

    def handle_input(self, event):
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up": self.menu.move(-1)
            elif d == "down": self.menu.move(1)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.dict.get("btn", "")

            if btn == "a":
                selected = self.menu.get_selected()
                if not selected or not selected.get("action"):
                    return True

                action = selected["action"]
                path = selected.get("path", "")

                if action == "parent" or action == "enter":
                    self.current_path = path
                    self._refresh()
                    self.menu.cursor = 0
                    self.menu.scroll_offset = 0
                elif action == "select_dir":
                    if self.on_select:
                        self.on_select(path)
                    self.app.go_back()
                elif action == "select_file":
                    if self.on_select:
                        self.on_select(path)
                    self.app.go_back()
                elif action == "info":
                    self.message = path
                    self.message_timer = 3000
                return True

            # X = create new folder (dir mode only)
            if btn == "x" and self.mode == "dir":
                self._create_folder()
                return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: self.menu.move(-1)
            elif event.key == pygame.K_DOWN: self.menu.move(1)
            elif event.key == pygame.K_RETURN:
                selected = self.menu.get_selected()
                if selected and selected.get("action") in ("parent", "enter"):
                    self.current_path = selected["path"]
                    self._refresh()
            return True

        return False

    def _create_folder(self):
        """Create a new folder using the on-screen keyboard."""
        from lib.keyboard import OnScreenKeyboard

        if not hasattr(self, '_keyboard'):
            self._keyboard = OnScreenKeyboard()

        def on_done(name):
            if name:
                new_path = os.path.join(self.current_path, name)
                try:
                    os.makedirs(new_path, exist_ok=True)
                    self.message = f"Created: {name}"
                    self.message_timer = 2000
                    self._refresh()
                except Exception as e:
                    self.message = f"Error: {e}"
                    self.message_timer = 3000

        self._keyboard.open(
            initial_text="",
            on_done=on_done,
            title="New folder name",
        )
        # Need to draw/handle keyboard — for now use a simple approach
        # TODO: integrate keyboard overlay properly
        # For now, create with a default name
        import time
        name = f"new_{time.strftime('%H%M%S')}"
        new_path = os.path.join(self.current_path, name)
        try:
            os.makedirs(new_path, exist_ok=True)
            self.message = f"Created: {name}"
            self.message_timer = 2000
            self._refresh()
        except Exception as e:
            self.message = f"Error: {e}"
            self.message_timer = 3000
