#!/bin/bash
# Full Deployment Script for AI Bot Trader
# Run this as 'ubuntu' user

PROJECT_NAME="Ai-Bot-Trader"
SOURCE_DIR="/home/akshay-b/Desktop/Ai Bot Trader"
TARGET_DIR="/home/ubuntu/$PROJECT_NAME"

echo "[*] Starting Full Deployment..."

# 1. Move project if source exists
if [ -d "$SOURCE_DIR" ]; then
    echo "[*] Moving project from Desktop to $TARGET_DIR..."
    sudo mv "$SOURCE_DIR" "$TARGET_DIR"
    sudo chown -R ubuntu:ubuntu "$TARGET_DIR"
fi

cd "$TARGET_DIR" || { echo "[!] Failed to enter project directory"; exit 1; }

# 2. Install System Dependencies
echo "[*] Installing system dependencies (Node.js, NPM, Gunicorn)..."
sudo apt update
sudo apt install -y nodejs npm gunicorn

# 3. Setup Python Virtual Environment
echo "[*] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 4. Setup React Frontend
echo "[*] Building React Frontend..."
npm install
cd frontend
npm install
npm run build
cd ..

# 5. Service Configuration
echo "[*] Configuring Systemd Service..."
sudo cp trading_bot.service /etc/systemd/system/trading_bot.service
sudo systemctl daemon-reload
sudo systemctl enable trading_bot.service
sudo systemctl restart trading_bot.service

echo ""
echo "[✔] DEPLOYMENT COMPLETE!"
echo "[i] Backend running at http://0.0.0.0:8000"
echo "[i] Status: sudo systemctl status trading_bot.service"
