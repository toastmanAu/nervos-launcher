# Nervos Launcher

Nervos Blockchain App Store for retro gaming handhelds. Install and manage the CKB light client, explore blocks, connect to peers, and run Nervos dApps — all from your handheld's Ports menu.

![Nervos Launcher Box Art](assets/boxart.png)

## What It Does

A pygame-based app that runs as an EmulationStation port. Self-bootstrapping — just drop the launcher script on your device and it downloads everything from GitHub on first run.

**Screens:**
- **Home** — Dashboard with live sync status, block height, peer count, full node ID and tip hash
- **Explorer** — Scrollable tip header with full hashes, epoch, timestamps, word wrapping
- **Peers** — Connected peers list with drill-down detail view (addresses, protocols, duration)
- **Recorder** — Screen + audio capture via ffmpeg. Records while playing games. Detached process survives app exit
- **Settings** — Install/update light client, start/stop service, persistent auto-start, editable config.toml with reset-to-default
- **Terminal** — 5 command categories (RPC, Service, System, Network, Install), on-screen keyboard for custom commands, user-editable command JSON
- **Button Mapping** — First-boot gamepad configuration (d-pad, thumbstick, face buttons — 12 inputs)

**Key Features:**
- **Screen Recorder** — h264 video + AAC audio via custom ffmpeg build (11MB). Records the entire handheld screen including games, ES menus, everything. Background process persists across app exit
- **On-Screen Keyboard** — 5 charsets (abc, ABC, 123, hex, symbols), minimisable, works with any gamepad
- **Config Editor** — Edit config.toml with syntax highlighting, reset to default from GitHub
- **Package Manager** — JSON registry of static binaries (no apt/pacman needed). Install jq, micro, ffmpeg, and more
- **File Manager** — Browse directories, select output paths, view file info
- **Built-in Installer** — Downloads the CKB light client binary directly from GitHub releases. No SSH or PC required after initial setup
- **Auto-install Dependencies** — Bootstrap script detects and installs Python + pygame if missing

## Install on Your Handheld

### Option 1: One-file install (easiest)

SSH into your device and run:

```bash
mkdir -p /userdata/roms/ports
curl -fsSL -o /userdata/roms/ports/Nervos-Launcher.sh \
  https://raw.githubusercontent.com/toastmanAu/nervos-launcher/main/Nervos-Launcher.sh
chmod +x /userdata/roms/ports/Nervos-Launcher.sh
```

Reboot or refresh gamelists. Launch "Nervos-Launcher" from Ports. It downloads the app on first run.

### Option 2: Remote deploy script

From your PC, deploy to any device over SSH:

```bash
./deploy.sh --host 192.168.1.50 --user root
```

### Option 3: Manual

Copy the repo contents to `/userdata/ckb-light-client/nervos-launcher/` on your device.

## Controls

Configured on first launch via the button mapping screen.

| Action | Default |
|--------|---------|
| Navigate | D-pad / Thumbstick |
| Confirm | A |
| Back | B |
| Home | Start |
| Terminal shortcut | Select |
| Quick commands (terminal) | L1 / R1 |
| Clear terminal | X |
| Command history | Y |
| Exit app | Select + Start |

## Compatible Devices

Any Linux handheld or SBC with arm64 or x86_64, pygame, and SSH access.

### Tier 1 — Easiest

| Device | Arch | RAM | OS |
|--------|------|-----|----|
| Raspberry Pi 4/5 | arm64 | 2–8GB | Raspberry Pi OS |
| Orange Pi 5 | arm64 | 4–32GB | Ubuntu, Armbian |
| Steam Deck | x86_64 | 16GB | SteamOS |

### Tier 2 — High-RAM handhelds

| Device | Arch | RAM | CFW |
|--------|------|-----|-----|
| Retroid Pocket 5/6 | arm64 | 6–16GB | ROCKNIX |
| Ayn Odin 2 | arm64 | 8–16GB | ROCKNIX |
| GameForce Ace | arm64 | 8–12GB | ROCKNIX |

### Tier 3 — 2GB handhelds

| Device | Arch | RAM | CFW |
|--------|------|-----|-----|
| Anbernic RG353 series | arm64 | 2GB | ROCKNIX, ArkOS |
| Powkiddy X55 | arm64 | 2GB | ROCKNIX |

### Tier 4 — 1GB handhelds (tested)

| Device | Arch | RAM | CFW |
|--------|------|-----|-----|
| **Anbernic RG35XX H** | arm64 | 1GB | Knulli |
| Anbernic RG35XX Plus/SP | arm64 | 1GB | Knulli, ROCKNIX |
| Powkiddy RGB30 | arm64 | 1GB | ROCKNIX |
| TrimUI Smart Pro | arm64 | 1GB | Knulli |

