import cv2
import copy

# === KONFIGURASI ===
IMG_PATH = "20251202162736_98145019_screenshot.jpg"  # ganti dengan path gambar Anda
WINDOW_NAME = "Lane Areas Editor (Python)"
OUTPUT_TXT = "lane_areas.txt"

# Koordinat default, sama seperti di detek_pose_fix.py
DEFAULT_LANE_AREAS = {
    1: {
        "area1": [10, 50, 120, 120],
        "area2": [10, 130, 120, 200],
        "area3": [10, 210, 120, 280],
        "area4": [10, 290, 120, 360],
        "area5": [10, 370, 120, 440],
    },
    2: {
        "area1": [130, 50, 240, 120],
        "area2": [130, 130, 240, 200],
        "area3": [130, 210, 240, 280],
        "area4": [130, 290, 240, 360],
        "area5": [130, 370, 240, 440],
    },
}

lane_areas = copy.deepcopy(DEFAULT_LANE_AREAS)

COLORS = {
    1: (255, 0, 0),     # BGR
    2: (255, 0, 255),
}
HANDLE_SIZE = 10

dragging = None  # {'lane', 'area', 'mode', 'offsetX', 'offsetY', 'handle'}

img = cv2.imread(IMG_PATH)
if img is None:
    raise FileNotFoundError(f"Gambar tidak ditemukan: {IMG_PATH}")

canvas = img.copy()
h, w = canvas.shape[:2]

def draw_scene():
    global canvas
    canvas = img.copy()

    # Gambar area
    for lane, areas in lane_areas.items():
        for name, coords in areas.items():
            draw_box(lane, name, coords)

    # Garis pemisah lane
    cv2.line(canvas, (125, 0), (125, h), (255, 255, 255), 2)

    # Label lane
    cv2.putText(canvas, "Lane 1", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 255), 2)
    cv2.putText(canvas, "Lane 2", (140, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 0, 255), 2)

def draw_box(lane, name, coords):
    x1, y1, x2, y2 = coords
    color = COLORS.get(lane, (0, 255, 0))

    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
    cv2.putText(canvas, f"L{lane} {name}", (x1 + 4, y1 + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # handle corner
    for hx, hy in get_handles(coords):
        cv2.rectangle(canvas,
                      (hx - HANDLE_SIZE // 2, hy - HANDLE_SIZE // 2),
                      (hx + HANDLE_SIZE // 2, hy + HANDLE_SIZE // 2),
                      (255, 255, 255), -1)
        cv2.rectangle(canvas,
                      (hx - HANDLE_SIZE // 2, hy - HANDLE_SIZE // 2),
                      (hx + HANDLE_SIZE // 2, hy + HANDLE_SIZE // 2),
                      color, 1)

def get_handles(coords):
    x1, y1, x2, y2 = coords
    return [
        (x1, y1),  # tl
        (x2, y1),  # tr
        (x1, y2),  # bl
        (x2, y2),  # br
    ]

def point_in_rect(x, y, coords):
    x1, y1, x2, y2 = coords
    return x1 <= x <= x2 and y1 <= y <= y2

def on_mouse(event, x, y, flags, param):
    global dragging, lane_areas

    if event == cv2.EVENT_LBUTTONDOWN:
        # cek handle (resize)
        found = None
        for lane, areas in lane_areas.items():
            for name, coords in areas.items():
                handles = get_handles(coords)
                for idx, (hx, hy) in enumerate(handles):
                    if (abs(x - hx) <= HANDLE_SIZE and
                            abs(y - hy) <= HANDLE_SIZE):
                        handle_name = ["tl", "tr", "bl", "br"][idx]
                        found = {
                            "lane": lane,
                            "area": name,
                            "mode": "resize",
                            "handle": handle_name,
                        }
                        break
                if found:
                    break
            if found:
                break

        # jika tidak di handle, cek di dalam box (move)
        if not found:
            for lane, areas in lane_areas.items():
                for name, coords in areas.items():
                    if point_in_rect(x, y, coords):
                        x1, y1, x2, y2 = coords
                        found = {
                            "lane": lane,
                            "area": name,
                            "mode": "move",
                            "offsetX": x - x1,
                            "offsetY": y - y1,
                        }
                        break
                if found:
                    break

        dragging = found

    elif event == cv2.EVENT_MOUSEMOVE and dragging is not None:
        lane = dragging["lane"]
        area = dragging["area"]
        coords = lane_areas[lane][area]
        x1, y1, x2, y2 = coords

        if dragging["mode"] == "move":
            w_box = x2 - x1
            h_box = y2 - y1
            new_x1 = x - dragging["offsetX"]
            new_y1 = y - dragging["offsetY"]
            new_x2 = new_x1 + w_box
            new_y2 = new_y1 + h_box

            # clamp
            new_x1 = max(0, min(new_x1, w - w_box))
            new_y1 = max(0, min(new_y1, h - h_box))
            new_x2 = new_x1 + w_box
            new_y2 = new_y1 + h_box

            lane_areas[lane][area] = [int(new_x1), int(new_y1),
                                      int(new_x2), int(new_y2)]

        elif dragging["mode"] == "resize":
            min_size = 20
            handle = dragging["handle"]
            if "t" in handle:
                y1 = max(0, min(y, y2 - min_size))
            if "b" in handle:
                y2 = min(h, max(y, y1 + min_size))
            if "l" in handle:
                x1 = max(0, min(x, x2 - min_size))
            if "r" in handle:
                x2 = min(w, max(x, x1 + min_size))

            lane_areas[lane][area] = [int(x1), int(y1), int(x2), int(y2)]

        draw_scene()

    elif event == cv2.EVENT_LBUTTONUP:
        dragging = None

def format_lane_areas():
    lines = []
    lines.append("LANE_AREAS = {")
    for lane in [1, 2]:
        lines.append(f"    {lane}: {{  # Lane {lane}")
        areas = lane_areas[lane]
        keys = list(areas.keys())
        for i, (name, coords) in enumerate(areas.items()):
            x1, y1, x2, y2 = coords
            comma = "," if i < len(keys) - 1 else ""
            lines.append(
                f'        "{name}": ({x1}, {y1}, {x2}, {y2}){comma}'
            )
        comma_lane = "," if lane == 1 else ""
        lines.append(f"    }}{comma_lane}")
    lines.append("}")
    return "\n".join(lines)

def save_to_txt(path=OUTPUT_TXT):
    text = format_lane_areas()
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[INFO] Koordinat disimpan ke {path}")

def reset_areas():
    global lane_areas
    lane_areas = copy.deepcopy(DEFAULT_LANE_AREAS)
    print("[INFO] Koordinat dikembalikan ke nilai default")
    draw_scene()

def main():
    draw_scene()
    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    print("[INFO] Kontrol:")
    print("  - Drag di dalam kotak : pindahkan box")
    print("  - Drag titik sudut    : resize box")
    print("  - Tekan 'r'           : reset ke default")
    print("  - Tekan 's'           : save lane_areas.txt")
    print("  - Tekan 'q' atau ESC  : keluar")

    while True:
        cv2.imshow(WINDOW_NAME, canvas)
        key = cv2.waitKey(20) & 0xFF
        if key in (27, ord('q')):
            break
        elif key == ord('s'):
            save_to_txt()
        elif key == ord('r'):
            reset_areas()

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()