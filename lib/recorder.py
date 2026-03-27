"""
recorder.py — Framebuffer screen recorder for handhelds
Uses ffmpeg to capture /dev/fb0 at configurable fps/quality.
Runs as a background process, triggered from any module.

Usage:
    from lib.recorder import ScreenRecorder
    rec = ScreenRecorder()
    rec.start()      # begins recording
    rec.stop()       # stops and saves
    rec.screenshot() # single frame capture
"""

import subprocess
import os
import time
import threading
import signal


class ScreenRecorder:
    """Framebuffer screen recorder using ffmpeg."""

    def __init__(self, output_dir="/userdata/ckb-light-client/recordings",
                 fps=30, quality="medium"):
        self.output_dir = output_dir
        self.fps = fps
        self.quality = quality  # "low", "medium", "high"
        self.process = None
        self.recording = False
        self.current_file = ""
        self._lock = threading.Lock()

        # Detect framebuffer
        self.fb_device = "/dev/fb0"
        self.fb_width = 640
        self.fb_height = 480
        self.fb_bpp = 32
        self._detect_framebuffer()

    def _detect_framebuffer(self):
        """Read framebuffer dimensions from sysfs."""
        try:
            with open("/sys/class/graphics/fb0/virtual_size") as f:
                dims = f.read().strip().split(",")
                self.fb_width = int(dims[0])
                # Some devices report double height for double buffering
                raw_height = int(dims[1])
                if raw_height > self.fb_width * 2:
                    self.fb_height = raw_height // 2
                else:
                    self.fb_height = raw_height
            with open("/sys/class/graphics/fb0/bits_per_pixel") as f:
                self.fb_bpp = int(f.read().strip())
        except:
            pass

    @property
    def _pixel_format(self):
        """ffmpeg pixel format for this framebuffer."""
        if self.fb_bpp == 32:
            return "bgra"
        elif self.fb_bpp == 16:
            return "rgb565le"
        return "bgra"

    @property
    def _crf(self):
        """ffmpeg CRF value for quality setting."""
        return {"low": 35, "medium": 28, "high": 20}.get(self.quality, 28)

    @property
    def _preset(self):
        """ffmpeg preset for encoding speed."""
        return {"low": "ultrafast", "medium": "veryfast", "high": "fast"}.get(self.quality, "veryfast")

    def start(self):
        """Start recording the framebuffer."""
        with self._lock:
            if self.recording:
                return False

            os.makedirs(self.output_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.current_file = os.path.join(self.output_dir, f"rec_{timestamp}.mp4")

            cmd = [
                "ffmpeg",
                "-y",                           # overwrite
                "-f", "rawvideo",                # raw framebuffer input
                "-pixel_format", self._pixel_format,
                "-video_size", f"{self.fb_width}x{self.fb_height}",
                "-framerate", str(self.fps),
                "-i", self.fb_device,            # read from framebuffer
                "-c:v", "libx264",               # h264 encode
                "-preset", self._preset,
                "-crf", str(self._crf),
                "-pix_fmt", "yuv420p",           # compatible output
                "-movflags", "+faststart",        # web-friendly
                self.current_file,
            ]

            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                )
                self.recording = True
                return True
            except Exception as e:
                self.recording = False
                return False

    def stop(self):
        """Stop recording and finalize the file."""
        with self._lock:
            if not self.recording or not self.process:
                return None

            try:
                # Send 'q' to ffmpeg for graceful stop
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
                self.process.wait(timeout=10)
            except:
                try:
                    self.process.send_signal(signal.SIGINT)
                    self.process.wait(timeout=5)
                except:
                    self.process.kill()

            self.recording = False
            saved = self.current_file
            self.process = None

            # Verify file exists and has content
            if os.path.exists(saved) and os.path.getsize(saved) > 1024:
                return saved
            return None

    def screenshot(self, filename=None):
        """Capture a single frame from the framebuffer."""
        os.makedirs(self.output_dir, exist_ok=True)

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"shot_{timestamp}.png")

        # Try fbgrab first (simpler)
        try:
            result = subprocess.run(
                ["fbgrab", filename],
                capture_output=True, timeout=5)
            if result.returncode == 0 and os.path.exists(filename):
                return filename
        except:
            pass

        # Fallback: ffmpeg single frame
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "rawvideo",
                "-pixel_format", self._pixel_format,
                "-video_size", f"{self.fb_width}x{self.fb_height}",
                "-framerate", "1",
                "-i", self.fb_device,
                "-frames:v", "1",
                filename,
            ]
            subprocess.run(cmd, capture_output=True, timeout=5)
            if os.path.exists(filename):
                return filename
        except:
            pass

        return None

    def list_recordings(self):
        """List all recordings and screenshots."""
        if not os.path.exists(self.output_dir):
            return []
        files = []
        for f in sorted(os.listdir(self.output_dir), reverse=True):
            path = os.path.join(self.output_dir, f)
            if os.path.isfile(path):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                files.append({
                    "name": f,
                    "path": path,
                    "size": f"{size_mb:.1f}MB",
                    "type": "video" if f.endswith(".mp4") else "image",
                })
        return files

    def delete(self, path):
        """Delete a recording or screenshot."""
        if os.path.exists(path) and path.startswith(self.output_dir):
            os.remove(path)
            return True
        return False
