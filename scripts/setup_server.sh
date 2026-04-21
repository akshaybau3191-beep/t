#!/bin/bash

# Update and install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv nginx certbot python3-certbot-nginx

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Setup .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[!] Created .env from template. Please edit it with your real keys."
fi

# Install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Setup Systemd Service
sudo cp trading_bot.service /etc/systemd/system/trading_bot.service
sudo systemctl daemon-reload
sudo systemctl enable trading_bot
sudo systemctl start trading_bot

# Setup Nginx
sudo cp nginx_config /etc/nginx/sites-available/trading_bot
sudo ln -sf /etc/nginx/sites-available/trading_bot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "Setup complete! Don't forget to run: sudo certbot --nginx -d yourdomain.com"
