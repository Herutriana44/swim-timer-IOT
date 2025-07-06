#!/bin/bash

echo "🏊‍♂️ Swim Timer Web Application"
echo "================================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment tidak ditemukan!"
    echo "📦 Jalankan install.sh terlebih dahulu"
    exit 1
fi

# Activate virtual environment
echo "🔧 Mengaktifkan virtual environment..."
source venv/bin/activate

# Check if required files exist
if [ ! -f "swim_timer_web.py" ]; then
    echo "❌ File swim_timer_web.py tidak ditemukan!"
    exit 1
fi

if [ ! -f "templates/index.html" ]; then
    echo "❌ File templates/index.html tidak ditemukan!"
    exit 1
fi

# Get IP address
IP_ADDRESS=$(hostname -I | awk '{print $1}')

echo "✅ Semua file ditemukan"
echo "🌐 Web interface akan tersedia di: http://$IP_ADDRESS:5000"
echo "📡 MQTT Topic: renang/timer"
echo ""
echo "🚀 Menjalankan web server..."
echo "Tekan Ctrl+C untuk menghentikan"
echo ""

# Run the application
python swim_timer_web.py 