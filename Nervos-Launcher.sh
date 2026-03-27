#!/bin/sh
# Nervos Launcher — self-bootstrapping EmulationStation port
# Drop this file in /userdata/roms/ports/ and it handles the rest.
INSTALL_DIR=/userdata/ckb-light-client
LAUNCHER_DIR=$INSTALL_DIR/nervos-launcher

if [ ! -f "$LAUNCHER_DIR/launcher.py" ]; then
  echo "Downloading Nervos Launcher..."
  mkdir -p $INSTALL_DIR
  cd /tmp
  curl -fsSL -o nl.tar.gz "https://github.com/toastmanAu/nervos-launcher/archive/refs/heads/main.tar.gz"
  tar -xzf nl.tar.gz
  mkdir -p $LAUNCHER_DIR
  cp -r nervos-launcher-main/launcher.py nervos-launcher-main/lib nervos-launcher-main/screens nervos-launcher-main/assets $LAUNCHER_DIR/
  rm -rf nl.tar.gz nervos-launcher-main
  echo "Nervos Launcher installed."
fi

cd $INSTALL_DIR
python3 $LAUNCHER_DIR/launcher.py

if [ $? -ne 0 ]; then
  echo "Error. Press any key..."
  read -n 1
fi
