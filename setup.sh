#!/bin/bash
# Automated Setup for Local Modules

echo "[*] Updating system and installing pip..."
sudo apt update && sudo apt install python3-pip -y

echo "[*] Downloading dependencies into ./modules folder..."
mkdir -p modules
python3 -m pip install -t modules -r requirements.txt

echo ""
echo "[✔] SETUP COMPLETE!"
echo "[i] You can now run the app using: python3 run.py"
echo "[i] All libraries are stored locally in the './modules' folder."
