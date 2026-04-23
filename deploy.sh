#!/bin/bash
# Full Deployment Script for AI Bot Trader (Production)
# Run this as 'ubuntu' user inside /home/ubuntu/Ai-Bot-Trader

TARGET_DIR="/home/ubuntu/Ai-Bot-Trader"

echo "[*] Starting Production Deployment in $TARGET_DIR..."

cd "$TARGET_DIR" || { echo "[!] Failed to enter project directory. Please ensure you are in $TARGET_DIR"; exit 1; }

# 1. Reset Permissions
echo "[*] Setting permissions..."
sudo chown -R ubuntu:www-data .
sudo chmod -R 775 .

# 2. Install System Dependencies
echo "[*] Installing system dependencies (Node.js, NPM, Gunicorn)..."
sudo apt update
sudo apt install -y nodejs npm gunicorn

# 3. Setup Python Virtual Environment
echo "[*] Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 4. Setup React Frontend
echo "[*] Building React Frontend..."
# Root dependencies (concurrently, etc.)
npm install
# Frontend specific build
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
echo "[✔] PRODUCTION DEPLOYMENT COMPLETE!"
echo "[i] Status: sudo systemctl status trading_bot.service"
