"""
installer.py — Shared installer engine with live progress updates
Used by Settings screen and future dApp Store for installing/updating software.
Writes progress lines to a shared buffer that the UI renders in real-time.
"""

import os
import json
import threading
import subprocess
import urllib.request
import time


class ProgressLog:
    """Thread-safe log buffer for live install progress display."""

    def __init__(self, max_lines=50):
        self.lines = []  # list of (text, color_name) tuples
        self.max_lines = max_lines
        self._lock = threading.Lock()
        self.busy = False
        self.title = ""
        self.done = False
        self.success = False

    def log(self, text, color="text"):
        with self._lock:
            self.lines.append((text, color))
            if len(self.lines) > self.max_lines:
                self.lines = self.lines[-self.max_lines:]

    def info(self, text):
        self.log(f"  {text}", "muted")

    def step(self, text):
        self.log(f"▶ {text}", "accent")

    def ok(self, text):
        self.log(f"  ✓ {text}", "green")

    def warn(self, text):
        self.log(f"  ⚠ {text}", "yellow")

    def error(self, text):
        self.log(f"  ✗ {text}", "red")

    def clear(self):
        with self._lock:
            self.lines.clear()
            self.done = False
            self.success = False

    def get_lines(self):
        with self._lock:
            return list(self.lines)

    def finish(self, success=True):
        self.done = True
        self.success = success
        self.busy = False


