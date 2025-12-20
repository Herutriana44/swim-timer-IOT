import cv2
import mediapipe as mp
import time
import requests
import threading
import sys
import os
from typing import Dict, Optional
from datetime import datetime
from queue import Queue

# === Unbuffered output untuk mencegah terminal macet ===
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
os.environ['PYTHONUNBUFFERED'] = '1'

# === Konfigurasi API ===
API_BASE_URL = "http://localhost:5000"  # URL dari swim timer web application
current_lane = 1  # Lintasan aktif saat ini (1 atau 2) - bisa diubah dengan keyboard
ENABLE_API = True  # Set False untuk disable API calls
API_TIMEOUT = 1  # Timeout untuk API request (detik) - dikurangi untuk respons lebih cepat

# === Optimasi Performa ===
PRINT_DETECTION = False  # Set True untuk print setiap deteksi (bisa memperlambat)
SKIP_FRAMES = 1  # Skip setiap N frame untuk deteksi (0 = tidak skip, 1 = skip 1 frame)
frame_count = 0

# === Mediapipe Pose initialization ===
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# === Konfigurasi Video Source ===
# Pilih salah satu:
# - Untuk kamera USB: gunakan angka (0, 1, 2, dst.)
# - Untuk RTSP stream: gunakan string URL seperti "rtsp://user:pass@ip:port/stream"
# - Untuk file video: gunakan path ke file video
VIDEO_SOURCE = 0  # Default: kamera USB index 0
# VIDEO_SOURCE = "rtsp://admin:Kosanibunur123@192.168.137.153:554/live/ch00_0"  # Contoh RTSP
# VIDEO_SOURCE = "pose_record_20251202_173124.mp4"  # Contoh file video

# === OpenCV camera ===
# Gunakan cara sederhana seperti file lama yang sudah bekerja
print(f"📹 Membuka video source: {VIDEO_SOURCE}", flush=True)
cap = cv2.VideoCapture(VIDEO_SOURCE)

if not cap.isOpened():
    print(f"❌ Error: Tidak bisa membuka video source: {VIDEO_SOURCE}", flush=True)
    print("💡 Tips:", flush=True)
    print("   - Pastikan kamera terhubung dan tidak digunakan aplikasi lain", flush=True)
    print("   - Coba ubah VIDEO_SOURCE ke 1, 2, atau 3", flush=True)
    print("   - Untuk RTSP, pastikan URL dan kredensial benar", flush=True)
    sys.exit(1)

print(f"✅ Video source berhasil dibuka: {VIDEO_SOURCE}", flush=True)

# === Video recording (diinisialisasi setelah frame pertama) ===
video_writer = None
VIDEO_FPS = 25.0  # sesuaikan jika perlu

