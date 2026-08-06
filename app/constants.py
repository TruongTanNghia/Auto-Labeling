"""Hang so dung chung cho toan bo ung dung."""
from __future__ import annotations

APP_NAME = "AutoLabel Studio AI"
APP_TAGLINE = "AI-Powered Video to Dataset Annotation"
APP_VERSION = "1.0.0"
ORG_NAME = "AutoLabelAI"

# ---------------------------------------------------------------- Bang mau ---
COLORS = {
    "bg": "#0F0F16",
    "bg_alt": "#14141D",
    "surface": "#1A1A26",
    "surface_alt": "#1F1F2E",
    "surface_hi": "#26263A",
    "border": "#2A2A3C",
    "border_hi": "#38384F",
    "text": "#E8E8F0",
    "text_dim": "#A0A0B8",
    "text_mute": "#6C6C86",
    "accent": "#7C5CFF",
    "accent_hi": "#9B82FF",
    "accent_dim": "#5B3FD9",
    "accent_soft": "#2A2350",
    "success": "#3DD68C",
    "warning": "#F5A524",
    "danger": "#F3506B",
    "info": "#38BDF8",
    "shadow": "#07070C",
}

# Bang mau gan cho class annotation (tuong phan tot tren nen toi)
CLASS_PALETTE = [
    "#7C5CFF", "#FF7A45", "#3DD68C", "#F5A524", "#38BDF8",
    "#F3506B", "#A78BFA", "#22D3EE", "#FB923C", "#4ADE80",
    "#F472B6", "#60A5FA", "#FACC15", "#2DD4BF", "#C084FC",
    "#FF6B6B", "#94E2D5", "#FDBA74", "#818CF8", "#34D399",
]

# ------------------------------------------------------------------ Trang ---
PAGE_DASHBOARD = "dashboard"
PAGE_IMPORT = "import"
PAGE_EXTRACT = "extract"
PAGE_AUTOLABEL = "autolabel"
PAGE_EDITOR = "editor"
PAGE_DATASET = "dataset"
PAGE_STATS = "stats"
PAGE_TRAIN = "train"
PAGE_SETTINGS = "settings"

NAV_ITEMS = [
    (PAGE_DASHBOARD, "Dashboard", "dashboard"),
    (PAGE_IMPORT, "Import", "import"),
    (PAGE_EXTRACT, "Frame Extractor", "film"),
    (PAGE_AUTOLABEL, "Auto Label", "wand"),
    (PAGE_EDITOR, "Annotation Editor", "pen"),
    (PAGE_DATASET, "Dataset Manager", "database"),
    (PAGE_STATS, "Statistics & Export", "chart"),
    (PAGE_TRAIN, "Train Model", "cpu"),
    (PAGE_SETTINGS, "Settings", "settings"),
]

# ---------------------------------------------------------- Frame extractor ---
MODE_EVERY_FRAME = "every_frame"
MODE_EVERY_N_FRAMES = "every_n_frames"
MODE_EVERY_N_SECONDS = "every_n_seconds"
MODE_ADAPTIVE_MOTION = "adaptive_motion"
MODE_SCENE_DETECT = "scene_detect"

EXTRACT_MODES = [
    (MODE_EVERY_FRAME, "Mọi frame", "Lấy toàn bộ frame của video"),
    (MODE_EVERY_N_FRAMES, "Mỗi N frame", "Lấy 1 frame sau mỗi N frame"),
    (MODE_EVERY_N_SECONDS, "Mỗi N giây", "Lấy 1 frame sau mỗi N giây"),
    (MODE_ADAPTIVE_MOTION, "Theo chuyển động",
     "Chỉ lấy frame khi có chuyển động đáng kể"),
    (MODE_SCENE_DETECT, "Đổi cảnh", "Lấy frame mỗi khi khung hình đổi cảnh"),
]

# ------------------------------------------------------------------- Model ---
YOLO_TASKS = ["detect", "segment", "obb", "pose"]

MODEL_ZOO = {
    "detect": [
        "yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt",
        "yolo11n.pt", "yolo11s.pt", "yolo11m.pt", "yolo11l.pt", "yolo11x.pt",
        "yolo12n.pt", "yolo12s.pt", "yolo12m.pt", "yolo12l.pt", "yolo12x.pt",
    ],
    "segment": [
        "yolov8n-seg.pt", "yolov8s-seg.pt", "yolov8m-seg.pt", "yolov8l-seg.pt", "yolov8x-seg.pt",
        "yolo11n-seg.pt", "yolo11s-seg.pt", "yolo11m-seg.pt", "yolo11l-seg.pt", "yolo11x-seg.pt",
        "yolo12n-seg.pt", "yolo12s-seg.pt", "yolo12m-seg.pt",
    ],
    "obb": [
        "yolov8n-obb.pt", "yolov8s-obb.pt", "yolov8m-obb.pt", "yolov8l-obb.pt",
        "yolo11n-obb.pt", "yolo11s-obb.pt", "yolo11m-obb.pt", "yolo11l-obb.pt",
    ],
    "pose": [
        "yolov8n-pose.pt", "yolov8s-pose.pt", "yolov8m-pose.pt", "yolov8l-pose.pt",
        "yolo11n-pose.pt", "yolo11s-pose.pt", "yolo11m-pose.pt", "yolo11l-pose.pt",
    ],
}

