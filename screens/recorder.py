"""
recorder.py — Screen recorder control screen
Start/stop recording, take screenshots, manage saved files.
Recording continues in background even when navigating other screens.
"""

import pygame
import os
from lib.ui import Page, ScrollList, COLORS, draw_text, draw_status_bar, draw_nav_bar, draw_box, get_font
from lib.recorder import ScreenRecorder


class RecorderPage(Page):

    def __init__(self, app, install_dir="/userdata/ckb-light-client"):
        super().__init__(app)
        self.recorder = ScreenRecorder(
            output_dir=os.path.join(install_dir, "recordings")
        )
        self.menu = ScrollList([], item_height=30, visible_area_top=100, visible_area_bottom=32)
        self.message = ""
        self.message_timer = 0
        self.confirm_delete = None  # path pending deletion confirmation

    def on_enter(self):
        self._rebuild_menu()

    def update(self, dt):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = ""

    def _rebuild_menu(self):
        items = []

        if self.recorder.recording:
            items.append({
                "text": "Stop Recording",
                "subtext": f"{self.recorder.record_seconds:.0f}s",
                "subcolor": COLORS["red"],
                "action": "stop",
            })
        else:
            if self.recorder.ffmpeg_available:
                encoder, _ = self.recorder._detect_encoder()
                items.append({
                    "text": "Start Recording",
                    "subtext": f"{self.recorder.fps}fps {encoder}",
                    "subcolor": COLORS["green"],
                    "action": "start",
                })
            else:
                items.append({
                    "text": "Install ffmpeg first",
                    "subtext": "Settings > Install",
                    "subcolor": COLORS["red"],
                    "action": None,
                })

        items.append({
            "text": "Screenshot",
            "subtext": "fbgrab (no ffmpeg needed)",
            "action": "screenshot",
        })

        items.append({"text": "", "subtext": "", "action": None})

        # Encoder info
        items.append({
            "text": "Encoder",
            "subtext": self.recorder.ffmpeg_info,
            "subcolor": COLORS["muted"],
            "action": None,
        })

        # Quality settings
        items.append({
            "text": "Quality",
            "subtext": self.recorder.quality,
            "subcolor": COLORS["accent"],
            "action": "cycle_quality",
        })
        items.append({
            "text": "FPS",
            "subtext": str(self.recorder.fps),
            "subcolor": COLORS["accent"],
            "action": "cycle_fps",
        })
        # Audio toggle
        if self.recorder.audio_available:
            items.append({
                "text": "Audio",
                "subtext": "ON" if self.recorder.record_audio else "OFF",
                "subcolor": COLORS["green"] if self.recorder.record_audio else COLORS["red"],
                "action": "toggle_audio",
            })
        else:
            items.append({
                "text": "Audio",
                "subtext": "not available",
                "subcolor": COLORS["muted"],
                "action": None,
            })

        items.append({
            "text": "Resolution",
            "subtext": f"{self.recorder.fb_width}x{self.recorder.fb_height}",
            "subcolor": COLORS["muted"],
            "action": None,
        })
        items.append({
            "text": "Output Path",
            "subtext": self.recorder.output_dir.replace("/userdata/ckb-light-client/", ""),
            "subcolor": COLORS["accent"],
            "action": "change_output",
        })

        items.append({"text": "", "subtext": "", "action": None})

        # Saved recordings
        recordings = self.recorder.list_recordings()
        if recordings:
            for rec in recordings[:10]:
                icon = "🎬" if rec["type"] == "video" else "📷"
                items.append({
                    "text": f"{icon} {rec['name']}",
                    "subtext": rec["size"],
                    "action": "view_file",
                    "path": rec["path"],
                    "file_type": rec["type"],
                })
        else:
            items.append({
                "text": "No recordings yet",
                "subtext": "",
                "color": COLORS["muted"],
                "action": None,
            })

        self.menu.update_items(items)

    def _set_message(self, text, color=None, duration=2000):
        self.message = text
        self.message_timer = duration

    def draw(self, surface):
        w = surface.get_width()
        margin = int(w * 0.025)

        draw_status_bar(surface, "Recorder",
                        "● REC" if self.recorder.recording else "")

        # Recording status panel
        y = 38
        panel = pygame.Rect(margin, y, w - margin * 2, 52)
        if self.recorder.recording:
            # Pulsing red border
            pulse = abs((pygame.time.get_ticks() % 1000) - 500) / 500.0
            border = (int(248 * pulse), int(50 * pulse), int(50 * pulse))
            draw_box(surface, panel, fill=COLORS["surface"], border=border)
            pygame.draw.circle(surface, COLORS["red"], (margin + 18, y + 16), 6)
            draw_text(surface, "RECORDING", margin + 30, y + 8, COLORS["red"], size=14, bold=True)
            mins = int(self.recorder.record_seconds // 60)
            secs = int(self.recorder.record_seconds % 60)
            draw_text(surface, f"{mins:02d}:{secs:02d}", margin + 30, y + 28, COLORS["text"], size=12)
            # File size estimate
            draw_text(surface, self.recorder.current_file.split("/")[-1],
                      w // 2, y + 18, COLORS["muted"], size=10,
                      max_width=w // 2 - margin)
        else:
            draw_box(surface, panel, fill=COLORS["surface"], border=COLORS["border"])
            draw_text(surface, "Ready to record", margin + 12, y + 8, COLORS["muted"], size=14)
            fb_info = f"Framebuffer: {self.recorder.fb_width}x{self.recorder.fb_height} {self.recorder.fb_bpp}bpp"
            draw_text(surface, fb_info, margin + 12, y + 28, COLORS["dim"], size=10)

        self.menu.draw(surface)

        # Confirm delete overlay
        if self.confirm_delete:
            overlay_y = surface.get_height() // 2 - 30
            overlay = pygame.Rect(int(w * 0.1), overlay_y, int(w * 0.8), 60)
            draw_box(surface, overlay, fill=COLORS["surface"], border=COLORS["red"])
            draw_text(surface, "Delete this file?", int(w * 0.15), overlay_y + 8,
                      COLORS["red"], size=14, bold=True)
            fname = os.path.basename(self.confirm_delete)
            draw_text(surface, fname, int(w * 0.15), overlay_y + 28,
                      COLORS["muted"], size=11, max_width=int(w * 0.6))
            draw_nav_bar(surface, [("A", "Yes, delete"), ("B", "Cancel")])
            return

        if self.message:
            draw_text(surface, self.message, margin, surface.get_height() - 58,
                      COLORS["green"], size=12)

        # Dynamic nav bar based on selected item
        selected = self.menu.get_selected()
        action = selected.get("action", "") if selected else ""

        if action == "start":
            draw_nav_bar(surface, [("B", "Back"), ("A", "Start Recording"), ("D-pad", "Scroll")])
        elif action == "stop":
            draw_nav_bar(surface, [("B", "Back"), ("A", "Stop Recording")])
        elif action == "screenshot":
            draw_nav_bar(surface, [("B", "Back"), ("A", "Take Screenshot")])
        elif action == "view_file":
            draw_nav_bar(surface, [("B", "Back"), ("A", "Info"), ("Y", "Delete"), ("D-pad", "Scroll")])
        elif action in ("cycle_quality", "cycle_fps"):
            draw_nav_bar(surface, [("B", "Back"), ("A", "Change"), ("D-pad", "Scroll")])
        elif action == "change_output":
            draw_nav_bar(surface, [("B", "Back"), ("A", "Browse"), ("D-pad", "Scroll")])
        else:
            draw_nav_bar(surface, [("B", "Back"), ("A", "Select"), ("D-pad", "Scroll")])

    def handle_input(self, event):
        # ── Confirm delete dialog ────────────────────────────
        if self.confirm_delete:
            if event.type == pygame.JOYBUTTONDOWN:
                btn = event.dict.get("btn", "")
                if btn == "a":
                    # Confirmed
                    if self.recorder.delete(self.confirm_delete):
                        self._set_message("Deleted")
                    self.confirm_delete = None
                    self._rebuild_menu()
                    return True
                elif btn == "b":
                    # Cancelled
                    self.confirm_delete = None
                    return True
            return True  # absorb all input while dialog shown

        # ── D-pad scroll ─────────────────────────────────────
        if event.type == pygame.USEREVENT:
            d = event.dict.get("dpad", "")
            if d == "up": self.menu.move(-1)
            elif d == "down": self.menu.move(1)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.dict.get("btn", "")
            selected = self.menu.get_selected()
            action = selected.get("action", "") if selected else ""

            # ── A button: primary action ─────────────────────
            if btn == "a":
                if action == "start":
                    if self.recorder.start():
                        self._set_message("Recording started")
                    else:
                        self._set_message("Failed to start recording")
                    self._rebuild_menu()

                elif action == "stop":
                    saved = self.recorder.stop()
                    if saved:
                        size = os.path.getsize(saved) / (1024 * 1024)
                        self._set_message(f"Saved: {size:.1f}MB")
                    else:
                        self._set_message("Recording failed")
                    self._rebuild_menu()

                elif action == "screenshot":
                    path = self.recorder.screenshot()
                    if path:
                        self._set_message("Screenshot saved")
                    else:
                        self._set_message("Screenshot failed")
                    self._rebuild_menu()

                elif action == "cycle_quality":
                    qualities = ["low", "medium", "high"]
                    idx = qualities.index(self.recorder.quality) if self.recorder.quality in qualities else 0
                    self.recorder.quality = qualities[(idx + 1) % len(qualities)]
                    self._rebuild_menu()

                elif action == "toggle_audio":
                    self.recorder.record_audio = not self.recorder.record_audio
                    self._rebuild_menu()

                elif action == "cycle_fps":
                    fps_opts = [15, 24, 30, 60]
                    idx = fps_opts.index(self.recorder.fps) if self.recorder.fps in fps_opts else 2
                    self.recorder.fps = fps_opts[(idx + 1) % len(fps_opts)]
                    self._rebuild_menu()

                elif action == "change_output":
                    if "fileman" in self.app.pages:
                        def on_dir_selected(path):
                            self.recorder.output_dir = path
                            self._set_message(f"Output: {path}")
                            self._rebuild_menu()
                        self.app.pages["fileman"].open(
                            start_path=self.recorder.output_dir,
                            mode="dir",
                            title="Recording Output",
                            on_select=on_dir_selected,
                        )
                        self.app.navigate("fileman")

                elif action == "view_file":
                    path = selected.get("path", "")
                    self._set_message(path)

                return True

            # ── Y button: delete (files only) ────────────────
            if btn == "y" and action == "view_file":
                path = selected.get("path", "")
                if path:
                    self.confirm_delete = path
                return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: self.menu.move(-1)
            elif event.key == pygame.K_DOWN: self.menu.move(1)
            return True

        return False