# === Define areas untuk setiap lane (x1, y1, x2, y2) ===
# Area diperkecil dan dipisah untuk Lane 1 (kiri) dan Lane 2 (kanan)
# Setiap lane memiliki 5 area checkpoint sendiri
LANE_AREAS = {
    1: {  # Lane 1
        "area1": (405, 299, 508, 345),
        "area2": (350, 355, 477, 408),
        "area3": (276, 421, 446, 489),
        "area4": (214, 502, 405, 580),
        "area5": (212, 596, 405, 665)
    },
    2: {  # Lane 2
        "area1": (830, 306, 1058, 345),
        "area2": (690, 355, 1051, 408),
        "area3": (659, 419, 1038, 491),
        "area4": (620, 504, 1025, 581),
        "area5": (622, 594, 1019, 665)
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
print("=" * 50, flush=True)
print("🏊 Pose Detection - Swim Timer Checkpoint API (2 Lintasan)", flush=True)
print("=" * 50, flush=True)
print(f"API Base URL: {API_BASE_URL}", flush=True)
print(f"Lintasan Aktif (awal): {current_lane}", flush=True)
print(f"API Enabled: {ENABLE_API}", flush=True)
print(f"Trigger Cooldown: {TRIGGER_COOLDOWN}s", flush=True)
print(f"Frame Skip: {SKIP_FRAMES}", flush=True)
print("\nArea Mapping (Area diperkecil dan dipisah per lane):", flush=True)
for lane_num in [1, 2]:
    print(f"  Lane {lane_num}:", flush=True)
    for area, checkpoint in AREA_TO_CHECKPOINT.items():
        distance = checkpoint * 10
        if lane_num in LANE_AREAS and area in LANE_AREAS[lane_num]:
            coords = LANE_AREAS[lane_num][area]
            print(f"    {area} → Checkpoint {checkpoint} ({distance}m) - Koordinat: {coords}", flush=True)
print("\n" + "=" * 50, flush=True)
if ENABLE_API:
    print(f"✅ API Checkpoint aktif - checkpoint akan dikirim ke {API_BASE_URL}", flush=True)
    print("⚠️ Pastikan swim timer web application sedang berjalan!", flush=True)
else:
    print("⚠️ API Checkpoint tidak aktif (ENABLE_API = False)", flush=True)
print("=" * 50, flush=True)
print("\nKontrol Keyboard:", flush=True)
print("  - Tekan '1' untuk switch ke Lintasan 1 (manual override)", flush=True)
print("  - Tekan '2' untuk switch ke Lintasan 2 (manual override)", flush=True)
print("  - Tekan 'q' atau ESC untuk berhenti", flush=True)
print("\nRekaman video akan dimulai otomatis dan berhenti saat program selesai.", flush=True)
print("=" * 50, flush=True)
print("🚀 Program dimulai...", flush=True)
print()

# === Visual feedback ===
feedback_messages: Dict[str, tuple] = {}  # {feedback_key: (message, timestamp)}

# === Thread-safe queue untuk API calls ===
api_queue = Queue()
api_thread_running = True


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


def send_checkpoint_api_worker(lane_num: int, checkpoint_num: int) -> bool:
    """
    Worker function untuk kirim checkpoint ke API swim timer (dipanggil di thread terpisah)

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
            if PRINT_DETECTION:
                print(f"✅ Checkpoint {distance}m untuk Lintasan {lane_num} berhasil dikirim: {time_display}", flush=True)
            return True
        elif response.status_code == 400:
            if PRINT_DETECTION:
                error_data = response.json()
                error_msg = error_data.get('error', 'Unknown error')
                print(f"⚠️ Gagal mengirim checkpoint: {error_msg}", flush=True)
                print(f"   Pastikan timer sedang berjalan untuk lintasan {lane_num}", flush=True)
            return False
        else:
            if PRINT_DETECTION:
                print(f"⚠️ Gagal mengirim checkpoint: HTTP {response.status_code}", flush=True)
            return False

    except requests.exceptions.ConnectionError:
        if PRINT_DETECTION:
            print(f"❌ Tidak bisa terhubung ke API server di {API_BASE_URL}", flush=True)
            print(f"   Pastikan swim timer web application sedang berjalan", flush=True)
        return False
    except requests.exceptions.Timeout:
        if PRINT_DETECTION:
            print(f"⏱️ Timeout saat mengirim checkpoint ke API", flush=True)
        return False
    except Exception as e:
        if PRINT_DETECTION:
            print(f"❌ Error saat mengirim checkpoint: {e}", flush=True)
        return False


def api_worker_thread():
    """Thread worker untuk memproses API calls dari queue"""
    global api_thread_running
    while api_thread_running:
        try:
            # Get item from queue dengan timeout
            item = api_queue.get(timeout=0.1)
            if item is None:
                continue
            lane_num, checkpoint_num, callback = item
            success = send_checkpoint_api_worker(lane_num, checkpoint_num)
            if callback:
                callback(success, lane_num, checkpoint_num)
            api_queue.task_done()
        except:
            continue


def send_checkpoint_api(lane_num: int, checkpoint_num: int, callback=None) -> bool:
    """
    Kirim checkpoint ke API swim timer (non-blocking via queue)

    Args:
        lane_num: Nomor lintasan (1 atau 2)
        checkpoint_num: Nomor checkpoint (1=10m, 2=20m, dst.)
        callback: Function callback(success, lane_num, checkpoint_num) untuk dipanggil setelah selesai

    Returns:
        True jika berhasil ditambahkan ke queue, False jika gagal
    """
    if not ENABLE_API:
        return False
    
    # Tambahkan ke queue untuk diproses di thread terpisah
    api_queue.put((lane_num, checkpoint_num, callback))
    return True


def set_current_lane(lane_num: int):
    """
    Set lintasan aktif saat ini (manual override)
    """
    global current_lane
    if lane_num in [1, 2]:
        current_lane = lane_num
        print(f"🔄 Switched to Lintasan {lane_num} (manual)", flush=True)


def get_current_lane() -> int:
    """Get lintasan aktif saat ini"""
    return current_lane


def trigger_checkpoint(area_name: str, lane_num: int):
    """
    Trigger checkpoint jika area terdeteksi dan cooldown sudah selesai
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

    # Update tracking untuk lintasan ini (sebelum API call)
    tracking['last_triggered_area'] = area_name
    tracking['last_triggered_time'] = current_time

    # Callback untuk update feedback setelah API call selesai
    def api_callback(success, lane, checkpoint):
        feedback_key = f"lane{lane}_{area_name}"
        if success:
            feedback_messages[feedback_key] = (f"✓ L{lane}: {distance}m sent!", time.time() + 1.5)
        else:
            feedback_messages[feedback_key] = (f"✗ L{lane}: Failed {distance}m", time.time() + 1.5)

    # Set feedback sementara (akan diupdate oleh callback)
    feedback_key = f"lane{lane_num}_{area_name}"
    feedback_messages[feedback_key] = (f"⏳ L{lane_num}: {distance}m...", current_time + 0.5)
    
    # Kirim checkpoint ke API (non-blocking dengan callback)
    send_checkpoint_api(lane_num, checkpoint_num, api_callback)


def get_pose_point(landmarks, image_width: int, image_height: int):
    """
    Ambil titik referensi dari pose untuk deteksi area.
    Di sini digunakan titik pinggang (mid-hip) sebagai posisi orang.
    Jika titik pinggang tidak tersedia, fallback ke bahu tengah.
    """
    if not landmarks:
        return None, None

    # Index landmark MediaPipe Pose:
    # 23: left_hip, 24: right_hip
    # 11: left_shoulder, 12: right_shoulder
    def get_xy(idx):
        lm = landmarks[idx]
        return int(lm.x * image_width), int(lm.y * image_height)

    try:
        # Coba gunakan pinggang terlebih dahulu
        hip_left = landmarks[23]
        hip_right = landmarks[24]
        hip_x = int((hip_left.x + hip_right.x) / 2 * image_width)
        hip_y = int((hip_left.y + hip_right.y) / 2 * image_height)
        return hip_x, hip_y
    except Exception:
        pass

    try:
        # Fallback ke bahu
        shoulder_left = landmarks[11]
        shoulder_right = landmarks[12]
        sh_x = int((shoulder_left.x + shoulder_right.x) / 2 * image_width)
        sh_y = int((shoulder_left.y + shoulder_right.y) / 2 * image_height)
        return sh_x, sh_y
    except Exception:
        return None, None
# === Start API worker thread ===
api_thread = threading.Thread(target=api_worker_thread, daemon=True)
api_thread.start()
print("✅ API worker thread dimulai", flush=True)

# === Variabel untuk error handling ===
consecutive_errors = 0
MAX_CONSECUTIVE_ERRORS = 10

try:
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                print(f"❌ Error: Gagal membaca frame {MAX_CONSECUTIVE_ERRORS} kali berturut-turut", flush=True)
                print("   Mencoba reconnect...", flush=True)
                # Coba reconnect
                cap.release()
                time.sleep(1)
                cap = cv2.VideoCapture(VIDEO_SOURCE)
                if not cap.isOpened():
                    print("❌ Gagal reconnect. Program dihentikan.", flush=True)
                    break
                consecutive_errors = 0
                print("✅ Reconnect berhasil", flush=True)
            else:
                # Skip frame yang error, coba lagi
                time.sleep(0.01)
            continue
        
        # Reset error counter jika berhasil membaca frame
        consecutive_errors = 0

        frame_count += 1
        h, w, _ = frame.shape

        # Inisialisasi VideoWriter setelah ukuran frame diketahui
        if video_writer is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pose_record_{ts}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            video_writer = cv2.VideoWriter(filename, fourcc, VIDEO_FPS, (w, h))
            if video_writer.isOpened():
                print(f"🎥 Rekaman video dimulai: {filename}", flush=True)
            else:
                print("⚠️ Gagal menginisialisasi VideoWriter, rekaman tidak akan disimpan.", flush=True)
                video_writer = None

        # Optimasi: Skip frame untuk deteksi pose (hanya deteksi setiap N frame)
        should_detect = (frame_count % (SKIP_FRAMES + 1) == 0)
        
        # Convert to RGB for mediapipe (hanya jika perlu deteksi)
        pose_landmarks = None
        if should_detect:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)
            
            # Deteksi pose
            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                    mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2),
                )

                pose_landmarks = results.pose_landmarks.landmark
        else:
            # Gunakan pose_landmarks dari frame sebelumnya jika ada (untuk visualisasi)
            # Tapi tidak akan trigger checkpoint baru
            pass

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
                # Area2 (20m) diberi warna khusus dan tetap aktif
                is_area2 = (name == "area2")
                
                # Tentukan warna berdasarkan lane, area2, dan feedback
                if is_area2:
                    # Area2 selalu aktif dengan warna kuning/cyan yang mencolok
                    color = (0, 255, 255)  # Cyan/Kuning untuk area2
                    thickness = 3
                elif is_active_lane:
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
                        if is_area2:
                            # Area2 dengan feedback: hijau terang
                            color = (0, 255, 0)  # Hijau untuk area2 dengan feedback
                            thickness = 4
                        elif is_active_lane:
                            color = (0, 255, 0)  # Hijau untuk success lane aktif
                            thickness = 3
                        else:
                            color = (0, 255, 255)  # Kuning untuk success lane tidak aktif
                            thickness = 2
                    else:
                        # Hapus feedback yang sudah expired
                        del feedback_messages[feedback_key]
                        # Kembalikan warna area2 ke cyan jika tidak ada feedback
                        if is_area2:
                            color = (0, 255, 255)
                            thickness = 3

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

                # Tampilkan label lane dan checkpoint info
                checkpoint_num = AREA_TO_CHECKPOINT.get(name, 0)
                distance = checkpoint_num * 10
                area_label = f"L{lane_num} {name} ({distance}m)"
                font_scale = 0.4 if not is_active_lane else 0.5
                cv2.putText(
                    frame,
                    area_label,
                    (x1 + 3, y1 + 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    color,
                    1 if not is_active_lane else 2,
                )

                # Tampilkan feedback message jika ada
                if feedback_key in feedback_messages:
                    msg, expiry_time = feedback_messages[feedback_key]
                    if current_time < expiry_time:
                        cv2.putText(
                            frame,
                            msg,
                            (x1 + 3, y1 + 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.35,
                            (0, 255, 0),
                            1,
                        )

            # Gambar garis pemisah antara lane
            if lane_num == 1:
                cv2.line(frame, (125, 0), (125, h), (255, 255, 255), 2)
                # Label Lane 1
                cv2.putText(
                    frame,
                    "LANE 1",
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 255) if active_lane == 1 else (150, 150, 150),
                    2,
                )
            elif lane_num == 2:
                # Label Lane 2
                cv2.putText(
                    frame,
                    "LANE 2",
                    (140, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 255) if active_lane == 2 else (150, 150, 150),
                    2,
                )

        # Handle keyboard input (manual override lane) - non-blocking
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):  # ESC atau 'q' untuk keluar
            print("🔚 Dihentikan oleh user (keyboard).")
            break
        elif key == ord('1'):  # Switch ke Lintasan 1 (manual)
            if active_lane != 1:
                set_current_lane(1)
                active_lane = 1  # Update lokal untuk frame ini
        elif key == ord('2'):  # Switch ke Lintasan 2 (manual)
            if active_lane != 2:
                set_current_lane(2)
                active_lane = 2  # Update lokal untuk frame ini

        # Logika deteksi area berbasis SEMUA bagian tubuh (landmark pose)
        # Hanya cek jika pose terdeteksi dan pada frame deteksi
        detected_lane = None
        detected_area = None
        hit_point = None

        if pose_landmarks and should_detect:
            # Optimasi: Cek landmark yang relevan saja (pinggang, bahu, kepala, lutut)
            # Index: 0=nose, 11=left_shoulder, 12=right_shoulder, 23=left_hip, 24=right_hip
            # 25=left_knee, 26=right_knee
            relevant_indices = [0, 11, 12, 23, 24, 25, 26]
            
            # Cek semua landmark terhadap semua area di kedua lane
            for lane_num in [1, 2]:
                if lane_num not in LANE_AREAS:
                    continue
                areas = LANE_AREAS[lane_num]

                for area_name, (x1, y1, x2, y2) in areas.items():
                    # Cek landmark yang relevan terlebih dahulu
                    for idx in relevant_indices:
                        if idx < len(pose_landmarks):
                            lm = pose_landmarks[idx]
                            px = int(lm.x * w)
                            py = int(lm.y * h)

                            if x1 <= px <= x2 and y1 <= py <= y2:
                                detected_lane = lane_num
                                detected_area = area_name
                                hit_point = (px, py)
                                break
                    
                    # Jika belum ditemukan, cek semua landmark
                    if not detected_lane:
                        for lm in pose_landmarks:
                            px = int(lm.x * w)
                            py = int(lm.y * h)

                            if x1 <= px <= x2 and y1 <= py <= y2:
                                detected_lane = lane_num
                                detected_area = area_name
                                hit_point = (px, py)
                                break
                    
                    if detected_lane:
                        break
                if detected_lane:
                    break

            if detected_lane and detected_area:
                # Gambar titik pada landmark yang memicu area
                if hit_point is not None:
                    cv2.circle(frame, hit_point, 10, (0, 255, 255), -1)

                if PRINT_DETECTION:
                    print(
                        f"Pose Terdeteksi di Lane {detected_lane}, Area {detected_area} "
                        f"(Checkpoint {AREA_TO_CHECKPOINT[detected_area]*10}m)", flush=True
                    )
                # Trigger checkpoint untuk lane & area yang terdeteksi
                trigger_checkpoint(detected_area, detected_lane)

        # Tampilkan status API di frame
        api_status = "API: ON" if ENABLE_API else "API: OFF"
        lane_info = f"Lintasan Aktif (manual): {active_lane}"
        api_url_short = API_BASE_URL.replace("http://", "").replace("https://", "")

        # Background untuk status bar
        cv2.rectangle(frame, (5, h - 80), (350, h - 5), (0, 0, 0), -1)

        cv2.putText(
            frame,
            api_status,
            (10, h - 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0) if ENABLE_API else (0, 0, 255),
            2,
        )

        # Tampilkan lintasan aktif dengan warna berbeda
        lane_color = (0, 255, 255) if active_lane == 1 else (255, 0, 255)
        cv2.putText(
            frame,
            lane_info,
            (10, h - 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            lane_color,
            2,
        )

        cv2.putText(
            frame,
            api_url_short,
            (10, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (200, 200, 200),
            1,
        )

        # Tampilkan instruksi keyboard
        cv2.putText(
            frame,
            "Press '1' or '2' to switch lane (manual)",
            (w - 360, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (150, 150, 150),
            1,
        )

        # Tulis frame ke file video (dengan overlay)
        if video_writer is not None:
            video_writer.write(frame)

        cv2.imshow("Pose Detection - Swim Timer Checkpoint (2 Lanes)", frame)

except KeyboardInterrupt:
    print("\n🔚 Dihentikan oleh user (Ctrl+C).", flush=True)

finally:
    # Stop API worker thread
    globals()['api_thread_running'] = False
    print("⏹️  Menghentikan API worker thread...", flush=True)
    
    # Tunggu queue selesai (dengan timeout)
    try:
        api_queue.join(timeout=2.0)
    except:
        pass
    
    cap.release()
    if video_writer is not None:
        video_writer.release()
        print("💾 Rekaman video disimpan.", flush=True)
    cv2.destroyAllWindows()
    print("✅ Program selesai.", flush=True)


