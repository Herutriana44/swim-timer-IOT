import cv2
import mediapipe as mp
import time
import requests
from typing import Dict, Optional

# === Konfigurasi API ===
API_BASE_URL = "http://localhost:5000"  # URL dari swim timer web application
current_lane = 1  # Lintasan aktif saat ini (1 atau 2) - bisa diubah dengan keyboard
ENABLE_API = True  # Set False untuk disable API calls
API_TIMEOUT = 2  # Timeout untuk API request (detik)

# === Mediapipe initialization ===
mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5 
)

# === OpenCV camera ===
cap = cv2.VideoCapture(0)

# === Define areas untuk setiap lane (x1, y1, x2, y2) ===
# Area diperkecil dan dipisah untuk Lane 1 (kiri) dan Lane 2 (kanan)
# Setiap lane memiliki 5 area checkpoint sendiri
LANE_AREAS = {
    1: {  # Lane 1 - Bagian Kiri
        "area1": (10, 50, 120, 120),    # 10m - lebih kecil
        "area2": (10, 130, 120, 200),  # 20m
        "area3": (10, 210, 120, 280),  # 30m
        "area4": (10, 290, 120, 360),  # 40m
        "area5": (10, 370, 120, 440),  # 50m
    },
    2: {  # Lane 2 - Bagian Kanan
        "area1": (130, 50, 240, 120),   # 10m - lebih kecil
        "area2": (130, 130, 240, 200),  # 20m
        "area3": (130, 210, 240, 280),  # 30m
        "area4": (130, 290, 240, 360),  # 40m
        "area5": (130, 370, 240, 440),  # 50m
    }
}

# === Mapping area ke checkpoint number ===
# area1 = checkpoint 1 (10m), area2 = checkpoint 2 (20m), dst.
AREA_TO_CHECKPOINT = {
    "area1": 1,  # 10 meter
    "area2": 2,  # 20 meter
    "area3": 3,  # 30 meter
    "area4": 4,  # 40 meter
    "area5": 5,  # 50 meter
}

# === Tracking untuk debouncing (mencegah multiple API calls) ===
# Tracking terpisah untuk setiap lintasan
lane_tracking: Dict[int, Dict[str, any]] = {
    1: {
        'last_triggered_area': None,
        'last_triggered_time': 0.0
    },
    2: {
        'last_triggered_area': None,
        'last_triggered_time': 0.0
    }
}
TRIGGER_COOLDOWN = 2.0  # Cooldown dalam detik sebelum bisa trigger checkpoint yang sama lagi

# === Print konfigurasi saat program dimulai ===
print("=" * 50)
print("🏊 Finger Detection - Swim Timer Checkpoint API (2 Lintasan)")
print("=" * 50)
print(f"API Base URL: {API_BASE_URL}")
print(f"Lintasan Aktif: {current_lane}")
print(f"API Enabled: {ENABLE_API}")
print(f"Trigger Cooldown: {TRIGGER_COOLDOWN}s")
print("\nArea Mapping (Area diperkecil dan dipisah per lane):")
for lane_num in [1, 2]:
    print(f"  Lane {lane_num}:")
    for area, checkpoint in AREA_TO_CHECKPOINT.items():
        distance = checkpoint * 10
        if lane_num in LANE_AREAS and area in LANE_AREAS[lane_num]:
            coords = LANE_AREAS[lane_num][area]
            print(f"    {area} → Checkpoint {checkpoint} ({distance}m) - Koordinat: {coords}")
print("\n" + "=" * 50)
if ENABLE_API:
    print(f"✅ API Checkpoint aktif - checkpoint akan dikirim ke {API_BASE_URL}")
    print("⚠️ Pastikan swim timer web application sedang berjalan!")
else:
    print("⚠️ API Checkpoint tidak aktif (ENABLE_API = False)")
print("=" * 50)
print("\nKontrol Keyboard:")
print("  - Tekan '1' untuk switch ke Lintasan 1")
print("  - Tekan '2' untuk switch ke Lintasan 2")
print("  - Tekan ESC untuk keluar")
print("=" * 50)
print()

# === Visual feedback ===
feedback_messages: Dict[str, tuple] = {}  # {area_name: (message, timestamp)}

def check_area(x, y, lane_num: int):
    """Cek apakah koordinat berada di area tertentu untuk lane tertentu"""
    if lane_num not in LANE_AREAS:
        return {}
    
    areas = LANE_AREAS[lane_num]
    result = {a: False for a in areas}
    for area_name, (x1, y1, x2, y2) in areas.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            result[area_name] = True
    return result

