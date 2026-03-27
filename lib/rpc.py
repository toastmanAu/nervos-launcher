"""
rpc.py — CKB Light Client RPC wrapper
Async-friendly (uses urllib, no extra deps) with caching.
"""

import json
import urllib.request
import time
import threading


class LightClientRPC:
    """Wrapper for ckb-light-client JSON-RPC."""

    def __init__(self, url="http://127.0.0.1:9000"):
        self.url = url
        self._cache = {}
        self._cache_ttl = {}
        self._lock = threading.Lock()
        self._id = 0

    def _next_id(self):
        self._id += 1
        return self._id

    def call(self, method, params=None, cache_secs=0):
        """Make an RPC call. Returns result dict or None on error."""
        cache_key = f"{method}:{json.dumps(params or [])}"

        # Check cache
        if cache_secs > 0:
            with self._lock:
                if cache_key in self._cache and time.time() < self._cache_ttl.get(cache_key, 0):
                    return self._cache[cache_key]

        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": self._next_id()
        }).encode()

        try:
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                result = data.get("result")
                if cache_secs > 0 and result is not None:
                    with self._lock:
                        self._cache[cache_key] = result
                        self._cache_ttl[cache_key] = time.time() + cache_secs
                return result
        except Exception:
            return None

    # ── Convenience methods ──────────────────────────────────

    def node_info(self):
        """Get local node info (node_id, version, connections)."""
        return self.call("local_node_info", cache_secs=10)

    def tip_header(self):
        """Get the current tip header."""
        return self.call("get_tip_header", cache_secs=3)

    def peers(self):
        """Get connected peers list."""
        return self.call("get_peers", cache_secs=5)

    def get_cells_capacity(self, script):
        """Get total capacity for a lock script."""
        return self.call("get_cells_capacity", [{"script": script, "script_type": "lock"}])

    def set_scripts(self, scripts):
        """Set scripts to watch."""
        return self.call("set_scripts", [scripts])

    def get_scripts(self):
        """Get currently watched scripts."""
        return self.call("get_scripts", cache_secs=10)

    def is_alive(self):
        """Quick check if the RPC is responding."""
        info = self.call("local_node_info", cache_secs=2)
        return info is not None

    # ── Parsed helpers ───────────────────────────────────────

    def get_status(self):
        """Return a combined status dict for the dashboard."""
        info = self.node_info()
        tip = self.tip_header()
        peer_list = self.peers()

        status = {
            "alive": info is not None,
            "node_id": "",
            "version": "",
            "block": 0,
            "block_hash": "",
            "epoch": "",
            "timestamp": 0,
            "peers": 0,
            "peer_list": [],
        }

        if info:
            status["node_id"] = info.get("node_id", "")
            status["version"] = info.get("version", "")

        if tip:
            inner = tip.get("inner", tip)  # handle both nested and flat
            number = inner.get("number", "0x0")
            status["block"] = int(number, 16) if isinstance(number, str) else number
            status["block_hash"] = inner.get("hash", "")[:18] + "..."
            status["epoch"] = inner.get("epoch", "")
            ts = inner.get("timestamp", "0x0")
            status["timestamp"] = int(ts, 16) if isinstance(ts, str) else ts

        if peer_list:
            status["peers"] = len(peer_list)
            status["peer_list"] = peer_list

        return status


# ── Background poller ────────────────────────────────────────
class StatusPoller:
    """Polls the light client RPC in a background thread."""

    def __init__(self, rpc, interval=3.0):
        self.rpc = rpc
        self.interval = interval
        self.status = {"alive": False, "block": 0, "peers": 0}
        self._thread = None
        self._running = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                self.status = self.rpc.get_status()
            except:
                self.status = {"alive": False, "block": 0, "peers": 0}
            time.sleep(self.interval)
