#!/usr/bin/env python3
"""
Swim Timer Web Application untuk Raspberry Pi 3 dengan 2 Lintasan
Menampilkan timer renang secara realtime dari ESP32 sensors untuk 2 lintasan
Dengan dukungan data checkpoint per 10 meter dari simulasi renang

KONFIGURASI:
-----------
Untuk menggunakan dengan kode Arduino yang ada:
- Semua device menggunakan topic yang sama: "renang/timer"
- Lintasan 1 timerstart mengirim: "start1"
- Lintasan 2 timerstart mengirim: "start2"
- Lintasan 1 timerstop mengirim: "stop1"
- Lintasan 2 timerstop mengirim: "stop2"

Data checkpoint per 10 meter diterima dari simulasi:
- Topic checkpoint: "renang/timer/checkpoint" atau "renang/checkpoint"
- Format JSON: {"lane": 1, "checkpoint": 10, "time": 12.5, "timestamp": 1234567890}

CARA KERJA:
-----------
- Sistem mengidentifikasi lintasan berdasarkan pesan MQTT:
  - "start1" dan "stop1" → Lintasan 1
  - "start2" dan "stop2" → Lintasan 2
- Data checkpoint per 10 meter diterima dari simulasi renang via MQTT
- Semua device menggunakan topic yang sama: "renang/timer"

API ENDPOINTS:
-------------
- GET  /api/timer          - Data semua lintasan
- GET  /api/timer/1        - Data lintasan 1
- GET  /api/timer/2        - Data lintasan 2
- POST /api/reset          - Reset semua lintasan
- POST /api/reset/1        - Reset lintasan 1
- POST /api/reset/2        - Reset lintasan 2
- POST /api/<lane>/checkpoint/<num> - Set checkpoint untuk lintasan (num=1 berarti 10m, num=2 berarti 20m, dst)
"""

import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
import json
import sys
from functools import partial

# Pastikan output tidak ter-buffer sehingga tidak perlu menekan Enter di CMD
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# Semua print otomatis flush agar log terus mengalir
print = partial(print, flush=True)

app = Flask(__name__)

# Struktur data untuk setiap lintasan
class LaneTimer:
    def __init__(self, lane_number):
        self.lane_number = lane_number
        self.timer_running = False
        self.start_time = None
        self.elapsed_time = timedelta(0)
        self.last_lap_time = None
        self.lap_count = 0
        self.finished = False
        self.checkpoint_times = {}  # {checkpoint_distance: waktu dalam detik}
        self.checkpoint_data = {}   # {checkpoint_distance: {"time": waktu, "timestamp": timestamp}}

# Global variables untuk 2 lintasan
lanes = {
    1: LaneTimer(1),
    2: LaneTimer(2)
}

# Import configuration dari config_mosquitto.py
try:
    from config_mosquitto import *
except ImportError:
    # Default configuration jika config_mosquitto.py tidak ada
    MQTT_BROKER = "broker.emqx.io"
    MQTT_PORT = 1883
    MQTT_TOPIC = "renang/timer"
    MQTT_CLIENT_ID = "swim_timer_web"
    TIMER_UPDATE_INTERVAL = 0.1
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    WEB_DEBUG = False
    BROKER_INFO = {"name": "EMQX", "url": MQTT_BROKER}

# Topic untuk setiap lintasan (bisa menggunakan topic terpisah atau sama)
MQTT_TOPIC_LANE1 = getattr(globals(), 'MQTT_TOPIC_LANE1', MQTT_TOPIC)
MQTT_TOPIC_LANE2 = getattr(globals(), 'MQTT_TOPIC_LANE2', MQTT_TOPIC)

# Topic untuk checkpoint (untuk menerima checkpoint times dari simulasi)
# Menggunakan format yang sama dengan simulasi
if "/timer/" in MQTT_TOPIC:
    MQTT_TOPIC_CHECKPOINT = MQTT_TOPIC.replace("/timer/", "/checkpoint/")
else:
    MQTT_TOPIC_CHECKPOINT = f"{MQTT_TOPIC}/checkpoint"

