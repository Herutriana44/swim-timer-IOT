import cv2
import numpy as np
import mediapipe as mp
import time
import random
import threading
from typing import List, Dict, Optional, Tuple
from enum import Enum
import json
import os

# Import MQTT
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("Warning: paho-mqtt tidak tersedia. Install dengan: pip install paho-mqtt")

# Import configuration dari config_mosquitto.py
try:
    from config_mosquitto import *
except ImportError:
    # Default configuration jika config_mosquitto.py tidak ada
    MQTT_BROKER = "broker.emqx.io"
    MQTT_PORT = 1883
    MQTT_TOPIC = "renang/timer"
    MQTT_TOPIC_LANE1 = "renang/timer/lintasan1"
    MQTT_TOPIC_LANE2 = "renang/timer/lintasan2"
    MQTT_CLIENT_ID = "swim_detection"

# Konstanta
TRACK_LENGTH = 50  # meter
CHECKPOINT_DISTANCES = [10, 20, 30, 40, 50]  # meter
FPS = 30

# Warna (BGR untuk OpenCV)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (200, 100, 0)
LIGHT_BLUE = (230, 216, 173)
RED = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
ORANGE = (0, 165, 255)
GRAY = (128, 128, 128)
DARK_BLUE = (100, 50, 0)
CYAN = (255, 255, 0)

class Direction(Enum):
    """Arah pergerakan perenang"""
    LEFT_TO_RIGHT = "left_to_right"
    RIGHT_TO_LEFT = "right_to_left"
    TOP_TO_BOTTOM = "top_to_bottom"
    BOTTOM_TO_TOP = "bottom_to_top"

class Mode(Enum):
    """Mode operasi"""
    REAL = "real"  # Deteksi perenang dengan MediaPipe
    SIMULATION = "simulation"  # Simulasi dengan objek

