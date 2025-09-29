# Swim Timer dengan test.mosquitto.org

Proyek Swim Timer yang telah dikonfigurasi untuk menggunakan broker MQTT publik `test.mosquitto.org`.

## 🌐 Broker Information

**test.mosquitto.org** adalah server MQTT publik yang disediakan oleh Eclipse Mosquitto untuk keperluan testing dan pengembangan.

### Port yang Tersedia:
- **1883** : MQTT, unencrypted, unauthenticated (default)
- **1884** : MQTT, unencrypted, authenticated
- **8883** : MQTT, encrypted, unauthenticated
- **8884** : MQTT, encrypted, client certificate required
- **8885** : MQTT, encrypted, authenticated
- **8886** : MQTT, encrypted, unauthenticated
- **8887** : MQTT, encrypted, server certificate deliberately expired
- **8080** : MQTT over WebSockets, unencrypted, unauthenticated
- **8081** : MQTT over WebSockets, encrypted, unauthenticated
- **8090** : MQTT over WebSockets, unencrypted, authenticated
- **8091** : MQTT over WebSockets, encrypted, authenticated

### Authentication:
- **rw/readwrite** : read/write access
- **ro/readonly** : read only access
- **wo/writeonly** : write only access

## 📁 File Baru

### Konfigurasi
- `config_mosquitto.py` - Konfigurasi untuk test.mosquitto.org
- `swim_timer_web_mosquitto.py` - Web application dengan broker baru
- `test_mqtt_mosquitto.py` - Test script untuk koneksi MQTT
- `monitor_mosquitto.py` - Monitor sistem dengan broker baru

### Arduino/ESP32
- `timerstart_mosquitto.ino` - Sensor start dengan broker baru
- `TIMERSTOP_mosquitto.ino` - Sensor stop dengan broker baru

## 🚀 Cara Penggunaan

### 1. Test Koneksi MQTT
```bash
python test_mqtt_mosquitto.py
```

### 2. Jalankan Web Application
```bash
python swim_timer_web_mosquitto.py
```

### 3. Monitor Sistem
```bash
# Single check
python monitor_mosquitto.py

# Continuous monitoring (30 detik interval)
python monitor_mosquitto.py --continuous 30
```

### 4. Upload Arduino Code
Upload file `.ino` yang sesuai ke ESP32:
- `timerstart_mosquitto.ino` untuk sensor start
- `TIMERSTOP_mosquitto.ino` untuk sensor stop

## ⚙️ Konfigurasi

### Mengubah Port
Edit `config_mosquitto.py`:
```python
MQTT_PORT = 1884  # Untuk authenticated
# atau
MQTT_PORT = 8080  # Untuk WebSocket
```

### Menggunakan Authentication
Edit `config_mosquitto.py`:
```python
MQTT_USERNAME = "rw"
MQTT_PASSWORD = "readwrite"
```

### Menggunakan Port Encrypted
Edit `config_mosquitto.py`:
```python
MQTT_PORT = 8883  # Encrypted, unauthenticated
```

## 🔧 Perbedaan dengan Setup Asli

| Aspek | Setup Asli | Setup Mosquitto |
|-------|------------|-----------------|
| Broker | broker.emqx.io | test.mosquitto.org |
| Port | 1883 | 1883 (default) |
| Authentication | Tidak ada | Opsional |
| Encryption | Tidak ada | Tersedia |
| WebSocket | Tidak ada | Tersedia |
| Stabilitas | Production | Testing |
| Kecepatan | Normal | Mungkin lambat |

## ⚠️ Catatan Penting

### Keuntungan test.mosquitto.org:
- ✅ Gratis untuk testing
- ✅ Banyak pilihan port
- ✅ Support WebSocket
- ✅ Support encryption
- ✅ Support authentication

### Keterbatasan:
- ⚠️ **Tidak untuk production**
- ⚠️ Mungkin tidak stabil (testing server)
- ⚠️ Mungkin lambat (runs under valgrind/perf)
- ⚠️ WebSocket dan TLS mungkin tidak tersedia
- ⚠️ Server mungkin restart sewaktu-waktu

## 🧪 Testing

### Test Koneksi Dasar
```bash
python test_mqtt_mosquitto.py
```

### Test Berbagai Port
Script akan otomatis test port 1883, 1884, dan 8080.

### Test Web Interface
1. Jalankan `swim_timer_web_mosquitto.py`
2. Buka browser ke `http://localhost:5000`
3. Cek broker info di `http://localhost:5000/api/broker-info`

## 📊 Monitoring

### Real-time Monitoring
```bash
python monitor_mosquitto.py --continuous 10
```

### Check Status
```bash
python monitor_mosquitto.py
```

## 🔄 Migrasi dari broker.emqx.io

1. **Backup konfigurasi lama**
2. **Gunakan file baru** (dengan suffix `_mosquitto`)
3. **Test koneksi** dengan `test_mqtt_mosquitto.py`
4. **Update ESP32** dengan file Arduino baru
5. **Monitor sistem** dengan `monitor_mosquitto.py`

## 📞 Support

- **Website**: https://test.mosquitto.org/
- **Documentation**: http://mqtt.org/
- **Matrix Channel**: Mosquitto channel

## 🎯 Rekomendasi

1. **Untuk Development**: Gunakan port 1883 (default)
2. **Untuk Testing Security**: Gunakan port 1884 dengan auth
3. **Untuk WebSocket**: Gunakan port 8080
4. **Untuk Production**: Pindah ke broker production

---

**⚠️ Peringatan**: Server ini hanya untuk testing. Jangan gunakan untuk aplikasi production yang membutuhkan stabilitas tinggi.