### Not Compatible

| Device | Reason |
|--------|--------|
| Miyoo Mini / Plus | arm32 only |
| Anbernic RG35XX (2023) | 32-bit firmware |

## Verification

After deployment, generate a health report (saved locally, not on device):

```bash
./verify.sh --host 192.168.68.110 --user root
```

Reports saved to `tested/` as markdown.

## Architecture

```
nervos-launcher/
├── launcher.py              # Entry point, page registration
├── lib/
│   ├── ui.py                # App, Page, ScrollList, theme, widgets
│   ├── rpc.py               # Light client RPC wrapper + background poller
│   ├── installer.py         # Download engine with live progress
│   ├── packages.py          # Package manager (JSON registry + static binaries)
│   ├── keyboard.py          # On-screen keyboard (5 charsets, minimisable)
│   ├── editor.py            # Reusable text editor with syntax highlighting
│   ├── recorder.py          # Screen + audio recorder (detached ffmpeg)
│   └── fileman.py           # File manager / directory browser
├── screens/
│   ├── home.py              # Dashboard
│   ├── explorer.py          # Block explorer (scrollable, full hashes)
│   ├── peers.py             # Peer list + detail view (word wrapping)
│   ├── recorder.py          # Recorder control screen
│   ├── settings.py          # Service management + installer + config editor
│   ├── terminal.py          # Mini shell (5 categories, keyboard input)
│   ├── install_progress.py  # Live install progress
│   └── button_map.py        # First-boot input configuration (12 inputs)
├── packages.json            # Package registry (static binaries)
├── assets/                  # Box art, demo videos
├── deploy.sh                # Remote SSH deployer
├── verify.sh                # Health check report generator
└── tested/                  # Verified device reports
```

**Adding a new screen:** Create a file in `screens/`, subclass `Page`, register in `launcher.py`. The page system handles navigation stack (push/pop), input routing, and lifecycle.

## Testnet Only

This is currently **testnet only** — no mainnet support until thoroughly tested.

## Demo Videos

All recorded natively on the RG35XX H using the built-in screen recorder:

- **[Full Walkthrough](assets/nervos-launcher-demo.mp4)** — 4 min, complete tour of all features
- **[Game Recording with Audio](assets/game-recording-with-audio.mp4)** — 3 min, SNES gameplay + BGM audio capture
- **[First Run Setup](assets/first-run.mp4)** — Button mapping + initial configuration
- **[Terminal Demo](assets/terminal-demo.mp4)** — Command categories, RPC queries
- **[Launcher Promo](assets/launcher-promo.mp4)** — Highlight reel

## Roadmap

### Phase 1 — Core Platform (current)
- [x] Self-bootstrapping installer
- [x] Button mapping (d-pad, thumbstick, face buttons)
- [x] CKB light client installer with live progress
- [x] Block explorer, peer detail, terminal
- [x] On-screen keyboard + text editor
- [x] Screen recorder with audio (custom ffmpeg, h264 + AAC + PulseAudio)
- [x] Package manager (JSON registry, static binaries)
- [x] File manager widget
- [x] Config editor with syntax highlighting + reset
- [x] Package manager (JSON registry + static binaries)
- [x] Screen recorder (ffmpeg, detached process)
- [x] File manager widget
- [x] Persistent auto-start service
- [ ] PortMaster submission for one-tap install

### Phase 2 — dApp Store
- [ ] Plugin manifest (JSON) for installable modules
- [ ] dApp Store screen with images, descriptions, install/uninstall
- [ ] Desktop module builder tool for developers
- [ ] FiberQuest module (RetroArch tournaments with Fiber payments)
- [ ] Wallet module (watch addresses, check balances)
- [ ] DOB viewer (display Spore NFTs)

### Phase 3 — Nervos OS
- [ ] Fork Knulli/Buildroot with Nervos tools baked in
- [ ] CKB light client as system service (not port)
- [ ] Nervos Launcher as first-class ES app
- [ ] Custom ES theme with blockchain category
- [ ] Pre-configured drivers + WiFi + SSH
- [ ] System-level package manager integration
- [ ] Multi-device image builds (H700, RK3566, RK3588)

## Community

- [Nervos Nation Telegram](https://t.me/NervosNation)
- [Wyltek Industries](https://wyltekindustries.com)
- [GitHub](https://github.com/toastmanAu)

## License

MIT