class CheckpointBox:
    """Bounding box untuk checkpoint"""
    def __init__(self, checkpoint_distance: int, x: int, y: int, width: int, height: int):
        self.checkpoint_distance = checkpoint_distance
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    
    def get_center(self) -> Tuple[int, int]:
        """Dapatkan titik tengah bounding box"""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    def contains_point(self, point: Tuple[int, int]) -> bool:
        """Cek apakah point berada dalam bounding box"""
        px, py = point
        return self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height
    
    def to_dict(self) -> dict:
        """Convert ke dictionary untuk disimpan"""
        return {
            "checkpoint_distance": self.checkpoint_distance,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Buat dari dictionary"""
        return cls(
            data["checkpoint_distance"],
            data["x"],
            data["y"],
            data["width"],
            data["height"]
        )

class Swimmer:
    def __init__(self, name: str, color: tuple, lane_number: int, direction: Direction = Direction.LEFT_TO_RIGHT):
        self.name = name
        self.color = color
        self.lane_number = lane_number
        self.direction = direction
        self.position = 0.0  # posisi dalam meter (0-50)
        self.speed = random.uniform(0.8, 1.2)  # meter per detik (untuk simulation mode)
        self.finished = False
        self.start_time = None
        self.checkpoint_times: Dict[int, float] = {}  # {checkpoint_distance: waktu}
        self.finish_time = None
        self.current_position_pixel: Optional[Tuple[int, int]] = None  # Posisi pixel saat ini (untuk real mode)
        self.tracked = False  # Apakah perenang sedang ditrack
        
    def update_simulation(self, delta_time: float):
        """Update posisi perenang (untuk simulation mode)"""
        if not self.finished and self.start_time is not None:
            self.position += self.speed * delta_time
            if self.position >= TRACK_LENGTH:
                self.position = TRACK_LENGTH
                self.finished = True
                if self.finish_time is None:
                    self.finish_time = time.time() - self.start_time
    
    def update_real(self, position_pixel: Tuple[int, int], track_length_pixels: float):
        """Update posisi perenang berdasarkan deteksi (untuk real mode)"""
        self.current_position_pixel = position_pixel
        
        # Hitung posisi dalam meter berdasarkan arah
        if self.direction == Direction.LEFT_TO_RIGHT:
            # Asumsikan start di kiri, finish di kanan
            progress = position_pixel[0] / track_length_pixels
        elif self.direction == Direction.RIGHT_TO_LEFT:
            # Start di kanan, finish di kiri
            progress = (track_length_pixels - position_pixel[0]) / track_length_pixels
        elif self.direction == Direction.TOP_TO_BOTTOM:
            # Start di atas, finish di bawah
            progress = position_pixel[1] / track_length_pixels
        elif self.direction == Direction.BOTTOM_TO_TOP:
            # Start di bawah, finish di atas
            progress = (track_length_pixels - position_pixel[1]) / track_length_pixels
        else:
            progress = 0.0
        
        self.position = progress * TRACK_LENGTH
        
        if self.position >= TRACK_LENGTH:
            self.position = TRACK_LENGTH
            self.finished = True
            if self.finish_time is None and self.start_time is not None:
                self.finish_time = time.time() - self.start_time
    
    def check_checkpoint(self, checkpoint_distance: int, current_time: float):
        """Cek apakah perenang melewati checkpoint"""
        if checkpoint_distance not in self.checkpoint_times:
            if self.position >= checkpoint_distance:
                elapsed_time = current_time - self.start_time
                self.checkpoint_times[checkpoint_distance] = elapsed_time
                return True
        return False
    
    def start(self, start_time: float):
        """Mulai renang"""
        self.start_time = start_time
        self.finished = False
        self.position = 0.0
        self.checkpoint_times = {}
        self.finish_time = None

def load_rtsp_url(filepath: str = "rtsp_url.txt") -> Optional[str]:
    """Load RTSP URL dari file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                url = f.read().strip()
                if url:
                    print(f"✅ RTSP URL loaded dari {filepath}: {url}")
                    return url
        else:
            print(f"⚠️ File {filepath} tidak ditemukan")
    except Exception as e:
        print(f"❌ Error membaca RTSP URL dari {filepath}: {e}")
    return None

class SwimmingDetection:
    def __init__(self, mode: Mode = Mode.SIMULATION, camera_id: int = 0, 
                 frame_width: int = 1280, frame_height: int = 720, enable_mqtt: bool = True,
                 rtsp_file: str = "rtsp_url.txt", use_rtsp: bool = True):
        self.mode = mode
        self.camera_id = camera_id
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.rtsp_file = rtsp_file
        self.use_rtsp = use_rtsp
        self.rtsp_url = None
        
        # Setup MediaPipe untuk real mode
        self.mp_pose = None
        self.pose = None
        self.mp_drawing = None
        
        if mode == Mode.REAL:
            self.mp_pose = mp.solutions.pose
            self.pose = self.mp_pose.Pose(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.mp_drawing = mp.solutions.drawing_utils
            
            # Coba gunakan RTSP jika diminta
            if use_rtsp:
                self.rtsp_url = load_rtsp_url(rtsp_file)
                if self.rtsp_url:
                    print(f"📹 Menggunakan RTSP stream: {self.rtsp_url}")
                    # Gunakan RTSP dengan buffer size yang lebih besar untuk stabilitas
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    # Set buffer size untuk mengurangi latency
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                else:
                    print(f"⚠️ RTSP tidak tersedia, menggunakan camera ID {camera_id}")
                    self.cap = cv2.VideoCapture(camera_id)
            else:
                self.cap = cv2.VideoCapture(camera_id)
            
            if self.cap.isOpened():
                # Set frame properties
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
                # Set FPS jika memungkinkan
                self.cap.set(cv2.CAP_PROP_FPS, FPS)
                print(f"✅ Camera berhasil dibuka")
            else:
                print(f"❌ Warning: Cannot open camera, switching to SIMULATION mode")
                self.mode = Mode.SIMULATION
                self.cap = None
        else:
            self.cap = None
        
        # Setup perenang
        self.swimmers = [
            Swimmer("Perenang 1", RED, 1, Direction.LEFT_TO_RIGHT),
            Swimmer("Perenang 2", GREEN, 2, Direction.LEFT_TO_RIGHT)
        ]
        
        # Setup checkpoint boxes (default)
        self.checkpoint_boxes: List[CheckpointBox] = []
        self.setup_default_checkpoint_boxes()
        
        # State
        self.running = False
        self.start_time = None
        self.paused = False
        self.pause_start_time = None
        self.total_pause_time = 0.0
        
        # UI
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.7
        self.thickness = 2
        
        # Track length untuk real mode (dalam pixels)
        self.track_length_pixels = max(frame_width, frame_height)
        
        # MQTT setup
        self.enable_mqtt = enable_mqtt and MQTT_AVAILABLE
        self.mqtt_client = None
        self.mqtt_connected = False
        
        if self.enable_mqtt:
            self.setup_mqtt()
        
    def setup_default_checkpoint_boxes(self):
        """Setup default checkpoint boxes"""
        # Default: horizontal track (left to right)
        box_width = 100
        box_height = 50
        start_x = 100
        start_y = self.frame_height // 2 - box_height // 2
        
        for i, checkpoint in enumerate(CHECKPOINT_DISTANCES):
            x = start_x + int((checkpoint / TRACK_LENGTH) * (self.frame_width - start_x - 200))
            y = start_y
            self.checkpoint_boxes.append(
                CheckpointBox(checkpoint, x, y, box_width, box_height)
            )
    
    def load_checkpoint_boxes(self, filepath: str):
        """Load checkpoint boxes dari file JSON"""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                self.checkpoint_boxes = [CheckpointBox.from_dict(box) for box in data]
    
    def save_checkpoint_boxes(self, filepath: str):
        """Simpan checkpoint boxes ke file JSON"""
        data = [box.to_dict() for box in self.checkpoint_boxes]
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def detect_swimmer_position(self, frame: np.ndarray, swimmer: Swimmer) -> Optional[Tuple[int, int]]:
        """Deteksi posisi perenang menggunakan MediaPipe"""
        if self.pose is None:
            return None
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)
        
        if results.pose_landmarks:
            # Gunakan titik tengah tubuh (hip) sebagai posisi perenang
            landmarks = results.pose_landmarks.landmark
            
            # Hip landmarks (left_hip dan right_hip)
            left_hip = landmarks[self.mp_pose.PoseLandmark.LEFT_HIP]
            right_hip = landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP]
            
            # Konversi ke pixel coordinates
            h, w = frame.shape[:2]
            hip_x = int((left_hip.x + right_hip.x) / 2 * w)
            hip_y = int((left_hip.y + right_hip.y) / 2 * h)
            
            # Draw pose landmarks
            self.mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS
            )
            
            return (hip_x, hip_y)
        
        return None
    
    def draw_checkpoint_boxes(self, frame: np.ndarray):
        """Gambar checkpoint boxes"""
        for box in self.checkpoint_boxes:
            # Gambar bounding box
            cv2.rectangle(frame, 
                         (box.x, box.y), 
                         (box.x + box.width, box.y + box.height),
                         YELLOW, 2)
            
            # Label checkpoint
            label = f"{box.checkpoint_distance}m"
            label_size, _ = cv2.getTextSize(label, self.font, 0.5, 1)
            cv2.putText(frame, label,
                       (box.x + box.width // 2 - label_size[0] // 2,
                        box.y - 5),
                       self.font, 0.5, YELLOW, 1)
    
    def draw_swimmer_simulation(self, frame: np.ndarray, swimmer: Swimmer):
        """Gambar perenang untuk simulation mode"""
        if swimmer.start_time is None:
            return
        
        # Hitung posisi pixel berdasarkan direction
        if swimmer.direction == Direction.LEFT_TO_RIGHT:
            x = int(100 + (swimmer.position / TRACK_LENGTH) * (self.frame_width - 300))
            y = self.frame_height // 2 + (swimmer.lane_number - 1) * 100 - 50
        elif swimmer.direction == Direction.RIGHT_TO_LEFT:
            x = int(self.frame_width - 200 - (swimmer.position / TRACK_LENGTH) * (self.frame_width - 300))
            y = self.frame_height // 2 + (swimmer.lane_number - 1) * 100 - 50
        elif swimmer.direction == Direction.TOP_TO_BOTTOM:
            x = self.frame_width // 2 + (swimmer.lane_number - 1) * 100 - 50
            y = int(100 + (swimmer.position / TRACK_LENGTH) * (self.frame_height - 200))
        else:  # BOTTOM_TO_TOP
            x = self.frame_width // 2 + (swimmer.lane_number - 1) * 100 - 50
            y = int(self.frame_height - 100 - (swimmer.position / TRACK_LENGTH) * (self.frame_height - 200))
        
        # Gambar bounding box perenang
        box_size = 40
        cv2.rectangle(frame,
                     (x - box_size // 2, y - box_size // 2),
                     (x + box_size // 2, y + box_size // 2),
                     swimmer.color, -1)
        cv2.rectangle(frame,
                     (x - box_size // 2, y - box_size // 2),
                     (x + box_size // 2, y + box_size // 2),
                     BLACK, 2)
        
        # Nama perenang
        cv2.putText(frame, swimmer.name,
                   (x - 30, y - box_size // 2 - 10),
                   self.font, 0.5, swimmer.color, 1)
    
    def draw_swimmer_real(self, frame: np.ndarray, swimmer: Swimmer):
        """Gambar perenang untuk real mode"""
        if swimmer.current_position_pixel is None:
            return
        
        px, py = swimmer.current_position_pixel
        
        # Gambar bounding box di sekitar posisi terdeteksi
        box_size = 50
        cv2.rectangle(frame,
                     (px - box_size // 2, py - box_size // 2),
                     (px + box_size // 2, py + box_size // 2),
                     swimmer.color, 2)
        
        # Nama perenang
        cv2.putText(frame, swimmer.name,
                   (px - 30, py - box_size // 2 - 10),
                   self.font, 0.5, swimmer.color, 2)
    
    def draw_timer(self, frame: np.ndarray):
        """Gambar timer"""
        if self.start_time is not None and not self.paused:
            elapsed_time = time.time() - self.start_time - self.total_pause_time
            timer_text = f"Timer: {elapsed_time:.2f}s"
        else:
            timer_text = "Timer: 0.00s"
        
        cv2.putText(frame, timer_text,
                   (10, 30),
                   self.font, 1, BLACK, 2)
    
    def draw_checkpoint_times(self, frame: np.ndarray):
        """Gambar waktu checkpoint"""
        y_offset = 60
        x_offset = self.frame_width - 300
        
        # Header
        cv2.putText(frame, "Waktu Checkpoint",
                   (x_offset, y_offset),
                   self.font, 0.7, BLACK, 2)
        y_offset += 30
        
        for swimmer in self.swimmers:
            # Nama perenang
            cv2.putText(frame, swimmer.name,
                       (x_offset, y_offset),
                       self.font, 0.6, swimmer.color, 2)
            y_offset += 25
            
            # Waktu checkpoint
            for checkpoint in CHECKPOINT_DISTANCES:
                if checkpoint in swimmer.checkpoint_times:
                    checkpoint_time = swimmer.checkpoint_times[checkpoint]
                    time_text = f"  {checkpoint}m: {checkpoint_time:.2f}s"
                    cv2.putText(frame, time_text,
                               (x_offset, y_offset),
                               self.font, 0.5, BLACK, 1)
                else:
                    checkpoint_text = f"  {checkpoint}m: -"
                    cv2.putText(frame, checkpoint_text,
                               (x_offset, y_offset),
                               self.font, 0.5, GRAY, 1)
                y_offset += 20
            
            # Waktu finish
            if swimmer.finished and swimmer.finish_time is not None:
                finish_text = f"  FINISH: {swimmer.finish_time:.2f}s"
                cv2.putText(frame, finish_text,
                           (x_offset, y_offset),
                           self.font, 0.5, ORANGE, 2)
                y_offset += 20
            
            y_offset += 10
    
    def draw_controls(self, frame: np.ndarray):
        """Gambar instruksi kontrol"""
        controls = [
            "SPACE: Start/Pause",
            "R: Reset",
            "M: Toggle Mode",
            "C: Configure Checkpoints",
            "ESC: Quit"
        ]
        y_pos = self.frame_height - 120
        for control in controls:
            cv2.putText(frame, control,
                       (10, y_pos),
                       self.font, 0.5, BLACK, 1)
            y_pos += 25
    
    def draw_mode_indicator(self, frame: np.ndarray):
        """Gambar indikator mode"""
        mode_text = f"Mode: {self.mode.value.upper()}"
        cv2.putText(frame, mode_text,
                   (10, self.frame_height - 20),
                   self.font, 0.6, BLUE, 2)
        
        # Tampilkan status MQTT
        if self.enable_mqtt:
            mqtt_status = "MQTT: Connected" if self.mqtt_connected else "MQTT: Disconnected"
            cv2.putText(frame, mqtt_status,
                       (10, self.frame_height - 50),
                       self.font, 0.5, GREEN if self.mqtt_connected else RED, 1)
    
    def check_checkpoint_crossing(self, swimmer: Swimmer):
        """Cek apakah perenang melewati checkpoint box"""
        if swimmer.current_position_pixel is None:
            return
        
        current_time = time.time()
        for box in self.checkpoint_boxes:
            if box.contains_point(swimmer.current_position_pixel):
                swimmer.check_checkpoint(box.checkpoint_distance, current_time)
    
    def configure_checkpoints(self, frame: np.ndarray):
        """Mode konfigurasi checkpoint boxes"""
        print("Mode Konfigurasi Checkpoint")
        print("Klik dan drag untuk membuat/memindahkan checkpoint box")
        print("Tekan angka 1-5 untuk memilih checkpoint (10m-50m)")
        print("Tekan S untuk menyimpan, ESC untuk keluar")
        
        config_state = {
            'selected_checkpoint_idx': 0,
            'dragging': False,
            'drag_start': None
        }
        
        def mouse_callback(event, x, y, flags, param):
            state = param
            
            if event == cv2.EVENT_LBUTTONDOWN:
                # Cek apakah klik pada checkpoint box yang ada
                clicked_box = None
                for i, box in enumerate(self.checkpoint_boxes):
                    if box.contains_point((x, y)):
                        state['selected_checkpoint_idx'] = i
                        state['dragging'] = True
                        state['drag_start'] = (x, y)
                        clicked_box = i
                        break
                
                if clicked_box is None:
                    # Buat checkpoint box baru di posisi klik
                    box_width = 100
                    box_height = 50
                    idx = state['selected_checkpoint_idx']
                    self.checkpoint_boxes[idx] = CheckpointBox(
                        CHECKPOINT_DISTANCES[idx],
                        x - box_width // 2,
                        y - box_height // 2,
                        box_width,
                        box_height
                    )
                    state['dragging'] = True
                    state['drag_start'] = (x, y)
            
            elif event == cv2.EVENT_MOUSEMOVE and state['dragging']:
                dx = x - state['drag_start'][0]
                dy = y - state['drag_start'][1]
                idx = state['selected_checkpoint_idx']
                box = self.checkpoint_boxes[idx]
                box.x += dx
                box.y += dy
                state['drag_start'] = (x, y)
            
            elif event == cv2.EVENT_LBUTTONUP:
                state['dragging'] = False
        
        cv2.namedWindow("Swimming Detection")
        cv2.setMouseCallback("Swimming Detection", mouse_callback, config_state)
        
        while True:
            display_frame = frame.copy()
            self.draw_checkpoint_boxes(display_frame)
            
            # Highlight selected checkpoint
            idx = config_state['selected_checkpoint_idx']
            box = self.checkpoint_boxes[idx]
            cv2.rectangle(display_frame,
                         (box.x, box.y),
                         (box.x + box.width, box.y + box.height),
                         RED, 3)
            
            cv2.putText(display_frame, f"Selected: {box.checkpoint_distance}m",
                       (10, 30), self.font, 0.7, RED, 2)
            
            cv2.imshow("Swimming Detection", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('s'):
                self.save_checkpoint_boxes("checkpoint_boxes.json")
                print("Checkpoint boxes disimpan!")
                break
            elif key == 27:  # ESC
                break
            elif ord('1') <= key <= ord('5'):
                config_state['selected_checkpoint_idx'] = key - ord('1')
        
        cv2.setMouseCallback("Swimming Detection", lambda *args: None)
    
    def setup_mqtt(self):
        """Setup MQTT client"""
        if not MQTT_AVAILABLE:
            return
        
        try:
            self.mqtt_client = mqtt.Client(MQTT_CLIENT_ID + "_detection")
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            print(f"🔗 Menghubungkan ke MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"❌ Error setup MQTT: {e}")
            self.enable_mqtt = False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback ketika terhubung ke MQTT broker"""
        if rc == 0:
            self.mqtt_connected = True
            print("✅ Koneksi MQTT berhasil!")
            # Subscribe ke topic untuk kedua lintasan
            client.subscribe(MQTT_TOPIC_LANE1)
            client.subscribe(MQTT_TOPIC_LANE2)
            print(f"📡 Subscribed ke topic Lintasan 1: {MQTT_TOPIC_LANE1}")
            print(f"📡 Subscribed ke topic Lintasan 2: {MQTT_TOPIC_LANE2}")
        else:
            print(f"❌ Gagal koneksi MQTT dengan code: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """Callback ketika menerima pesan MQTT"""
        message = msg.payload.decode('utf-8').strip()
        topic = msg.topic
        
        print(f"📨 Pesan MQTT diterima dari {topic}: {message}")
        
        # Tentukan lintasan berdasarkan topic
        lane_num = None
        if topic == MQTT_TOPIC_LANE1:
            lane_num = 1
        elif topic == MQTT_TOPIC_LANE2:
            lane_num = 2
        elif "lintasan1" in topic.lower() or "lane1" in topic.lower():
            lane_num = 1
        elif "lintasan2" in topic.lower() or "lane2" in topic.lower():
            lane_num = 2
        
        if lane_num is None:
            # Jika topic tidak jelas, gunakan heuristik
            if message == "start2" or message == "start":
                # Cari lintasan yang tidak sedang running
                if not self.swimmers[0].start_time or not self.running:
                    lane_num = 1
                elif not self.swimmers[1].start_time or not self.running:
                    lane_num = 2
                else:
                    lane_num = 1  # Default
            else:
                lane_num = 1  # Default
        
        if lane_num and 1 <= lane_num <= len(self.swimmers):
            swimmer = self.swimmers[lane_num - 1]
            
            # Handle pesan start
            if message == "start2" or message == "start":
                if not self.running:
                    self.running = True
                    self.start_time = time.time()
                    for s in self.swimmers:
                        s.start(self.start_time)
                    print(f"🏊‍♂️ Deteksi STARTED dari MQTT (Lintasan {lane_num})")
                elif not swimmer.start_time:
                    swimmer.start(self.start_time)
                    print(f"🏊‍♂️ Perenang {lane_num} STARTED dari MQTT")
            
            # Handle pesan stop
            elif message == "stop":
                if self.running:
                    self.running = False
                    print(f"⏹️ Deteksi STOPPED dari MQTT")
            
            # Handle pesan reset
            elif message == "reset":
                self.reset()
                print(f"🔄 Deteksi RESET dari MQTT")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback ketika terputus dari MQTT broker"""
        self.mqtt_connected = False
        print(f"🔌 Terputus dari MQTT broker dengan code: {rc}")
    
    def publish_checkpoint(self, swimmer: Swimmer, checkpoint_distance: int, checkpoint_time: float):
        """Publish waktu checkpoint ke MQTT"""
        if not self.enable_mqtt or not self.mqtt_connected or not self.mqtt_client:
            return
        
        # Tentukan topic berdasarkan lintasan
        if swimmer.lane_number == 1:
            topic = MQTT_TOPIC_LANE1.replace("/timer/", "/checkpoint/") if "/timer/" in MQTT_TOPIC_LANE1 else f"{MQTT_TOPIC_LANE1}/checkpoint"
        else:
            topic = MQTT_TOPIC_LANE2.replace("/timer/", "/checkpoint/") if "/timer/" in MQTT_TOPIC_LANE2 else f"{MQTT_TOPIC_LANE2}/checkpoint"
        
        # Format pesan JSON
        message = json.dumps({
            "lane": swimmer.lane_number,
            "checkpoint": checkpoint_distance,
            "time": checkpoint_time,
            "timestamp": time.time()
        })
        
        try:
            self.mqtt_client.publish(topic, message)
            print(f"📤 Published checkpoint {checkpoint_distance}m untuk Lintasan {swimmer.lane_number}: {checkpoint_time:.2f}s")
        except Exception as e:
            print(f"❌ Error publish checkpoint: {e}")
    
    def update(self, frame: np.ndarray):
        """Update simulasi/deteksi"""
        if self.running and not self.paused:
            if self.mode == Mode.SIMULATION:
                # Simulation mode
                delta_time = 1.0 / FPS
                for swimmer in self.swimmers:
                    swimmer.update_simulation(delta_time)
                    
                    # Cek checkpoint
                    current_time = time.time()
                    for checkpoint in CHECKPOINT_DISTANCES:
                        if swimmer.check_checkpoint(checkpoint, current_time):
                            checkpoint_time = swimmer.checkpoint_times[checkpoint]
                            print(f"{swimmer.name} melewati checkpoint {checkpoint}m pada {checkpoint_time:.2f} detik")
                            # Publish checkpoint ke MQTT
                            self.publish_checkpoint(swimmer, checkpoint, checkpoint_time)
            
            else:
                # Real mode - deteksi perenang
                for swimmer in self.swimmers:
                    position = self.detect_swimmer_position(frame, swimmer)
                    if position:
                        swimmer.tracked = True
                        swimmer.update_real(position, self.track_length_pixels)
                        # Cek checkpoint crossing dan publish jika perlu
                        current_time = time.time()
                        for checkpoint in CHECKPOINT_DISTANCES:
                            if swimmer.check_checkpoint(checkpoint, current_time):
                                checkpoint_time = swimmer.checkpoint_times[checkpoint]
                                print(f"{swimmer.name} melewati checkpoint {checkpoint}m pada {checkpoint_time:.2f} detik")
                                # Publish checkpoint ke MQTT
                                self.publish_checkpoint(swimmer, checkpoint, checkpoint_time)
                    else:
                        swimmer.tracked = False
    
    def draw(self, frame: np.ndarray):
        """Gambar semua elemen"""
        # Gambar checkpoint boxes
        self.draw_checkpoint_boxes(frame)
        
        # Gambar perenang
        if self.mode == Mode.SIMULATION:
            for swimmer in self.swimmers:
                self.draw_swimmer_simulation(frame, swimmer)
        else:
            for swimmer in self.swimmers:
                self.draw_swimmer_real(frame, swimmer)
        
        # Gambar UI
        self.draw_timer(frame)
        self.draw_checkpoint_times(frame)
        self.draw_controls(frame)
        self.draw_mode_indicator(frame)
    
    def handle_events(self) -> bool:
        """Handle keyboard events"""
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27:  # ESC
            return False
        
        elif key == ord(' '):  # SPACE
            if not self.running:
                # Start
                self.running = True
                self.start_time = time.time()
                for swimmer in self.swimmers:
                    swimmer.start(self.start_time)
            else:
                # Pause/Resume
                if self.paused:
                    self.total_pause_time += time.time() - self.pause_start_time
                    self.paused = False
                else:
                    self.paused = True
                    self.pause_start_time = time.time()
        
        elif key == ord('r'):  # Reset
            self.reset()
        
        elif key == ord('m'):  # Toggle mode
            if self.mode == Mode.REAL:
                # Switch ke Simulation Mode
                self.mode = Mode.SIMULATION
                if self.pose:
                    self.pose.close()
                    self.pose = None
                if self.cap:
                    self.cap.release()
                    self.cap = None
                print("Switched to SIMULATION mode")
            else:
                # Switch ke Real Mode
                self.mode = Mode.REAL
                if self.cap:
                    self.cap.release()
                
                # Coba gunakan RTSP jika diminta
                if self.use_rtsp and not self.rtsp_url:
                    self.rtsp_url = load_rtsp_url(self.rtsp_file)
                
                if self.use_rtsp and self.rtsp_url:
                    print(f"📹 Menggunakan RTSP stream: {self.rtsp_url}")
                    self.cap = cv2.VideoCapture(self.rtsp_url)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                else:
                    self.cap = cv2.VideoCapture(self.camera_id)
                
                if not self.cap.isOpened():
                    print(f"Error: Cannot open camera")
                    self.mode = Mode.SIMULATION
                    self.cap = None
                else:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                    self.cap.set(cv2.CAP_PROP_FPS, FPS)
                    self.mp_pose = mp.solutions.pose
                    self.pose = self.mp_pose.Pose(
                        min_detection_confidence=0.5,
                        min_tracking_confidence=0.5
                    )
                    self.mp_drawing = mp.solutions.drawing_utils
                    print("Switched to REAL mode")
        
        elif key == ord('c'):  # Configure checkpoints
            if self.mode == Mode.REAL and self.cap:
                ret, frame = self.cap.read()
                if ret:
                    self.configure_checkpoints(frame)
            else:
                # Untuk simulation mode, buat frame kosong
                frame = np.ones((self.frame_height, self.frame_width, 3), dtype=np.uint8) * 255
                self.configure_checkpoints(frame)
        
        return True
    
    def reset(self):
        """Reset simulasi"""
        self.running = False
        self.start_time = None
        self.paused = False
        self.pause_start_time = None
        self.total_pause_time = 0.0
        
        for swimmer in self.swimmers:
            swimmer.position = 0.0
            swimmer.speed = random.uniform(0.8, 1.2)
            swimmer.finished = False
            swimmer.start_time = None
            swimmer.checkpoint_times = {}
            swimmer.finish_time = None
            swimmer.current_position_pixel = None
            swimmer.tracked = False
    
    def run(self):
        """Jalankan aplikasi"""
        print("Swimming Detection System")
        print("=" * 50)
        print(f"Mode: {self.mode.value}")
        print("Kontrol:")
        print("  SPACE: Start/Pause")
        print("  R: Reset")
        print("  M: Toggle Mode (Real/Simulation)")
        print("  C: Configure Checkpoint Boxes")
        print("  ESC: Quit")
        print("=" * 50)
        
        running = True
        
        try:
            while running:
                if self.mode == Mode.REAL:
                    if self.cap is None:
                        print("Error: Camera tidak tersedia")
                        break
                    
                    ret, frame = self.cap.read()
                    if not ret:
                        print("⚠️ Warning: Tidak dapat membaca frame dari camera")
                        # Coba reconnect jika menggunakan RTSP
                        if self.use_rtsp and self.rtsp_url:
                            print("🔄 Mencoba reconnect ke RTSP stream...")
                            self.cap.release()
                            time.sleep(1)  # Tunggu sebentar sebelum reconnect
                            self.cap = cv2.VideoCapture(self.rtsp_url)
                            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            if not self.cap.isOpened():
                                print("❌ Gagal reconnect, switching ke SIMULATION mode")
                                self.mode = Mode.SIMULATION
                                self.cap = None
                                continue
                        else:
                            print("Error: Tidak dapat membaca frame dari camera")
                            break
                else:
                    # Simulation mode - buat frame kosong
                    frame = np.ones((self.frame_height, self.frame_width, 3), dtype=np.uint8) * 255
                    
                    # Gambar track background
                    cv2.rectangle(frame, (50, 50), (self.frame_width - 50, self.frame_height - 50),
                                 LIGHT_BLUE, -1)
                    cv2.rectangle(frame, (50, 50), (self.frame_width - 50, self.frame_height - 50),
                                 DARK_BLUE, 3)
                
                # Update dan draw
                self.update(frame)
                self.draw(frame)
                
                # Tampilkan frame
                cv2.imshow("Swimming Detection", frame)
                
                # Handle events
                running = self.handle_events()
        
        except KeyboardInterrupt:
            print("\nProgram dihentikan oleh user")
        
        finally:
            # Cleanup
            if self.enable_mqtt and self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            if self.cap:
                self.cap.release()
            cv2.destroyAllWindows()
            if self.pose:
                self.pose.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Swimming Detection System")
    parser.add_argument("--mode", choices=["real", "simulation"], default="simulation",
                       help="Mode operasi: real atau simulation")
    parser.add_argument("--camera", type=int, default=0,
                       help="Camera ID untuk real mode")
    parser.add_argument("--width", type=int, default=1280,
                       help="Lebar frame")
    parser.add_argument("--height", type=int, default=720,
                       help="Tinggi frame")
    parser.add_argument("--checkpoints", type=str, default=None,
                       help="File JSON untuk load checkpoint boxes")
    parser.add_argument("--rtsp-file", type=str, default="rtsp_url.txt",
                       help="File yang berisi RTSP URL")
    parser.add_argument("--no-rtsp", action="store_true",
                       help="Jangan gunakan RTSP, gunakan camera ID saja")
    
    args = parser.parse_args()
    
    mode = Mode.REAL if args.mode == "real" else Mode.SIMULATION
    
    detection = SwimmingDetection(
        mode=mode,
        camera_id=args.camera,
        frame_width=args.width,
        frame_height=args.height,
        rtsp_file=args.rtsp_file,
        use_rtsp=not args.no_rtsp
    )
    
    if args.checkpoints:
        detection.load_checkpoint_boxes(args.checkpoints)
    
    detection.run()

