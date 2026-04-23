#!/bin/bash
# Automated Setup for Local Modules

echo "[*] Updating system and installing pip..."
sudo apt update && sudo apt install python3-pip -y

echo "[*] Downloading dependencies into ./modules folder..."
mkdir -p modules
python3 -m pip install -t modules -r requirements.txt

echo "[*] Setting up React Frontend..."
if command -v npm &> /dev/null
then
    npm install
    cd frontend && npm install && npm run build
    cd ..
    echo "[✔] Frontend built successfully!"
else
    echo "[!] NPM not found. Please install Node.js and run 'npm install' in frontend directory."
fi

echo ""
echo "[✔] SETUP COMPLETE!"
echo "[i] You can now run the app using: npm run dev (for development)"
echo "[i] Or: python3 run.py (for API only)"
