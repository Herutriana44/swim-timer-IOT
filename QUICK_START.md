# 🏊‍♂️ Quick Start - Swim Timer Web Application

## 📋 Prerequisites
- Raspberry Pi 3 dengan Raspberry Pi OS
- Koneksi internet untuk MQTT broker
- ESP32 dengan program `timerstart.ino` dan `TIMERSTOP.ino`

## 🚀 Instalasi Cepat

### 1. Copy Files ke Raspberry Pi
```bash
# Copy semua file ke Raspberry Pi
scp -r . pi@[raspberry-pi-ip]:~/swim-timer/
```

### 2. Install Dependencies
```bash
# SSH ke Raspberry Pi
ssh pi@[raspberry-pi-ip]

# Masuk ke direktori
cd ~/swim-timer/

# Jalankan installer
chmod +x install.sh
./install.sh
```

### 3. Test Koneksi
```bash
# Test MQTT connection
./test_mqtt.py

# Test web interface
./run.sh
```

### 4. Akses Web Interface
Buka browser dan akses:
```
http://[raspberry-pi-ip]:5000
```

## 📱 Fitur Web Interface

- ⏱️ **Timer Real-time**: Update setiap 100ms
- 🏊‍♂️ **Lap Counter**: Hitung jumlah lap
- 📊 **Status Display**: Running/Stopped/Waiting
- 🔄 **Reset Button**: Reset timer manual
- 📱 **Responsive**: Bisa diakses dari mobile

## 🔧 Troubleshooting

### Web Interface Tidak Muncul
```bash
# Cek service status
sudo systemctl status swim-timer.service

# Restart service
sudo systemctl restart swim-timer.service

# Cek logs
sudo journalctl -u swim-timer.service -f
```

### MQTT Connection Error
```bash
# Test MQTT
./test_mqtt.py

# Cek internet connection
ping broker.emqx.io
```

### Manual Start
```bash
# Stop service
sudo systemctl stop swim-timer.service

# Start manual
./run.sh
```

## 📞 Support
Jika ada masalah, cek:
1. Log service: `sudo journalctl -u swim-timer.service -f`
2. Monitor sistem: `./monitor.py`
3. Test MQTT: `./test_mqtt.py`

## 🎯 Cara Kerja
1. ESP32 Start sensor deteksi → kirim "start" via MQTT
2. Web interface terima "start" → mulai timer
3. ESP32 Stop sensor deteksi → kirim "stop" via MQTT  
4. Web interface terima "stop" → hentikan timer

**Selamat menggunakan Swim Timer Web Application! 🏊‍♂️⏱️** 