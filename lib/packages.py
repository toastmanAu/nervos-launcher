"""
packages.py — Lightweight package manager for Nervos Launcher
No apt, no pacman, no flatpak. Just a JSON registry of static binaries.

Registry: packages.json in this repo (or remote URL)
Binaries: precompiled static binaries hosted on GitHub releases
Install: download tarball/binary → extract → symlink to PATH

Supports arm64 + x86_64. Falls back gracefully.
"""

import json
import os
import subprocess
import urllib.request
import threading


# Remote registry URL (falls back to local bundled copy)
REGISTRY_URL = "https://raw.githubusercontent.com/toastmanAu/nervos-launcher/main/packages.json"
LOCAL_REGISTRY = "packages.json"  # bundled fallback

# Where packages get installed on the device
DEFAULT_PKG_DIR = "/userdata/ckb-light-client/packages"
BIN_DIR = "/userdata/ckb-light-client/packages/bin"


def get_arch():
    """Detect architecture."""
    arch = os.uname().machine
    if arch in ("aarch64", "arm64"):
        return "arm64"
    elif arch == "x86_64":
        return "x86_64"
    return arch


def load_registry(install_dir=None):
    """Fetch package registry. Try remote first, fall back to local."""
    # Try remote
    try:
        req = urllib.request.Request(REGISTRY_URL, headers={"User-Agent": "nervos-launcher"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except:
        pass

    # Fall back to local
    paths = []
    if install_dir:
        paths.append(os.path.join(install_dir, "nervos-launcher", LOCAL_REGISTRY))
    paths.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), LOCAL_REGISTRY))

    for path in paths:
        try:
            with open(path) as f:
                return json.load(f)
        except:
            pass

    return {"packages": []}


def get_installed(pkg_dir=DEFAULT_PKG_DIR):
    """Read installed packages from local state file."""
    state_file = os.path.join(pkg_dir, "installed.json")
    try:
        with open(state_file) as f:
            return json.load(f)
    except:
        return {}


def save_installed(installed, pkg_dir=DEFAULT_PKG_DIR):
    os.makedirs(pkg_dir, exist_ok=True)
    with open(os.path.join(pkg_dir, "installed.json"), "w") as f:
        json.dump(installed, f, indent=2)


class PackageManager:
    """Lightweight package manager using static binaries from a JSON registry."""

    def __init__(self, install_dir="/userdata/ckb-light-client", progress=None):
        self.install_dir = install_dir
        self.pkg_dir = os.path.join(install_dir, "packages")
        self.bin_dir = os.path.join(self.pkg_dir, "bin")
        self.progress = progress  # ProgressLog instance for live updates
        self.arch = get_arch()
        self.registry = {"packages": []}
        self.installed = {}

    def refresh(self):
        """Reload registry and installed state."""
        self.registry = load_registry(self.install_dir)
        self.installed = get_installed(self.pkg_dir)

    def list_available(self):
        """Return list of packages available for this architecture."""
        pkgs = []
        for pkg in self.registry.get("packages", []):
            binaries = pkg.get("binaries", {})
            if self.arch in binaries:
                pkg_copy = dict(pkg)
                pkg_copy["is_installed"] = pkg["name"] in self.installed
                pkg_copy["installed_version"] = self.installed.get(pkg["name"], {}).get("version", "")
                pkgs.append(pkg_copy)
        return pkgs

    def is_installed(self, name):
        return name in self.installed

    def install(self, name):
        """Install a package by name. Runs in current thread — wrap in threading for async."""
        p = self.progress
        self.refresh()

        # Find package in registry
        pkg = None
        for candidate in self.registry.get("packages", []):
            if candidate["name"] == name:
                pkg = candidate
                break

        if not pkg:
            if p: p.error(f"Package '{name}' not found in registry")
            return False

        binaries = pkg.get("binaries", {})
        if self.arch not in binaries:
            if p: p.error(f"No {self.arch} binary for '{name}'")
            return False

        binary_info = binaries[self.arch]
        url = binary_info["url"]
        bin_name = binary_info.get("bin", name)
        is_archive = binary_info.get("archive", url.endswith(".tar.gz") or url.endswith(".zip"))

        if p: p.step(f"Installing {name}")
        if p: p.info(f"Arch: {self.arch}")

        try:
            os.makedirs(self.bin_dir, exist_ok=True)
            dest = os.path.join(self.bin_dir, bin_name)

            if is_archive:
                # Download archive
                if p: p.step(f"Downloading {name}")
                tarball = f"/tmp/nervos-pkg-{name}.tar.gz"
                self._download(url, tarball, p)

                # Extract
                if p: p.step("Extracting")
                subprocess.run(f"cd /tmp && tar -xzf nervos-pkg-{name}.tar.gz",
                               shell=True, capture_output=True, timeout=30)

                # Find the binary
                result = subprocess.run(
                    f"find /tmp -name '{bin_name}' -type f | head -1",
                    shell=True, capture_output=True, text=True, timeout=10)
                found = result.stdout.strip()

                if not found:
                    if p: p.error(f"Binary '{bin_name}' not found in archive")
                    return False

                subprocess.run(["cp", found, dest], check=True, timeout=5)
                os.remove(tarball)
            else:
                # Direct binary download
                if p: p.step(f"Downloading {name}")
                self._download(url, dest, p)

            os.chmod(dest, 0o755)
            if p: p.ok(f"Installed: {dest}")

            # Run post-install commands if any
            post_install = pkg.get("post_install", [])
            for cmd in post_install:
                if p: p.info(f"Running: {cmd}")
                subprocess.run(cmd, shell=True, capture_output=True, timeout=30,
                               cwd=self.install_dir)

            # Update installed state
            self.installed[name] = {
                "version": pkg.get("version", "unknown"),
                "bin": dest,
                "description": pkg.get("description", ""),
            }
            save_installed(self.installed, self.pkg_dir)

            if p: p.ok(f"{name} v{pkg.get('version', '?')} installed")
            if p: p.finish(True)
            return True

        except Exception as e:
            if p: p.error(f"Failed: {e}")
            if p: p.finish(False)
            return False

    def uninstall(self, name):
        """Remove a package."""
        if name not in self.installed:
            return False

        info = self.installed[name]
        bin_path = info.get("bin", "")
        if bin_path and os.path.exists(bin_path):
            os.remove(bin_path)

        del self.installed[name]
        save_installed(self.installed, self.pkg_dir)
        return True

    def install_async(self, name, progress=None):
        """Install in background thread."""
        if progress:
            self.progress = progress
        if self.progress:
            self.progress.clear()
            self.progress.busy = True
            self.progress.title = f"Installing {name}"
        threading.Thread(target=self.install, args=(name,), daemon=True).start()

    def _download(self, url, dest, p=None):
        """Download with progress updates."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nervos-launcher"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                last_update = 0

                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if p and downloaded - last_update > 256 * 1024:
                            mb = downloaded / (1024 * 1024)
                            if total > 0:
                                pct = int((downloaded / total) * 100)
                                total_mb = total / (1024 * 1024)
                                p.info(f"  {mb:.1f}MB / {total_mb:.1f}MB ({pct}%)")
                            else:
                                p.info(f"  {mb:.1f}MB")
                            last_update = downloaded

            mb = downloaded / (1024 * 1024) if downloaded else 0
            if p: p.ok(f"Downloaded {mb:.1f}MB")
        except Exception as e:
            if p: p.error(f"Download failed: {e}")
            raise
