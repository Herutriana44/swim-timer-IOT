#!/bin/bash

echo "=========================================="
echo "  Swim Timer Web Application Installer"
echo "  untuk Raspberry Pi 3"
echo "=========================================="

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
sudo apt install python3-pip python3-venv -y

# Create virtual environment
echo "🔧 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment and install requirements
echo "📚 Installing Python packages..."
source venv/bin/activate
pip install -r requirements.txt

# Create templates directory if not exists
echo "📁 Creating templates directory..."
mkdir -p templates

# Set permissions
echo "🔐 Setting file permissions..."
chmod +x swim_timer_web.py

# Create systemd service
echo "⚙️ Creating systemd service..."
sudo tee /etc/systemd/system/swim-timer.service > /dev/null <<EOF
[Unit]
Description=Swim Timer Web Application
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python swim_timer_web.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "🚀 Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable swim-timer.service
sudo systemctl start swim-timer.service

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo "=========================================="
echo "✅ Installation completed!"
echo ""
echo "🌐 Web Interface: http://$IP_ADDRESS:5000"
echo "📊 Service Status: sudo systemctl status swim-timer.service"
echo "📝 View Logs: sudo journalctl -u swim-timer.service -f"
echo ""
echo "🔧 Manual start: source venv/bin/activate && python swim_timer_web.py"
echo "=========================================="

# Check service status
echo "🔍 Checking service status..."
sudo systemctl status swim-timer.service --no-pager -l 