# Topic checkpoint untuk setiap lintasan (untuk kompatibilitas)
MQTT_TOPIC_CHECKPOINT_LANE1 = MQTT_TOPIC_LANE1.replace("/timer/", "/checkpoint/") if "/timer/" in MQTT_TOPIC_LANE1 else f"{MQTT_TOPIC_LANE1}/checkpoint"
MQTT_TOPIC_CHECKPOINT_LANE2 = MQTT_TOPIC_LANE2.replace("/timer/", "/checkpoint/") if "/timer/" in MQTT_TOPIC_LANE2 else f"{MQTT_TOPIC_LANE2}/checkpoint"

def on_connect(client, userdata, flags, rc):
    """Callback ketika terhubung ke MQTT broker"""
    print(f"Terhubung ke MQTT broker {MQTT_BROKER} dengan code: {rc}")
    if rc == 0:
        print("✅ Koneksi MQTT berhasil!")
        # Subscribe ke topic untuk kedua lintasan
        client.subscribe(MQTT_TOPIC_LANE1)
        client.subscribe(MQTT_TOPIC_LANE2)
        # Subscribe ke topic checkpoint (untuk menerima data dari simulasi)
        client.subscribe(MQTT_TOPIC_CHECKPOINT)
        client.subscribe(MQTT_TOPIC_CHECKPOINT_LANE1)
        client.subscribe(MQTT_TOPIC_CHECKPOINT_LANE2)
        print(f"📡 Subscribed ke topic Lintasan 1: {MQTT_TOPIC_LANE1}")
        print(f"📡 Subscribed ke topic Lintasan 2: {MQTT_TOPIC_LANE2}")
        print(f"📡 Subscribed ke checkpoint topic: {MQTT_TOPIC_CHECKPOINT}")
        print(f"📡 Subscribed ke checkpoint Lintasan 1: {MQTT_TOPIC_CHECKPOINT_LANE1}")
        print(f"📡 Subscribed ke checkpoint Lintasan 2: {MQTT_TOPIC_CHECKPOINT_LANE2}")
    else:
        print(f"❌ Gagal koneksi MQTT dengan code: {rc}")

