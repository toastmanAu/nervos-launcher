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

# Preferred ffmpeg paths — our installed copy first, then system
FFMPEG_PATHS = [
    "/userdata/ckb-light-client/packages/bin/ffmpeg",  # our package manager install
    os.path.expanduser("~/ckb-light-client/packages/bin/ffmpeg"),
    "/usr/bin/ffmpeg",
    "/usr/local/bin/ffmpeg",
    "ffmpeg",  # PATH fallback
]


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

    def _find_ffmpeg(self):
        """Find the best available ffmpeg binary."""
        for path in FFMPEG_PATHS:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        # Last resort — check PATH
        try:
            result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True, timeout=3)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None

    @property
    def ffmpeg_path(self):
        """Cached ffmpeg path."""
        if not hasattr(self, '_ffmpeg_path') or self._ffmpeg_path is None:
            self._ffmpeg_path = self._find_ffmpeg()
        return self._ffmpeg_path

    @property
    def ffmpeg_available(self):
        return self.ffmpeg_path is not None

    @property
    def ffmpeg_info(self):
        """Return info about the ffmpeg we'll use."""
        path = self.ffmpeg_path
        if not path:
            return "not installed"
        is_ours = "packages/bin" in path
        try:
            result = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=3)
            ver = result.stdout.split("\n")[0] if result.stdout else "unknown"
            has_x264 = "libx264" in (result.stdout + result.stderr)
        except:
            ver = "unknown"
            has_x264 = False
        source = "installed" if is_ours else "system"
        codec = "h264 (libx264)" if has_x264 else "mpeg4 (fallback)"
        return f"{source} — {codec}"

    def _detect_framebuffer(self):
        """Read framebuffer dimensions from sysfs."""
        try:
            with open("/sys/class/graphics/fb0/virtual_size") as f:
                dims = f.read().strip().split(",")
                self.fb_width = int(dims[0])
                raw_height = int(dims[1])
                # Detect double buffering — if height > width, likely doubled
                if raw_height > self.fb_width:
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

    def _detect_encoder(self):
        """Find the best available h264 encoder by actually testing them."""
        ff = self.ffmpeg_path
        if not ff:
            return "mpeg4", "-b:v 3M"

        bitrates = {"low": "1M", "medium": "3M", "high": "6M"}
        br = bitrates.get(self.quality, "3M")

        # Check what's compiled in
        try:
            result = subprocess.run([ff, "-codecs"], capture_output=True, text=True, timeout=5)
            config = result.stdout + result.stderr
        except:
            config = ""

        # Option 1: libx264 (best quality, needs --enable-libx264)
        if "--enable-libx264" in config:
            return "libx264", f"-preset {self._preset} -crf {self._crf}"

        # Option 2: mpeg4 (software, always works, decent quality)
        # Skip h264_v4l2m2m — requires specific V4L2 hardware that most handhelds lack
        return "mpeg4", f"-b:v {br}"

    def start(self):
        """Start recording. ffmpeg runs fully detached — survives app exit."""
        if self.recording:
            return False

        ff = self.ffmpeg_path
        if not ff:
            return False

        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        outfile = os.path.join(self.output_dir, f"rec_{timestamp}.mp4")

        encoder, enc_opts = self._detect_encoder()

        # Write a launcher script — most reliable way to detach on all systems
        launcher = os.path.join(self.output_dir, ".rec_launch.sh")
        with open(launcher, "w") as f:
            f.write(f"""#!/bin/sh
{ff} -y \\
  -f rawvideo -pixel_format {self._pixel_format} \\
  -video_size {self.fb_width}x{self.fb_height} \\
  -framerate {self.fps} \\
  -i {self.fb_device} \\
  -c:v {encoder} {enc_opts} \\
  -pix_fmt yuv420p \\
  "{outfile}" \\
  > /dev/null 2>&1 &
echo $!
""")
        os.chmod(launcher, 0o755)

        try:
            # Fire and forget — os.system returns immediately since script backgrounds
            os.system(f"{launcher} > /tmp/.rec_pid 2>/dev/null")
            time.sleep(1)

            # Read PID from the script's echo output
            pid = ""
            try:
                with open("/tmp/.rec_pid") as f:
                    pid = f.read().strip().split("\n")[-1]
            except:
                pass

            # Fallback: pgrep
            if not pid or not pid.isdigit():
                result = subprocess.run(
                    ["pgrep", "-f", "ffmpeg.*rawvideo"],
                    capture_output=True, text=True, timeout=3)
                pids = result.stdout.strip().split("\n")
                pid = pids[-1] if pids and pids[-1] else ""

            if pid and pid.isdigit():
                # Verify it's actually running
                try:
                    os.kill(int(pid), 0)
                except OSError:
                    return False

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
            result = subprocess.run(["fbgrab", "-d", self.fb_device, filename], capture_output=True, timeout=5)
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