# ------------------------------------------------------------- Trang thai ---
IMG_UNLABELED = "unlabeled"
IMG_AUTO = "auto"
IMG_REVIEW = "review"
IMG_APPROVED = "approved"
IMG_REJECTED = "rejected"

IMAGE_STATUS_LABEL = {
    IMG_UNLABELED: ("Chưa gán nhãn", COLORS["text_mute"]),
    IMG_AUTO: ("Máy gán nhãn", COLORS["info"]),
    IMG_REVIEW: ("Cần xem lại", COLORS["warning"]),
    IMG_APPROVED: ("Đã duyệt", COLORS["success"]),
    IMG_REJECTED: ("Đã loại", COLORS["danger"]),
}

ANN_AUTO = "auto"
ANN_REVIEW = "review"
ANN_APPROVED = "approved"
ANN_MANUAL = "manual"

SHAPE_BBOX = "bbox"
SHAPE_POLYGON = "polygon"
SHAPE_OBB = "obb"
SHAPE_POSE = "pose"

# ------------------------------------------------------------------ Export ---
EXPORT_FORMATS = [
    ("yolo_seg", "YOLO Segmentation", "Polygon chuẩn hoá — dùng cho model *-seg.pt"),
    ("yolo_det", "YOLO Detection", "Bounding box chuẩn hoá: cx cy w h"),
    ("yolo_obb", "YOLO OBB", "Hộp xoay 4 đỉnh chuẩn hoá — dùng cho model *-obb.pt"),
    ("yolo_pose", "YOLO Pose", "Box kèm keypoint — dùng cho model *-pose.pt"),
    ("coco", "COCO JSON", "File instances.json chuẩn COCO, có cả keypoints"),
    ("voc", "Pascal VOC XML", "Một file .xml cho mỗi ảnh"),
    ("mask", "PNG Mask", "Ảnh mask 8-bit theo chỉ số lớp, kèm bản mask màu"),
]

# Be rong cot nhan trong cac bang nhap lieu - dung chung de khong lech nhau
LABEL_W_WIDE = 168     # form rong (Settings, Statistics)
LABEL_W = 132          # form thuong (Frame Extractor, Train)
LABEL_W_NARROW = 104   # cot ben (Auto Label, Editor)

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff")
VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg", ".webm")

# ---------------------------------------------------------------- Phim tat ---
SHORTCUTS = [
    ("Điều hướng", "Ctrl+1 … Ctrl+9", "Chuyển nhanh giữa các trang"),
    ("Điều hướng", "Ctrl+N", "Tạo project mới"),
    ("Điều hướng", "Ctrl+O", "Mở project có sẵn"),
    ("Điều hướng", "Ctrl+S", "Lưu project"),
    ("Sửa nhãn", "A / D", "Ảnh trước / ảnh sau"),
    ("Sửa nhãn", "V", "Công cụ Chọn"),
    ("Sửa nhãn", "W", "Công cụ Polygon"),
    ("Sửa nhãn", "B", "Công cụ Cọ vẽ"),
    ("Sửa nhãn", "E", "Công cụ Tẩy"),
    ("Sửa nhãn", "S", "Công cụ Cắt đôi"),
    ("Sửa nhãn", "M", "Gộp các vùng đang chọn"),
    ("Sửa nhãn", "Giữ Space", "Di chuyển ảnh"),
    ("Sửa nhãn", "Ctrl+Z / Ctrl+Y", "Hoàn tác / Làm lại"),
    ("Sửa nhãn", "Ctrl++ / Ctrl+-", "Phóng to / thu nhỏ"),
    ("Sửa nhãn", "Ctrl+0", "Vừa khung hình"),
    ("Sửa nhãn", "Delete", "Xoá đối tượng đang chọn"),
    ("Sửa nhãn", "1 … 9", "Gán lớp cho đối tượng đang chọn"),
    ("Sửa nhãn", "Enter", "Duyệt ảnh và sang ảnh kế tiếp"),
    ("Sửa nhãn", "Ctrl+A", "Chọn tất cả đối tượng"),
    ("Sửa nhãn", "Esc", "Huỷ thao tác đang vẽ"),
    ("Sửa nhãn", "Alt + cuộn chuột", "Đổi cỡ cọ vẽ / tẩy"),
    ("Gán nhãn tự động", "F5", "Bắt đầu gán nhãn tự động"),
    ("Chung", "F11", "Toàn màn hình"),
    ("Chung", "Ctrl+Q", "Thoát"),
]