def on_message(client, userdata, msg):
    """Callback ketika menerima pesan MQTT"""
    global lanes
    
    message = msg.payload.decode('utf-8').strip()
    topic = msg.topic
    
    # Cek apakah ini pesan checkpoint dari simulasi
    is_checkpoint_topic = (topic == MQTT_TOPIC_CHECKPOINT or 
                          topic == MQTT_TOPIC_CHECKPOINT_LANE1 or 
                          topic == MQTT_TOPIC_CHECKPOINT_LANE2)
    
    if is_checkpoint_topic:
        # Handle pesan checkpoint dari simulasi
        try:
            checkpoint_data = json.loads(message)
            checkpoint_lane = checkpoint_data.get('lane')
            checkpoint_distance = checkpoint_data.get('checkpoint')
            checkpoint_time = checkpoint_data.get('time')
            checkpoint_timestamp = checkpoint_data.get('timestamp', time.time())
            
            if checkpoint_lane and checkpoint_lane in lanes:
                lane = lanes[checkpoint_lane]
                
                # Simpan data checkpoint
                lane.checkpoint_times[checkpoint_distance] = checkpoint_time
                lane.checkpoint_data[checkpoint_distance] = {
                    "time": checkpoint_time,
                    "timestamp": checkpoint_timestamp
                }
                
                print(f"✅ Checkpoint {checkpoint_distance}m untuk Lintasan {checkpoint_lane}: {checkpoint_time:.2f}s (dari simulasi)")
            else:
                print(f"⚠️ Checkpoint data tidak valid: lane={checkpoint_lane}, checkpoint={checkpoint_distance}")
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parsing checkpoint data: {message}, Error: {e}")
        return
    
    # Tentukan lintasan berdasarkan pesan MQTT untuk start/stop
    # "start1" dan "stop1" → Lintasan 1
    # "start2" dan "stop2" → Lintasan 2
    lane_num = None
    
    # Identifikasi lintasan dari pesan
    if message == "start1" or message == "stop1":
        lane_num = 1
    elif message == "start2" or message == "stop2":
        lane_num = 2
    else:
        # Jika topic berbeda, gunakan topic untuk identifikasi
        if MQTT_TOPIC_LANE1 != MQTT_TOPIC_LANE2:
            if topic == MQTT_TOPIC_LANE1:
                lane_num = 1
            elif topic == MQTT_TOPIC_LANE2:
                lane_num = 2
    
    # Jika tidak bisa diidentifikasi, skip pesan
    if lane_num is None or lane_num not in lanes:
        print(f"⚠️ Pesan tidak dikenal dari topic {topic}: {message}")
        return
    
    lane = lanes[lane_num]
    
    print(f"📨 Pesan diterima dari topic {topic} (Lintasan {lane_num}): {message}")
    
    # Handle pesan "start1" dari timerstart lintasan 1
    if message == "start1":
        if not lane.timer_running:
            lane.timer_running = True
            lane.start_time = datetime.now()
            lane.elapsed_time = timedelta(0)
            lane.lap_count = 0
            lane.finished = False
            lane.checkpoint_times = {}  # Reset checkpoint times
            lane.checkpoint_data = {}    # Reset checkpoint data
            print(f"🏊‍♂️ Lintasan {lane_num} - Timer STARTED")
        else:
            # Lap time (jika timer sudah running)
            if lane.start_time:
                current_time = datetime.now()
                lane.last_lap_time = current_time - lane.start_time
                lane.lap_count += 1
                print(f"🏁 Lintasan {lane_num} - Lap {lane.lap_count}: {lane.last_lap_time}")
    
    # Handle pesan "start2" dari timerstart lintasan 2
    elif message == "start2":
        if not lane.timer_running:
            lane.timer_running = True
            lane.start_time = datetime.now()
            lane.elapsed_time = timedelta(0)
            lane.lap_count = 0
            lane.finished = False
            lane.checkpoint_times = {}  # Reset checkpoint times
            lane.checkpoint_data = {}    # Reset checkpoint data
            print(f"🏊‍♂️ Lintasan {lane_num} - Timer STARTED")
        else:
            # Lap time (jika timer sudah running)
            if lane.start_time:
                current_time = datetime.now()
                lane.last_lap_time = current_time - lane.start_time
                lane.lap_count += 1
                print(f"🏁 Lintasan {lane_num} - Lap {lane.lap_count}: {lane.last_lap_time}")
    
    # Handle pesan "stop1" dari timerstop lintasan 1
    elif message == "stop1":
        if lane.timer_running:
            lane.timer_running = False
            lane.finished = True
            if lane.start_time:
                lane.elapsed_time = datetime.now() - lane.start_time
            print(f"⏹️ Lintasan {lane_num} - Timer STOPPED. Total time: {lane.elapsed_time}")
    
    # Handle pesan "stop2" dari timerstop lintasan 2
    elif message == "stop2":
        if lane.timer_running:
            lane.timer_running = False
            lane.finished = True
            if lane.start_time:
                lane.elapsed_time = datetime.now() - lane.start_time
            print(f"⏹️ Lintasan {lane_num} - Timer STOPPED. Total time: {lane.elapsed_time}")
    
    # Handle pesan "reset" manual
    elif message == "reset":
        lane.timer_running = False
        lane.start_time = None
        lane.elapsed_time = timedelta(0)
        lane.last_lap_time = None
        lane.lap_count = 0
        lane.finished = False
        lane.checkpoint_times = {}
        lane.checkpoint_data = {}
        print(f"🔄 Lintasan {lane_num} - Timer di-reset manual")

def on_disconnect(client, userdata, rc):
    """Callback ketika terputus dari MQTT broker"""
    print(f"🔌 Terputus dari MQTT broker {MQTT_BROKER} dengan code: {rc}")

def update_timer():
    """Thread untuk update timer secara realtime untuk semua lintasan"""
    global lanes
    
    while True:
        for lane_num, lane in lanes.items():
            if lane.timer_running and lane.start_time:
                lane.elapsed_time = datetime.now() - lane.start_time
        time.sleep(TIMER_UPDATE_INTERVAL)

