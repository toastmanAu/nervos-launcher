# Installing Nervos Launcher

Three methods — choose whichever works for your device.

## Method 1: SD Card (works on ALL devices, no network needed)

1. Power off your handheld and remove the SD card
2. Insert SD card into your PC
3. Navigate to the `roms/ports/` folder on the SD card
4. Download the latest release from:
   https://github.com/toastmanAu/nervos-launcher/releases
5. Extract the zip — copy `Nervos-Launcher.sh` into `roms/ports/`
6. Also copy the `nervos-launcher/` folder into `roms/ports/` (or anywhere on the SD card)
7. Eject SD card, put it back in the handheld, power on
8. Refresh gamelists (START > Game Settings > Update Gamelists)
9. Find "Nervos-Launcher" in the Ports menu

**For box art:** Also copy `assets/boxart.png` to `roms/ports/images/Nervos-Launcher.png`

## Method 2: SSH (one command)

If your device has SSH enabled and network access:

```bash
# From your PC:
ssh root@<device-ip> 'mkdir -p /userdata/roms/ports && curl -fsSL -o /userdata/roms/ports/Nervos-Launcher.sh https://raw.githubusercontent.com/toastmanAu/nervos-launcher/main/Nervos-Launcher.sh && chmod +x /userdata/roms/ports/Nervos-Launcher.sh'
```

Or copy the file manually:
```bash
scp Nervos-Launcher.sh root@<device-ip>:/userdata/roms/ports/
```

The launcher self-bootstraps on first run — downloads the full app from GitHub.

## Method 3: Network file transfer (SMB/SFTP)

Most gaming OSes expose a network share:

- **Knulli:** `\\KNULLI\share\roms\ports\` (or SFTP on port 22)
- **ROCKNIX:** `\\ROCKNIX\roms\ports\`
- **Batocera:** `\\BATOCERA\share\roms\ports\`
- **ArkOS:** SFTP on port 22

Copy `Nervos-Launcher.sh` to the ports folder via your file manager.

## Enabling SSH

If SSH isn't enabled on your device:

| Firmware | How to enable SSH |
|----------|-------------------|
| **Knulli** | Settings > Network > Enable SSH |
| **ROCKNIX** | START > Network Settings > Enable SSH |
| **muOS** | Web Services > Enable SFTP |
| **ArkOS** | Enabled by default (user: ark, pass: ark) |
| **Batocera** | Enabled by default (user: root, pass: linux) |

## After Installation

1. Launch "Nervos-Launcher" from the Ports menu
2. First run: map your buttons (d-pad, A, B, X, Y, L1, R1, Select, Start)
3. Go to Settings > Install Light Client
4. Watch the live progress as it downloads and installs
5. Enable auto-start if you want the light client running on every boot

## Troubleshooting

**App doesn't appear in Ports:** Refresh gamelists (START > Game Settings > Update Gamelists) or reboot.

**"python3 not found":** Your OS doesn't include Python. The launcher tries to install it automatically, but if that fails: `apt-get install python3 python3-pygame` (on apt-based systems).

**"pygame not found":** Try `pip3 install pygame` via SSH, or install `python3-pygame` via your OS package manager.

**No network on device:** Use Method 1 (SD card). You can also pre-download the light client binary on your PC and copy it to `ckb-light-client/bin/ckb-light-client` on the SD card.