def send_checkpoint_api(lane_num: int, checkpoint_num: int) -> bool:
    """
    Kirim checkpoint ke API swim timer
    
    Args:
        lane_num: Nomor lintasan (1 atau 2)
        checkpoint_num: Nomor checkpoint (1=10m, 2=20m, dst.)
    
    Returns:
        True jika berhasil, False jika gagal
    """
    if not ENABLE_API:
        return False
    
    url = f"{API_BASE_URL}/api/{lane_num}/checkpoint/{checkpoint_num}"
    
    try:
        response = requests.post(url, timeout=API_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            distance = checkpoint_num * 10
            time_display = data.get('display', 'N/A')
            print(f"✅ Checkpoint {distance}m untuk Lintasan {lane_num} berhasil dikirim: {time_display}")
            return True
        elif response.status_code == 400:
            error_data = response.json()
            error_msg = error_data.get('error', 'Unknown error')
            print(f"⚠️ Gagal mengirim checkpoint: {error_msg}")
            print(f"   Pastikan timer sedang berjalan untuk lintasan {lane_num}")
            return False
        else:
            print(f"⚠️ Gagal mengirim checkpoint: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Tidak bisa terhubung ke API server di {API_BASE_URL}")
        print(f"   Pastikan swim timer web application sedang berjalan")
        return False
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout saat mengirim checkpoint ke API")
        return False
    except Exception as e:
        print(f"❌ Error saat mengirim checkpoint: {e}")
        return False

def set_current_lane(lane_num: int):
    """
    Set lintasan aktif saat ini
    
    Args:
        lane_num: Nomor lintasan (1 atau 2)
    """
    global current_lane
    if lane_num in [1, 2]:
        current_lane = lane_num
        print(f"🔄 Switched to Lintasan {lane_num}")

def get_current_lane() -> int:
    """
    Get lintasan aktif saat ini
    
    Returns:
        Nomor lintasan aktif (1 atau 2)
    """
    return current_lane

def trigger_checkpoint(area_name: str, lane_num: int):
    """
    Trigger checkpoint jika area terdeteksi dan cooldown sudah selesai
    
    Args:
        area_name: Nama area yang terdeteksi (area1, area2, dst.)
        lane_num: Nomor lintasan (1 atau 2)
    """
    global lane_tracking
    
    current_time = time.time()
    tracking = lane_tracking[lane_num]
    
    # Cek apakah ini area yang sama dan masih dalam cooldown untuk lintasan ini
    if area_name == tracking['last_triggered_area']:
        time_since_last = current_time - tracking['last_triggered_time']
        if time_since_last < TRIGGER_COOLDOWN:
            return  # Masih dalam cooldown, skip
    
    # Cek apakah area memiliki mapping checkpoint
    if area_name not in AREA_TO_CHECKPOINT:
        return
    
    checkpoint_num = AREA_TO_CHECKPOINT[area_name]
    distance = checkpoint_num * 10
    
    # Kirim checkpoint ke API
    success = send_checkpoint_api(lane_num, checkpoint_num)
    
    # Update tracking untuk lintasan ini
    tracking['last_triggered_area'] = area_name
    tracking['last_triggered_time'] = current_time
    
    # Tampilkan visual feedback dengan info lintasan
    feedback_key = f"lane{lane_num}_{area_name}"
    if success:
        feedback_messages[feedback_key] = (f"✓ L{lane_num}: {distance}m sent!", current_time + 1.5)
    else:
        feedback_messages[feedback_key] = (f"✗ L{lane_num}: Failed {distance}m", current_time + 1.5)


while True:
    ret, frame = cap.read()
    if not ret:
        print("Error reading camera")
        break

    h, w, _ = frame.shape

    # Convert to RGB for mediapipe
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    finger_x = None
    finger_y = None

    if results.multi_hand_landmarks:
        for handLms in results.multi_hand_landmarks:
            # Draw hand landmarks
            mp_drawing.draw_landmarks(frame, handLms, mp_hands.HAND_CONNECTIONS)

            # index finger tip = landmark 8
            index_tip = handLms.landmark[8]
            finger_x = int(index_tip.x * w)
            finger_y = int(index_tip.y * h)

            # Draw point
            cv2.circle(frame, (finger_x, finger_y), 10, (0, 255, 255), -1)
    
    # Draw all areas on screen dengan informasi checkpoint untuk kedua lane
    current_time = time.time()
    active_lane = get_current_lane()  # Baca lintasan aktif sekali per frame
    
    # Gambar area untuk kedua lane bersebelahan
    for lane_num in [1, 2]:
        if lane_num not in LANE_AREAS:
            continue
            
        areas = LANE_AREAS[lane_num]
        is_active_lane = (lane_num == active_lane)
        
        for name, (x1, y1, x2, y2) in areas.items():
            # Tentukan warna berdasarkan lane dan feedback
            if is_active_lane:
                color = (255, 0, 0)  # Biru untuk lane aktif
                thickness = 2
            else:
                color = (100, 100, 100)  # Abu-abu untuk lane tidak aktif
                thickness = 1
            
            # Cek feedback untuk lane ini
            feedback_key = f"lane{lane_num}_{name}"
            if feedback_key in feedback_messages:
                msg, expiry_time = feedback_messages[feedback_key]
                if current_time < expiry_time:
                    if is_active_lane:
                        color = (0, 255, 0)  # Hijau untuk success lane aktif
                        thickness = 3
                    else:
                        color = (0, 255, 255)  # Kuning untuk success lane tidak aktif
                        thickness = 2
                else:
                    # Hapus feedback yang sudah expired
                    del feedback_messages[feedback_key]
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Tampilkan label lane dan checkpoint info
            checkpoint_num = AREA_TO_CHECKPOINT.get(name, 0)
            distance = checkpoint_num * 10
            area_label = f"L{lane_num} {name} ({distance}m)"
            font_scale = 0.4 if not is_active_lane else 0.5
            cv2.putText(frame, area_label, (x1 + 3, y1 + 15), cv2.FONT_HERSHEY_SIMPLEX, 
                        font_scale, color, 1 if not is_active_lane else 2)
            
            # Tampilkan feedback message jika ada
            if feedback_key in feedback_messages:
                msg, expiry_time = feedback_messages[feedback_key]
                if current_time < expiry_time:
                    cv2.putText(frame, msg, (x1 + 3, y1 + 30), cv2.FONT_HERSHEY_SIMPLEX, 
                                0.35, (0, 255, 0), 1)
        
        # Gambar garis pemisah antara lane
        if lane_num == 1:
            cv2.line(frame, (125, 0), (125, h), (255, 255, 255), 2)
            # Label Lane 1
            cv2.putText(frame, "LANE 1", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, (0, 255, 255) if active_lane == 1 else (150, 150, 150), 2)
        elif lane_num == 2:
            # Label Lane 2
            cv2.putText(frame, "LANE 2", (140, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, (255, 0, 255) if active_lane == 2 else (150, 150, 150), 2)

    # Handle keyboard input
    key = cv2.waitKey(1) & 0xFF
    if key == 27:  # ESC untuk keluar
        break
    elif key == ord('1'):  # Switch ke Lintasan 1
        if active_lane != 1:
            set_current_lane(1)
            active_lane = 1  # Update lokal untuk frame ini
    elif key == ord('2'):  # Switch ke Lintasan 2
        if active_lane != 2:
            set_current_lane(2)
            active_lane = 2  # Update lokal untuk frame ini

    if finger_x is not None:
        print(f"\nJari Terdeteksi di koordinat: ({finger_x}, {finger_y}) - Lintasan Aktif: {active_lane}")
        
        # Cek area untuk kedua lane
        detected_lane = None
        detected_area = None
        
        for lane_num in [1, 2]:
            area_status = check_area(finger_x, finger_y, lane_num)
            for area, status in area_status.items():
                print(f"Lane {lane_num} - {area}: {status}")
                if status:
                    detected_lane = lane_num
                    detected_area = area
                    break
            if detected_lane:
                break
        
        # Trigger checkpoint jika area terdeteksi
        if detected_lane and detected_area:
            trigger_checkpoint(detected_area, detected_lane)

    else:
        print("\nTidak ada tangan / jari terdeteksi")

    # Tampilkan status API di frame
    api_status = "API: ON" if ENABLE_API else "API: OFF"
    lane_info = f"Lintasan Aktif: {active_lane}"
    api_url_short = API_BASE_URL.replace("http://", "").replace("https://", "")
    
    # Background untuk status bar
    cv2.rectangle(frame, (5, h - 80), (300, h - 5), (0, 0, 0), -1)
    
    cv2.putText(frame, api_status, (10, h - 60), cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, (0, 255, 0) if ENABLE_API else (0, 0, 255), 2)
    
    # Tampilkan lintasan aktif dengan warna berbeda
    lane_color = (0, 255, 255) if active_lane == 1 else (255, 0, 255)  # Kuning untuk L1, Magenta untuk L2
    cv2.putText(frame, lane_info, (10, h - 40), cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, lane_color, 2)
    
    cv2.putText(frame, api_url_short, (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, (200, 200, 200), 1)
    
    # Tampilkan instruksi keyboard
    cv2.putText(frame, "Press '1' or '2' to switch lane", (w - 300, h - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

    cv2.imshow("Finger Detection - Swim Timer Checkpoint (2 Lanes)", frame)

cap.release()
cv2.destroyAllWindows()