def start_mqtt_client():
    """Start MQTT client dalam thread terpisah"""
    client = mqtt.Client(MQTT_CLIENT_ID + "_web_2lanes_v2")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        print(f"🔗 Menghubungkan ke MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"❌ Error koneksi MQTT ke {MQTT_BROKER}: {e}")

@app.route('/')
def index():
    """Halaman utama web interface"""
    return render_template('index.html')

@app.route('/api/timer')
def get_timer_data():
    """API endpoint untuk data timer semua lintasan (AJAX)"""
    global lanes
    
    result = {}
    for lane_num, lane in lanes.items():
        # Format waktu untuk display
        if lane.timer_running and lane.start_time:
            current_elapsed = datetime.now() - lane.start_time
            display_time = str(current_elapsed).split('.')[0]  # Hapus microseconds
        else:
            display_time = str(lane.elapsed_time).split('.')[0]
        
        # Format lap time
        lap_display = ""
        if lane.last_lap_time:
            lap_display = str(lane.last_lap_time).split('.')[0]
        
        # Format checkpoint times untuk API response
        checkpoint_times_formatted = {}
        for checkpoint_distance, checkpoint_time in lane.checkpoint_times.items():
            checkpoint_times_formatted[checkpoint_distance] = {
                "time": checkpoint_time,
                "display": f"{checkpoint_time:.2f}s"
            }
            # Tambahkan data lengkap jika ada
            if checkpoint_distance in lane.checkpoint_data:
                checkpoint_times_formatted[checkpoint_distance].update(lane.checkpoint_data[checkpoint_distance])
        
        result[f'lane_{lane_num}'] = {
            'running': lane.timer_running,
            'time': display_time,
            'lap_count': lane.lap_count,
            'lap_time': lap_display,
            'finished': lane.finished,
            'checkpoint_times': checkpoint_times_formatted,
            'checkpoint_count': len(lane.checkpoint_times)
        }
    
    result['broker'] = MQTT_BROKER
    result['checkpoint_source'] = 'simulation'
    return jsonify(result)

@app.route('/api/timer/<int:lane_num>')
def get_timer_data_lane(lane_num):
    """API endpoint untuk data timer lintasan tertentu"""
    global lanes
    
    if lane_num not in lanes:
        return jsonify({'error': 'Lane not found'}), 404
    
    lane = lanes[lane_num]
    
    # Format waktu untuk display
    if lane.timer_running and lane.start_time:
        current_elapsed = datetime.now() - lane.start_time
        display_time = str(current_elapsed).split('.')[0]
    else:
        display_time = str(lane.elapsed_time).split('.')[0]
    
    # Format lap time
    lap_display = ""
    if lane.last_lap_time:
        lap_display = str(lane.last_lap_time).split('.')[0]
    
    # Format checkpoint times untuk API response
    checkpoint_times_formatted = {}
    for checkpoint_distance, checkpoint_time in lane.checkpoint_times.items():
        checkpoint_times_formatted[checkpoint_distance] = {
            "time": checkpoint_time,
            "display": f"{checkpoint_time:.2f}s"
        }
        # Tambahkan data lengkap jika ada
        if checkpoint_distance in lane.checkpoint_data:
            checkpoint_times_formatted[checkpoint_distance].update(lane.checkpoint_data[checkpoint_distance])
    
    return jsonify({
        'lane': lane_num,
        'running': lane.timer_running,
        'time': display_time,
        'lap_count': lane.lap_count,
        'lap_time': lap_display,
        'finished': lane.finished,
        'checkpoint_times': checkpoint_times_formatted,
        'checkpoint_count': len(lane.checkpoint_times),
        'broker': MQTT_BROKER,
        'checkpoint_source': 'simulation'
    })

@app.route('/api/reset')
def reset_timer():
    """API endpoint untuk reset semua timer"""
    global lanes
    
    for lane_num, lane in lanes.items():
        lane.timer_running = False
        lane.start_time = None
        lane.elapsed_time = timedelta(0)
        lane.last_lap_time = None
        lane.lap_count = 0
        lane.finished = False
        lane.checkpoint_times = {}
        lane.checkpoint_data = {}
    
    print("🔄 Semua timer di-reset")
    return jsonify({'status': 'reset', 'lanes': [1, 2]})

@app.route('/api/reset/<int:lane_num>')
def reset_timer_lane(lane_num):
    """API endpoint untuk reset timer lintasan tertentu"""
    global lanes
    
    if lane_num not in lanes:
        return jsonify({'error': 'Lane not found'}), 404
    
    lane = lanes[lane_num]
    lane.timer_running = False
    lane.start_time = None
    lane.elapsed_time = timedelta(0)
    lane.last_lap_time = None
    lane.lap_count = 0
    lane.finished = False
    lane.checkpoint_times = {}
    lane.checkpoint_data = {}
    
    print(f"🔄 Timer Lintasan {lane_num} di-reset")
    return jsonify({'status': 'reset', 'lane': lane_num})

@app.route('/api/broker-info')
def get_broker_info():
    """API endpoint untuk informasi broker"""
    return jsonify(BROKER_INFO)

@app.route('/api/checkpoints/<int:lane_num>')
def get_checkpoints(lane_num):
    """API endpoint untuk mendapatkan data checkpoint lintasan tertentu"""
    global lanes
    
    if lane_num not in lanes:
        return jsonify({'error': 'Lane not found'}), 404
    
    lane = lanes[lane_num]
    
    # Format checkpoint data
    checkpoints = []
    for checkpoint_distance in sorted(lane.checkpoint_times.keys()):
        checkpoint_time = lane.checkpoint_times[checkpoint_distance]
        checkpoint_info = {
            "distance": checkpoint_distance,
            "time": checkpoint_time,
            "display": f"{checkpoint_time:.2f}s"
        }
        if checkpoint_distance in lane.checkpoint_data:
            checkpoint_info.update(lane.checkpoint_data[checkpoint_distance])
        checkpoints.append(checkpoint_info)
    
    return jsonify({
        'lane': lane_num,
        'checkpoints': checkpoints,
        'count': len(checkpoints)
    })

@app.route('/api/<int:lane_num>/checkpoint/<int:checkpoint_num>', methods=['POST'])
def set_checkpoint(lane_num, checkpoint_num):
    """API endpoint untuk set checkpoint lintasan tertentu
    checkpoint_num=1 berarti 10m, checkpoint_num=2 berarti 20m, dst.
    """
    global lanes
    
    if lane_num not in lanes:
        return jsonify({'error': 'Lane not found'}), 404
    
    lane = lanes[lane_num]
    
    # Validasi: timer harus sedang berjalan
    if not lane.timer_running or not lane.start_time:
        return jsonify({
            'error': 'Timer tidak sedang berjalan',
            'lane': lane_num,
            'timer_running': lane.timer_running
        }), 400
    
    # Hitung checkpoint distance (checkpoint_num * 10 meter)
    checkpoint_distance = checkpoint_num * 10
    
    # Hitung waktu yang sudah dilewati dari start_time
    current_time = datetime.now()
    elapsed = current_time - lane.start_time
    checkpoint_time_seconds = elapsed.total_seconds()
    checkpoint_timestamp = time.time()
    
    # Simpan data checkpoint
    lane.checkpoint_times[checkpoint_distance] = checkpoint_time_seconds
    lane.checkpoint_data[checkpoint_distance] = {
        "time": checkpoint_time_seconds,
        "timestamp": checkpoint_timestamp
    }
    
    print(f"✅ Checkpoint {checkpoint_distance}m untuk Lintasan {lane_num}: {checkpoint_time_seconds:.2f}s (dari API)")
    
    return jsonify({
        'status': 'success',
        'lane': lane_num,
        'checkpoint': checkpoint_num,
        'distance': checkpoint_distance,
        'time': checkpoint_time_seconds,
        'display': f"{checkpoint_time_seconds:.2f}s",
        'timestamp': checkpoint_timestamp
    })

if __name__ == '__main__':
    print("🏊‍♂️ Swim Timer Web Application - 2 Lintasan (dengan Checkpoint dari Simulasi)")
    print(f"🌐 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📡 Topic Lintasan 1: {MQTT_TOPIC_LANE1}")
    print(f"📡 Topic Lintasan 2: {MQTT_TOPIC_LANE2}")
    print(f"📡 Topic Checkpoint: {MQTT_TOPIC_CHECKPOINT}")
    print("-" * 50)
    
    # Start MQTT client dalam thread terpisah
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()
    
    # Start timer update thread
    timer_thread = threading.Thread(target=update_timer, daemon=True)
    timer_thread.start()
    
    print("🚀 Web interface akan tersedia di: http://localhost:5000")
    print("📊 API Endpoints:")
    print("   - GET /api/timer - Data semua lintasan")
    print("   - GET /api/timer/1 - Data lintasan 1")
    print("   - GET /api/timer/2 - Data lintasan 2")
    print("   - GET /api/checkpoints/1 - Checkpoint lintasan 1")
    print("   - GET /api/checkpoints/2 - Checkpoint lintasan 2")
    print("   - POST /api/<lane>/checkpoint/<num> - Set checkpoint (num=1=10m, num=2=20m, dst)")
    print("   - POST /api/reset - Reset semua lintasan")
    print("   - POST /api/reset/1 - Reset lintasan 1")
    print("   - POST /api/reset/2 - Reset lintasan 2")
    
    # Start Flask web server
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)

