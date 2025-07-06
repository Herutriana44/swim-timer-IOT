# Swim Timer Web Application untuk Raspberry Pi 3

Program web sederhana untuk menampilkan timer renang secara realtime dari sensor ESP32.

## Fitur

- ⏱️ **Timer Real-time**: Menampilkan waktu berjalan secara real-time
- 🏊‍♂️ **Lap Counter**: Menghitung jumlah lap dan waktu lap terakhir
- 📡 **MQTT Integration**: Terhubung dengan ESP32 melalui MQTT broker
- 🌐 **Web Interface**: Interface web yang responsive dan modern
- 🔄 **Auto Reset**: Tombol reset untuk mengatur ulang timer
- 📱 **Mobile Friendly**: Responsive design untuk berbagai ukuran layar

## Komponen Sistem

1. **ESP32 Start Sensor** (`timerstart.ino`)
   - Sensor ultrasonik untuk deteksi start
   - Mengirim pesan "start" via MQTT

2. **ESP32 Stop Sensor** (`TIMERSTOP.ino`)
   - Sensor IR untuk deteksi finish
   - Mengirim pesan "stop" via MQTT

3. **Raspberry Pi 3 Web Server** (`swim_timer_web.py`)
   - Menerima pesan MQTT dari ESP32
   - Menampilkan timer di web interface

## Instalasi di Raspberry Pi 3

### 1. Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Python Dependencies
```bash
sudo apt install python3-pip python3-venv -y
```

### 3. Clone/Download Project
```bash
# Jika menggunakan git
git clone <repository-url>
cd swim-timer-IOT-main

# Atau copy file manual ke Raspberry Pi
```

### 4. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Buat Direktori Templates
```bash
mkdir templates
```

### 6. Copy Files
Pastikan file-file berikut ada:
- `swim_timer_web.py`
- `templates/index.html`
- `requirements.txt`

## Konfigurasi

### MQTT Settings
Program menggunakan MQTT broker publik `broker.emqx.io`. Jika ingin menggunakan broker lokal:

1. Edit file `swim_timer_web.py`
2. Ubah variabel MQTT:
```python
MQTT_BROKER = "your-mqtt-broker-ip"
MQTT_PORT = 1883
MQTT_TOPIC = "renang/timer"
```

### WiFi Settings
Pastikan Raspberry Pi terhubung ke WiFi yang sama dengan ESP32:
- SSID: "JE_ART 5"
- Password: "bubat123"

## Cara Menjalankan

### 1. Aktifkan Virtual Environment
```bash
source venv/bin/activate
```

### 2. Jalankan Web Server
```bash
python3 swim_timer_web.py
```

### 3. Akses Web Interface
Buka browser dan akses:
```
http://[raspberry-pi-ip]:5000
```

Contoh: `http://192.168.1.100:5000`

## Auto Start pada Boot

### Menggunakan systemd Service

1. Buat service file:
```bash
sudo nano /etc/systemd/system/swim-timer.service
```

2. Isi dengan konfigurasi:
```ini
[Unit]
Description=Swim Timer Web Application
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/swim-timer-IOT-main
Environment=PATH=/home/pi/swim-timer-IOT-main/venv/bin
ExecStart=/home/pi/swim-timer-IOT-main/venv/bin/python swim_timer_web.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable dan start service:
```bash
sudo systemctl enable swim-timer.service
sudo systemctl start swim-timer.service
```

4. Cek status:
```bash
sudo systemctl status swim-timer.service
```

## Cara Kerja

### Flow Timer:
1. **Standby**: Timer menunggu pesan "start" dari ESP32 start sensor
2. **Start**: Ketika sensor ultrasonik terdeteksi, ESP32 mengirim "start"
3. **Running**: Timer mulai berjalan dan menampilkan waktu real-time
4. **Lap**: Setiap kali sensor start terdeteksi lagi, lap counter bertambah
5. **Stop**: Ketika sensor IR finish terdeteksi, ESP32 mengirim "stop"
6. **Finish**: Timer berhenti dan menampilkan waktu total

### MQTT Messages:
- `"start"`: Mulai timer atau lap baru
- `"stop"`: Hentikan timer

## Troubleshooting

### 1. MQTT Connection Error
- Pastikan internet connection stabil
- Cek firewall settings
- Coba restart program

### 2. Web Interface Tidak Muncul
- Cek apakah port 5000 tidak digunakan aplikasi lain
- Pastikan firewall mengizinkan port 5000
- Cek log error di terminal

### 3. Timer Tidak Update
- Pastikan ESP32 terhubung ke WiFi yang sama
- Cek MQTT topic name
- Restart program web

### 4. Performance Issues
- Tutup aplikasi lain yang tidak perlu
- Pastikan Raspberry Pi tidak terlalu panas
- Cek memory usage dengan `htop`

## Monitoring

### Log Files
```bash
# Cek service logs
sudo journalctl -u swim-timer.service -f

# Cek real-time logs
tail -f /var/log/syslog | grep swim-timer
```

### System Resources
```bash
# Monitor CPU dan Memory
htop

# Monitor Network
iftop

# Monitor Disk
df -h
```

## Customization

### Mengubah Tema
Edit file `templates/index.html` bagian CSS untuk mengubah:
- Warna background
- Font style
- Layout design
- Animasi

### Menambah Fitur
- Export data ke CSV
- Multiple timer support
- Sound notifications
- Database logging

## Support

Jika ada masalah atau pertanyaan:
1. Cek log error di terminal
2. Pastikan semua dependencies terinstall
3. Restart service jika diperlukan
4. Cek koneksi network dan MQTT

## License

Program ini dibuat untuk sistem timer renang IoT. Silakan modifikasi sesuai kebutuhan. 