class LightClientInstaller:
    """Downloads and installs/updates the CKB light client with live progress."""

    REPO = "nervosnetwork/ckb-light-client"
    CONFIG_URL = "https://raw.githubusercontent.com/nervosnetwork/ckb-light-client/develop/config"

    def __init__(self, install_dir="/userdata/ckb-light-client", progress=None):
        self.install_dir = install_dir
        self.progress = progress or ProgressLog()

    def install_async(self, network="testnet"):
        """Run install in background thread. Monitor progress via self.progress."""
        if self.progress.busy:
            return
        self.progress.clear()
        self.progress.busy = True
        self.progress.title = "Installing Light Client"
        threading.Thread(target=self._do_install, args=(network,), daemon=True).start()

    def _do_install(self, network):
        p = self.progress
        try:
            p.step("Detecting architecture")
            arch = os.uname().machine
            if arch in ("aarch64", "arm64"):
                target = "aarch64-linux"
            elif arch == "x86_64":
                target = "x86_64-linux"
            else:
                p.error(f"Unsupported: {arch}")
                p.finish(False)
                return
            p.ok(f"{arch} → {target}")

            # Find latest release
            p.step("Checking GitHub releases")
            releases = self._fetch_json(
                f"https://api.github.com/repos/{self.REPO}/releases?per_page=5"
            )
            if not releases:
                p.error("Failed to fetch releases")
                p.finish(False)
                return

            download_url = None
            version = None
            for rel in releases:
                for asset in rel.get("assets", []):
                    name = asset.get("name", "")
                    if target in name and name.endswith(".tar.gz"):
                        if "portable" in name or download_url is None:
                            download_url = asset["browser_download_url"]
                            version = rel["tag_name"]
                        if "portable" in name:
                            break
                if download_url:
                    break

            if not download_url:
                p.error(f"No {target} binary in releases")
                p.finish(False)
                return
            p.ok(f"Found {version}")

            # Download
            p.step(f"Downloading {version}")
            tarball = "/tmp/ckb-light-install.tar.gz"
            self._download_with_progress(download_url, tarball)

            # Extract
            p.step("Extracting binary")
            result = subprocess.run(
                f"cd /tmp && tar -xzf ckb-light-install.tar.gz",
                shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                p.error(f"Extract failed: {result.stderr[:80]}")
                p.finish(False)
                return

            # Find binary
            result = subprocess.run(
                "find /tmp -name 'ckb-light-client' -type f | head -1",
                shell=True, capture_output=True, text=True, timeout=10)
            bin_path = result.stdout.strip()
            if not bin_path or not os.path.isfile(bin_path):
                p.error("Binary not found in archive")
                p.finish(False)
                return
            p.ok("Binary extracted")

            # Stop if running
            was_running = self._is_running()
            if was_running:
                p.step("Stopping current instance")
                subprocess.run([os.path.join(self.install_dir, "stop.sh")],
                               capture_output=True, timeout=5)
                time.sleep(1)
                p.ok("Stopped")

            # Install binary
            p.step("Installing binary")
            os.makedirs(os.path.join(self.install_dir, "bin"), exist_ok=True)
            dest = os.path.join(self.install_dir, "bin", "ckb-light-client")
            subprocess.run(["cp", bin_path, dest], check=True, timeout=5)
            os.chmod(dest, 0o755)
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            p.ok(f"Binary installed ({size_mb:.1f}MB)")

            # Config
            config_path = os.path.join(self.install_dir, "config.toml")
            if not os.path.exists(config_path):
                p.step(f"Downloading {network} config")
                config_url = f"{self.CONFIG_URL}/{network}.toml"
                urllib.request.urlretrieve(config_url, config_path)
                p.ok(f"Config: {network}")
            else:
                p.info(f"Config exists, keeping current ({network})")

            # Data dirs
            os.makedirs(os.path.join(self.install_dir, "data", "store"), exist_ok=True)
            os.makedirs(os.path.join(self.install_dir, "data", "network"), exist_ok=True)

            # Wrapper scripts
            p.step("Creating scripts")
            self._write_scripts()
            p.ok("start.sh, stop.sh, status.sh")

            # Restart if was running
            if was_running:
                p.step("Restarting light client")
                subprocess.run([os.path.join(self.install_dir, "start.sh")],
                               capture_output=True, timeout=5)
                time.sleep(2)
                if self._is_running():
                    p.ok("Running")
                else:
                    p.warn("Started but may need a moment")

            # Cleanup
            try:
                os.remove(tarball)
            except:
                pass

            p.log("", "text")
            p.ok(f"Installation complete — {version}")
            p.finish(True)

        except Exception as e:
            p.error(f"Failed: {e}")
            p.finish(False)

    def _fetch_json(self, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nervos-wallet"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except:
            return None

    def _download_with_progress(self, url, dest):
        """Download with progress updates to the log."""
        p = self.progress
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nervos-wallet"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024
                last_update = 0

                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Update every 500KB
                        if downloaded - last_update > 512 * 1024:
                            if total > 0:
                                pct = int((downloaded / total) * 100)
                                mb = downloaded / (1024 * 1024)
                                total_mb = total / (1024 * 1024)
                                p.info(f"  {mb:.1f}MB / {total_mb:.1f}MB ({pct}%)")
                            else:
                                mb = downloaded / (1024 * 1024)
                                p.info(f"  {mb:.1f}MB downloaded")
                            last_update = downloaded

            mb = downloaded / (1024 * 1024)
            p.ok(f"Downloaded {mb:.1f}MB")
        except Exception as e:
            p.error(f"Download failed: {e}")
            raise

    def _is_running(self):
        pid_file = os.path.join(self.install_dir, "data", "ckb-light.pid")
        try:
            with open(pid_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except:
            return False

    def _write_scripts(self):
        scripts = {
            "start.sh": f'''#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
RUST_LOG=info,ckb_light_client=info \\
  nohup "$DIR/bin/ckb-light-client" run --config-file "$DIR/config.toml" \\
  >> "$DIR/data/ckb-light.log" 2>&1 &
echo "$!" > "$DIR/data/ckb-light.pid"
echo "Started (PID $!)"
''',
            "stop.sh": '''#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/data/ckb-light.pid"
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  kill "$PID" 2>/dev/null && echo "Stopped" || echo "Not running"
  rm -f "$PID_FILE"
else
  pkill -f ckb-light-client 2>/dev/null && echo "Stopped" || echo "Not running"
fi
''',
            "status.sh": '''#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$DIR/data/ckb-light.pid"
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
  echo "Running (PID $(cat "$PID_FILE"))"
else
  echo "Not running"
fi
curl -s -X POST http://127.0.0.1:9000/ \\
  -H 'Content-Type: application/json' \\
  -d '{"jsonrpc":"2.0","method":"get_tip_header","params":[],"id":1}' | python3 -m json.tool 2>/dev/null || echo "(RPC not responding)"
''',
        }
        for name, content in scripts.items():
            path = os.path.join(self.install_dir, name)
            with open(path, "w") as f:
                f.write(content)
            os.chmod(path, 0o755)
