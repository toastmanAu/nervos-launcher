"""
recorder.py — Framebuffer screen recorder for handhelds
Uses ffmpeg to capture /dev/fb0. Runs as a fully detached process
that survives app exit/restart. Controlled via PID file.

Usage:
    from lib.recorder import ScreenRecorder
    rec = ScreenRecorder()
    rec.start()      # begins recording (detached from app)
    rec.stop()       # stops and saves
    rec.screenshot() # single frame capture
"""

import subprocess
import os
import time
import signal


class ScreenRecorder:
    """Framebuffer screen recorder using ffmpeg as a detached process."""

    def __init__(self, output_dir="/userdata/ckb-light-client/recordings"):
        self.output_dir = output_dir
        self.fps = 30
        self.quality = "medium"  # "low", "medium", "high"

        # State file — persists across app restarts
        self._pid_file = os.path.join(output_dir, ".rec.pid")
        self._file_file = os.path.join(output_dir, ".rec.file")
        self._start_file = os.path.join(output_dir, ".rec.start")

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
                raw_height = int(dims[1])
                # Some devices report double height for double buffering
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
        if self.fb_bpp == 32:
            return "bgra"
        elif self.fb_bpp == 16:
            return "rgb565le"
        return "bgra"

    @property
    def _crf(self):
        return {"low": 35, "medium": 28, "high": 20}.get(self.quality, 28)

    @property
    def _preset(self):
        return {"low": "ultrafast", "medium": "veryfast", "high": "fast"}.get(self.quality, "veryfast")

    @property
    def recording(self):
        """Check if ffmpeg is actually running (survives app restart)."""
        pid = self._read_pid()
        if pid:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                # Stale PID, clean up
                self._cleanup_state()
        return False

    @property
    def current_file(self):
        try:
            with open(self._file_file) as f:
                return f.read().strip()
        except:
            return ""

    @property
    def record_seconds(self):
        """How long the current recording has been running."""
        try:
            with open(self._start_file) as f:
                start = float(f.read().strip())
            return time.time() - start
        except:
            return 0

    def _read_pid(self):
        try:
            with open(self._pid_file) as f:
                return int(f.read().strip())
        except:
            return None

    def _cleanup_state(self):
        for f in [self._pid_file, self._file_file, self._start_file]:
            try:
                os.remove(f)
            except:
                pass

    def start(self):
        """Start recording. ffmpeg runs fully detached — survives app exit."""
        if self.recording:
            return False

        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        outfile = os.path.join(self.output_dir, f"rec_{timestamp}.mp4")

        # Build ffmpeg command
        cmd = (
            f'nohup setsid ffmpeg -y '
            f'-f rawvideo -pixel_format {self._pixel_format} '
            f'-video_size {self.fb_width}x{self.fb_height} '
            f'-framerate {self.fps} '
            f'-i {self.fb_device} '
            f'-c:v libx264 -preset {self._preset} -crf {self._crf} '
            f'-pix_fmt yuv420p -movflags +faststart '
            f'"{outfile}" '
            f'> /dev/null 2>&1 &'
        )

        try:
            # Launch via shell so nohup/setsid work properly
            subprocess.run(cmd, shell=True, timeout=5)

            # Give it a moment to start
            time.sleep(0.5)

            # Find the ffmpeg PID
            result = subprocess.run(
                ["pgrep", "-f", f"ffmpeg.*{outfile}"],
                capture_output=True, text=True, timeout=3)
            pid = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""

            if not pid:
                # Fallback: find any ffmpeg recording to our output dir
                result = subprocess.run(
                    ["pgrep", "-f", "ffmpeg.*rawvideo"],
                    capture_output=True, text=True, timeout=3)
                pid = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""

            if pid:
                with open(self._pid_file, "w") as f:
                    f.write(pid)
                with open(self._file_file, "w") as f:
                    f.write(outfile)
                with open(self._start_file, "w") as f:
                    f.write(str(time.time()))
                return True
            else:
                return False

        except Exception:
            return False

    def stop(self):
        """Stop recording and finalize the file."""
        pid = self._read_pid()
        saved = self.current_file

        if not pid:
            self._cleanup_state()
            return None

        try:
            # Send SIGINT for graceful ffmpeg shutdown (writes moov atom)
            os.kill(pid, signal.SIGINT)
            # Wait for it to finish writing
            for _ in range(50):  # up to 5 seconds
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break  # process exited
            else:
                # Force kill if still running
                try:
                    os.kill(pid, signal.SIGKILL)
                except:
                    pass
        except OSError:
            pass  # already dead

        self._cleanup_state()

        # Verify file
        if saved and os.path.exists(saved) and os.path.getsize(saved) > 1024:
            return saved
        return None

    def screenshot(self, filename=None):
        """Capture a single frame from the framebuffer."""
        os.makedirs(self.output_dir, exist_ok=True)

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.output_dir, f"shot_{timestamp}.png")

        # Try fbgrab first
        try:
            result = subprocess.run(["fbgrab", filename], capture_output=True, timeout=5)
            if result.returncode == 0 and os.path.exists(filename):
                return filename
        except:
            pass

        # Fallback: ffmpeg single frame
        try:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "rawvideo", "-pixel_format", self._pixel_format,
                "-video_size", f"{self.fb_width}x{self.fb_height}",
                "-framerate", "1", "-i", self.fb_device,
                "-frames:v", "1", filename,
            ], capture_output=True, timeout=5)
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
            if f.startswith("."):
                continue  # skip state files
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
