import streamlit as st
import cv2
import tempfile
import time
import os
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ultralytics import YOLO
import csv
from datetime import datetime
import urllib.request
from twilio.rest import Client
import pyttsx3
import queue
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict, deque
import numpy as np

# ===================== PAGE CONFIG =====================
st.set_page_config(
    page_title="Hospital Safety PRO MAX",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏥"
)

# ===================== CUSTOM CSS =====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
* { font-family: 'Space Grotesk', sans-serif; }
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1b2a 50%, #0a1628 100%);
    color: #e0e6f0;
}
.main-header {
    background: linear-gradient(90deg, #00d4ff22, #0066ff22);
    border: 1px solid #00d4ff44;
    border-radius: 16px;
    padding: 20px 30px;
    margin-bottom: 20px;
    text-align: center;
}
.main-header h1 {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00d4ff, #0099ff, #00ffcc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.main-header p {
    color: #7090b0;
    font-size: 0.85rem;
    margin: 6px 0 0 0;
    font-family: 'JetBrains Mono', monospace;
}
.metric-card {
    background: linear-gradient(135deg, #0d1b2a, #0f2035);
    border: 1px solid #1a3a5c;
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 10px;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #00d4ff, #0066ff);
}
.metric-value { font-size: 2rem; font-weight: 700; color: #00d4ff; font-family: 'JetBrains Mono', monospace; }
.metric-label { font-size: 0.72rem; color: #7090b0; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }
.status-danger {
    background: linear-gradient(135deg, #1a0a0a, #2a0f0f);
    border: 2px solid #ff4444;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 10px;
    animation: pulse-danger 1.5s infinite;
}
.status-safe {
    background: linear-gradient(135deg, #0a1a0f, #0f2a15);
    border: 1px solid #00cc66;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 10px;
}
.status-fall {
    background: linear-gradient(135deg, #1a0a00, #2a1500);
    border: 2px solid #ff8800;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 10px;
    animation: pulse-danger 1s infinite;
}
.status-wet {
    background: linear-gradient(135deg, #0a1020, #0f1a35);
    border: 2px solid #00aaff;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 10px;
    animation: pulse-wet 1.2s infinite;
}
@keyframes pulse-danger {
    0%, 100% { box-shadow: 0 0 0 0 #ff444433; }
    50% { box-shadow: 0 0 0 10px #ff444400; }
}
@keyframes pulse-wet {
    0%, 100% { box-shadow: 0 0 0 0 #00aaff33; }
    50% { box-shadow: 0 0 0 10px #00aaff00; }
}
.object-tag {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
    margin: 3px;
    font-family: 'JetBrains Mono', monospace;
}
.tag-danger { background: #ff000020; border: 1px solid #ff4444; color: #ff6666; }
.tag-safe   { background: #00cc6620; border: 1px solid #00cc66; color: #00ee88; }
.tag-warn   { background: #ffaa0020; border: 1px solid #ffaa00; color: #ffcc44; }
.tag-fall   { background: #ff880020; border: 1px solid #ff8800; color: #ffaa44; }
.tag-wet    { background: #00aaff20; border: 1px solid #00aaff; color: #44ccff; }
.log-entry {
    background: #0d1b2a;
    border-left: 3px solid #00d4ff;
    padding: 7px 12px;
    margin: 3px 0;
    border-radius: 0 8px 8px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: #a0b8d0;
}
.log-entry.danger { border-left-color: #ff4444; color: #ff8888; }
.log-entry.warn   { border-left-color: #ffaa00; color: #ffcc66; }
.log-entry.fall   { border-left-color: #ff8800; color: #ffaa44; }
.log-entry.wet    { border-left-color: #00aaff; color: #44ccff; }
.section-header {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #00d4ff;
    margin-bottom: 10px;
    padding-bottom: 5px;
    border-bottom: 1px solid #00d4ff22;
}
div[data-testid="stSidebarContent"] {
    background: linear-gradient(180deg, #080e18, #0a1220);
    border-right: 1px solid #1a3a5c;
}
.stButton > button {
    background: linear-gradient(90deg, #0066ff, #00aaff) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 4px 20px #0066ff55 !important; }
</style>
""", unsafe_allow_html=True)

# ===================== LANGUAGE CONFIG =====================
LANGUAGES = {
    "English": {
        "warning": "Warning",
        "detected": "detected",
        "fall_alert": "Fall detected! Person is on the ground!",
        "wet_floor": "Wet floor hazard detected! Slip risk in this area!",
        "zone_alert": "Zone alert",
        "in_zone": "in zone",
        "direction": {"left": "on the left", "right": "on the right", "front": "in front"},
        "distance": {"very close": "very close", "near": "nearby", "far": "far away"},
        "safe": "✅ SAFE",
        "danger": "🚨 DANGER",
        "fall": "🆘 FALL DETECTED",
        "wet": "💧 WET FLOOR HAZARD",
        "persons": "Persons",
    },
    "Tamil": {
        "warning": "எச்சரிக்கை",
        "detected": "கண்டறியப்பட்டது",
        "fall_alert": "விழுகை கண்டறியப்பட்டது! நபர் தரையில் இருக்கிறார்!",
        "wet_floor": "ஈரமான தரை ஆபத்து கண்டறியப்பட்டது! வழுக்கல் அபாயம்!",
        "zone_alert": "மண்டல எச்சரிக்கை",
        "in_zone": "மண்டலத்தில்",
        "direction": {"left": "இடதுபுறம்", "right": "வலதுபுறம்", "front": "முன்புறம்"},
        "distance": {"very close": "மிக அருகில்", "near": "அருகில்", "far": "தொலைவில்"},
        "safe": "✅ பாதுகாப்பு",
        "danger": "🚨 அபாயம்",
        "fall": "🆘 விழுகை கண்டறியப்பட்டது",
        "wet": "💧 ஈரமான தரை ஆபத்து",
        "persons": "நபர்கள்",
    },
    "Hindi": {
        "warning": "चेतावनी",
        "detected": "पता चला",
        "fall_alert": "गिरावट पता चली! व्यक्ति जमीन पर है!",
        "wet_floor": "गीला फर्श खतरा पाया गया! फिसलन का खतरा!",
        "zone_alert": "ज़ोन अलर्ट",
        "in_zone": "ज़ोन में",
        "direction": {"left": "बाईं ओर", "right": "दाईं ओर", "front": "सामने"},
        "distance": {"very close": "बहुत पास", "near": "पास", "far": "दूर"},
        "safe": "✅ सुरक्षित",
        "danger": "🚨 खतरा",
        "fall": "🆘 गिरावट पता चली",
        "wet": "💧 गीला फर्श खतरा",
        "persons": "व्यक्ति",
    },
    "Kannada": {
        "warning": "ಎಚ್ಚರಿಕೆ",
        "detected": "ಕಂಡುಬಂದಿದೆ",
        "fall_alert": "ಬಿದ್ದುಹೋಗಿರುವುದು ಕಂಡುಬಂದಿದೆ! ವ್ಯಕ್ತಿ ನೆಲದಲ್ಲಿ ಇದ್ದಾನೆ!",
        "wet_floor": "ಒದ್ದೆ ನೆಲದ ಅಪಾಯ ಕಂಡುಬಂದಿದೆ! ಜಾರುವ ಅಪಾಯ!",
        "zone_alert": "ಪ್ರದೇಶ ಎಚ್ಚರಿಕೆ",
        "in_zone": "ಪ್ರದೇಶದಲ್ಲಿ",
        "direction": {"left": "ಎಡಭಾಗದಲ್ಲಿ", "right": "ಬಲಭಾಗದಲ್ಲಿ", "front": "ಮುಂದೆ"},
        "distance": {"very close": "ತುಂಬಾ ಹತ್ತಿರ", "near": "ಹತ್ತಿರ", "far": "ದೂರದಲ್ಲಿ"},
        "safe": "✅ ಸುರಕ್ಷಿತ",
        "danger": "🚨 ಅಪಾಯ",
        "fall": "🆘 ಬಿದ್ದುಹೋಗಿರುವುದು",
        "wet": "💧 ಒದ್ದೆ ನೆಲದ ಅಪಾಯ",
        "persons": "ವ್ಯಕ್ತಿಗಳು",
    },
    "Arabic": {
        "warning": "تحذير",
        "detected": "تم اكتشاف",
        "fall_alert": "تم اكتشاف سقوط! الشخص على الأرض!",
        "wet_floor": "تم اكتشاف خطر الأرضية المبللة! خطر الانزلاق!",
        "zone_alert": "تنبيه المنطقة",
        "in_zone": "في المنطقة",
        "direction": {"left": "على اليسار", "right": "على اليمين", "front": "أمامك"},
        "distance": {"very close": "قريب جداً", "near": "قريب", "far": "بعيد"},
        "safe": "✅ آمن",
        "danger": "🚨 خطر",
        "fall": "🆘 تم اكتشاف سقوط",
        "wet": "💧 خطر الأرضية المبللة",
        "persons": "أشخاص",
    },
    "French": {
        "warning": "Attention",
        "detected": "détecté",
        "fall_alert": "Chute détectée! La personne est au sol!",
        "wet_floor": "Sol mouillé détecté! Risque de glissade!",
        "zone_alert": "Alerte de zone",
        "in_zone": "dans la zone",
        "direction": {"left": "à gauche", "right": "à droite", "front": "devant"},
        "distance": {"very close": "très proche", "near": "proche", "far": "loin"},
        "safe": "✅ SÛR",
        "danger": "🚨 DANGER",
        "fall": "🆘 CHUTE DÉTECTÉE",
        "wet": "💧 SOL MOUILLÉ",
        "persons": "Personnes",
    },
}

# ===================== SPEECH SYSTEM =====================
if "speech_system" not in st.session_state:
    st.session_state.speech_queue = queue.Queue()
    st.session_state.last_global_speak = 0

    _engine = pyttsx3.init()
    _engine.setProperty('rate', 155)
    _engine.setProperty('volume', 1.0)

    def _speech_worker():
        while True:
            text = st.session_state.speech_queue.get()
            if text is None:
                break
            try:
                _engine.say(text)
                _engine.runAndWait()
            except Exception as e:
                print("Speech error:", e)
            st.session_state.speech_queue.task_done()

    threading.Thread(target=_speech_worker, daemon=True).start()
    st.session_state.speech_system = True

def speak(text, priority=False):
    if not st.session_state.get("voice_enabled", True):
        return
    now = time.time()
    if not priority and now - st.session_state.last_global_speak < 2:
        return
    st.session_state.last_global_speak = now
    st.session_state.speech_queue.put(text)

# ===================== SESSION STATE =====================
defaults = {
    "detection_history": deque(maxlen=300),
    "heatmap_grid": np.zeros((10, 10), dtype=np.float32),
    "stats": {
        "total_detections": 0, "danger_events": 0,
        "fall_events": 0, "wet_floor_events": 0,
        "persons_detected": 0, "alerts_sent": 0,
        "session_start": datetime.now()
    },
    "recent_messages": deque(maxlen=20),
    "object_counts": defaultdict(int),
    "running": False,
    "voice_enabled": True,
    "prev_person_boxes": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ===================== CONSTANTS =====================
LOG_FILE = "detection_log.csv"

SAFE_OBJECTS = [
    "person", "chair", "bed", "couch", "sofa", "cup", "bottle",
    "cell phone", "laptop", "clock", "vase", "book", "remote",
    "keyboard", "mouse", "tv", "monitor", "potted plant", "teddy bear"
]
DANGEROUS_OBJECTS = ["knife", "scissors", "gun", "baseball bat", "fire", "smoke"]
RESTRICTED_OBJECTS = ["cell phone", "laptop", "remote"]
ALL_TRACKED = list(set(SAFE_OBJECTS + DANGEROUS_OBJECTS))
SPEAK_COOLDOWN = 4
SLIP_ZONE_LABEL = "WET FLOOR"

# ===================== SIDEBAR =====================
with st.sidebar:
    st.markdown('<div class="section-header">⚙️ System Configuration</div>', unsafe_allow_html=True)

    language = st.selectbox("🌐 Language", list(LANGUAGES.keys()), index=0)
    L = LANGUAGES[language]

    model_size = st.selectbox("YOLO Model", ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt"], index=0)
    conf_threshold = st.slider("Confidence Threshold", 0.2, 0.9, 0.4, 0.05)
    imgsz = st.select_slider("Inference Size", [160, 320, 480, 640], value=320)

    st.markdown('<div class="section-header" style="margin-top:16px">🔔 Alert Settings</div>', unsafe_allow_html=True)

    enable_sms = st.toggle("SMS Alerts (Twilio)", False)
    twilio_sid = twilio_token = twilio_from = nurse_phone = ""
    if enable_sms:
        twilio_sid   = st.text_input("Twilio SID", type="password")
        twilio_token = st.text_input("Twilio Token", type="password")
        twilio_from  = st.text_input("From Number", "+1234567890")
        nurse_phone  = st.text_input("Nurse Phone", "+919876543210")

    enable_email = st.toggle("Email Alerts", False)
    email_sender = email_password = email_receiver = ""
    if enable_email:
        email_sender   = st.text_input("Sender Email")
        email_password = st.text_input("Email Password", type="password")
        email_receiver = st.text_input("Receiver Email")

    enable_whatsapp = st.toggle("WhatsApp (Twilio)", False)
    wa_sid = wa_token = wa_from = wa_to = ""
    if enable_whatsapp:
        wa_sid   = st.text_input("WA Twilio SID",   type="password", key="wa_sid")
        wa_token = st.text_input("WA Twilio Token", type="password", key="wa_token")
        wa_from  = st.text_input("WA From", "whatsapp:+14155238886")
        wa_to    = st.text_input("WA To",   "whatsapp:+919876543210")

    alert_cooldown = st.slider("Alert Cooldown (sec)", 5, 120, 30)

    st.markdown('<div class="section-header" style="margin-top:16px">🚧 Zone Settings</div>', unsafe_allow_html=True)
    restricted_zone = st.toggle("Enable Restricted Zone Detection", False)
    zone_label = "General"
    zone_objects = []
    if restricted_zone:
        zone_label   = st.text_input("Zone Name", "ICU")
        zone_objects = st.multiselect("Alert if detected in zone", ALL_TRACKED, default=DANGEROUS_OBJECTS)

    st.markdown('<div class="section-header" style="margin-top:16px">💧 Wet Floor Detection</div>', unsafe_allow_html=True)
    enable_wet_detection = st.toggle("Enable Wet Floor / Slip Zone Detection", True)
    wet_area_ratio = st.slider("Min Spill Size (% of frame)", 1, 15, 4) / 100
    wet_brightness_thresh = st.slider("Reflectance Sensitivity", 140, 220, 180,
                                       help="Lower = detects dimmer reflections too")
    wet_saturation_thresh = st.slider("Saturation Threshold", 10, 80, 35,
                                       help="Lower = only colorless liquids; higher = colored spills too")

    st.markdown('<div class="section-header" style="margin-top:16px">🎨 Display</div>', unsafe_allow_html=True)
    show_heatmap = st.toggle("Live Heatmap", True)
    enable_voice = st.toggle("Voice Alerts", True)
    st.session_state.voice_enabled = enable_voice

    fall_sensitivity = st.slider("Fall Detection Sensitivity", 1, 5, 3,
                                  help="Higher = more sensitive to falls")

# ===================== MODEL =====================
@st.cache_resource
def load_model(size):
    return YOLO(size)

model = load_model(model_size)

# ===================== HELPERS =====================
def init_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "Timestamp", "Object", "Direction", "Distance",
                "Status", "PersonCount", "Zone"
            ])

def log_event(label, direction, distance, status, person_count, zone="General"):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            label, direction, distance, status, person_count, zone
        ])
    st.session_state.stats["total_detections"] += 1
    if status == "DANGER":
        st.session_state.stats["danger_events"] += 1
    elif status == "FALL":
        st.session_state.stats["fall_events"] += 1
    elif status == "WET":
        st.session_state.stats["wet_floor_events"] += 1
    st.session_state.object_counts[label] += 1

def get_direction(box, w):
    x1, _, x2, _ = box.xyxy[0]
    cx = float((x1 + x2) / 2)
    if cx < w / 3:   return "left"
    if cx > 2*w / 3: return "right"
    return "front"

def get_distance(box, w, h):
    x1, y1, x2, y2 = box.xyxy[0]
    ratio = float((x2-x1)*(y2-y1)) / (w*h)
    if ratio > 0.3:  return "very close"
    if ratio > 0.1:  return "near"
    return "far"

def update_heatmap(box, w, h):
    x1, y1, x2, y2 = box.xyxy[0]
    cx = min(int(float((x1+x2)/2) / w * 10), 9)
    cy = min(int(float((y1+y2)/2) / h * 10), 9)
    st.session_state.heatmap_grid[cy][cx] += 1

# ===================== FALL DETECTION =====================
def is_person_fallen(box, w, h):
    """
    Detects fall by checking if bounding box is wider than tall
    (person lying horizontal) AND box is in lower portion of frame.
    """
    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
    bw = x2 - x1
    bh = y2 - y1
    if bh == 0:
        return False
    aspect_ratio = bw / bh  # >1 means wider than tall = horizontal
    center_y = (y1 + y2) / 2
    frame_lower_half = center_y > h * 0.35

    # Sensitivity: higher = triggers at lower ratio
    threshold = 0.8 + (5 - fall_sensitivity) * 0.15  # 1.4 at sens=1, 0.8 at sens=5

    return aspect_ratio > threshold and frame_lower_half

# ===================== WET FLOOR / SLIP DETECTION =====================
def detect_wet_floor(frame):
    """
    Detects liquid spills and wet/slip surfaces by finding floor regions that are:
      - Highly reflective (high V channel in HSV)
      - Low saturation (colorless / semi-transparent liquids like water)
      - Large enough to be a real spill (not sensor noise)
    Restricts search to the lower 60% of the frame (floor area).
    Returns:
        spill_regions : list of (x1, y1, x2, y2) bounding boxes
        wet_mask      : binary mask (for debugging / heatmap use)
    """
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Channel isolation
    s_channel = hsv[:, :, 1]   # Saturation
    v_channel = hsv[:, :, 2]   # Value / brightness

    # Low saturation (colorless liquid) + high brightness (reflective surface)
    low_sat  = cv2.inRange(s_channel, 0, int(wet_saturation_thresh))
    high_val = cv2.inRange(v_channel, int(wet_brightness_thresh), 255)
    wet_mask = cv2.bitwise_and(low_sat, high_val)

    # Restrict to floor area: lower 60% of frame
    floor_mask = np.zeros_like(wet_mask)
    floor_start = int(h * 0.40)
    floor_mask[floor_start:, :] = 255
    wet_mask = cv2.bitwise_and(wet_mask, floor_mask)

    # Morphological cleanup — close small gaps, remove tiny noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    wet_mask = cv2.morphologyEx(wet_mask, cv2.MORPH_CLOSE, kernel)
    wet_mask = cv2.morphologyEx(wet_mask, cv2.MORPH_OPEN, kernel)

    # Find contours of spill blobs
    contours, _ = cv2.findContours(wet_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    spill_regions = []
    min_area = w * h * wet_area_ratio
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > min_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            spill_regions.append((x, y, x + bw, y + bh))

    return spill_regions, wet_mask


def draw_slip_zones(frame, spill_regions):
    """
    Draws warning overlays on detected wet / slip-risk areas.
    Uses a semi-transparent cyan fill with diagonal hatching
    and a bold bounding box + label.
    """
    for (x1, y1, x2, y2) in spill_regions:
        overlay = frame.copy()

        # Semi-transparent cyan fill
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 200, 0), -1)
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

        # Diagonal hatching lines for "wet surface" visual cue
        hatch_gap = 18
        for xh in range(x1, x2 + (y2 - y1), hatch_gap):
            pt1 = (max(x1, xh - (y2 - y1)), y1 if xh > x1 else y1 + (x1 - xh))
            pt2 = (min(x2, xh), y1 + min(xh - x1, y2 - y1) if xh <= x2 else y2)
            cv2.line(frame, pt1, pt2, (180, 220, 255), 1, cv2.LINE_AA)

        # Bold border
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 255), 2)

        # Background pill for label
        label_text = "WET FLOOR / SLIP RISK"
        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 180, 220), -1)
        cv2.putText(frame, label_text, (x1 + 5, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # Small water-drop icon dots
        dot_x, dot_y = x2 - 20, y1 + 20
        cv2.circle(frame, (dot_x, dot_y), 6, (0, 220, 255), -1)
        cv2.circle(frame, (dot_x - 16, dot_y + 6), 4, (0, 200, 240), -1)
        cv2.circle(frame, (dot_x + 12, dot_y + 8), 5, (0, 210, 250), -1)

    return frame


def update_heatmap_from_spill(spill_regions, w, h):
    """Updates the spatial heatmap for spill zone locations."""
    for (x1, y1, x2, y2) in spill_regions:
        cx = min(int(((x1 + x2) / 2) / w * 10), 9)
        cy = min(int(((y1 + y2) / 2) / h * 10), 9)
        st.session_state.heatmap_grid[cy][cx] += 2  # weight spills heavier

# ===================== ALERT SYSTEM =====================
_alert_last = {"sms": 0, "email": 0, "wa": 0}

def _send_sms(msg):
    if not enable_sms or not twilio_sid: return
    if time.time() - _alert_last["sms"] < alert_cooldown: return
    try:
        Client(twilio_sid, twilio_token).messages.create(
            body=msg, from_=twilio_from, to=nurse_phone)
        _alert_last["sms"] = time.time()
        st.session_state.stats["alerts_sent"] += 1
    except Exception as e: print("SMS:", e)

def _send_email(msg):
    if not enable_email or not email_sender: return
    if time.time() - _alert_last["email"] < alert_cooldown: return
    try:
        m = MIMEMultipart()
        m["From"] = email_sender; m["To"] = email_receiver
        m["Subject"] = "🚨 Hospital Safety ALERT"
        m.attach(MIMEText(msg, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(email_sender, email_password)
            s.sendmail(email_sender, email_receiver, m.as_string())
        _alert_last["email"] = time.time()
        st.session_state.stats["alerts_sent"] += 1
    except Exception as e: print("Email:", e)

def _send_wa(msg):
    if not enable_whatsapp or not wa_sid: return
    if time.time() - _alert_last["wa"] < alert_cooldown: return
    try:
        Client(wa_sid, wa_token).messages.create(
            body=msg, from_=wa_from, to=wa_to)
        _alert_last["wa"] = time.time()
        st.session_state.stats["alerts_sent"] += 1
    except Exception as e: print("WA:", e)

def fire_alerts(message):
    threading.Thread(target=_send_sms,   args=(message,), daemon=True).start()
    threading.Thread(target=_send_email, args=(message,), daemon=True).start()
    threading.Thread(target=_send_wa,    args=(message,), daemon=True).start()

# ===================== FRAME PROCESSOR =====================
_obj_last_spoken = {}

def process_frame(frame):
    global _obj_last_spoken
    h, w = frame.shape[:2]
    L = LANGUAGES[language]

    results = model.predict(frame, conf=conf_threshold, imgsz=imgsz, verbose=False)
    annotated = results[0].plot()

    now = time.time()
    detected_objects = set()
    messages = []
    danger_detected = False
    fall_detected = False
    zone_violation = False
    wet_floor_detected = False

    # ---- WET FLOOR / SLIP ZONE DETECTION ----
    if enable_wet_detection:
        spill_regions, wet_mask = detect_wet_floor(frame)
        wet_floor_detected = len(spill_regions) > 0

        if wet_floor_detected:
            annotated = draw_slip_zones(annotated, spill_regions)
            update_heatmap_from_spill(spill_regions, w, h)

            # Log each spill region
            for (x1, y1, x2, y2) in spill_regions:
                cx = (x1 + x2) // 2
                direction = "left" if cx < w // 3 else ("right" if cx > 2 * w // 3 else "front")
                log_event(SLIP_ZONE_LABEL, direction, "very close", "WET", 0,
                          zone_label if restricted_zone else "General")

            # Voice + message alert (throttled)
            last_wet = _obj_last_spoken.get("wet_floor", 0)
            if now - last_wet > SPEAK_COOLDOWN:
                wet_msg = L["wet_floor"]
                speak(wet_msg, priority=True)
                entry = {"text": wet_msg, "type": "wet", "time": datetime.now().strftime("%H:%M:%S")}
                messages.append(entry)
                st.session_state.recent_messages.appendleft(entry)
                _obj_last_spoken["wet_floor"] = now

                fire_alerts(
                    f"💧 WET FLOOR / SLIP RISK detected at "
                    f"{datetime.now().strftime('%H:%M:%S')}\n"
                    f"Zones affected: {len(spill_regions)}"
                )

    # ---- YOLO OBJECT DETECTION ----
    boxes = results[0].boxes
    person_count = 0

    if boxes is not None:
        person_count = sum(1 for b in boxes if model.names[int(b.cls[0])] == "person")
        st.session_state.stats["persons_detected"] = max(
            st.session_state.stats["persons_detected"], person_count)

        for box in boxes:
            label = model.names[int(box.cls[0])]
            is_danger  = label in DANGEROUS_OBJECTS
            is_zone_v  = restricted_zone and label in zone_objects
            is_person  = label == "person"

            detected_objects.add(label)

            direction = get_direction(box, w)
            distance  = get_distance(box, w, h)
            update_heatmap(box, w, h)

            # Fall detection
            person_fallen = False
            if is_person:
                person_fallen = is_person_fallen(box, w, h)
                if person_fallen:
                    fall_detected = True

            status = "FALL" if person_fallen else ("DANGER" if is_danger else "SAFE")
            if is_danger: danger_detected = True
            if is_zone_v: zone_violation  = True

            log_event(label, direction, distance, status, person_count,
                      zone_label if restricted_zone else "General")

            last_t = _obj_last_spoken.get(label, 0)
            if now - last_t > SPEAK_COOLDOWN:
                dir_txt  = L["direction"].get(direction, direction)
                dist_txt = L["distance"].get(distance, distance)

                if person_fallen:
                    msg_txt  = L["fall_alert"]
                    msg_type = "fall"
                elif is_danger:
                    msg_txt  = f"{L['warning']}! {label} {L['detected']} {dir_txt}, {dist_txt}"
                    msg_type = "danger"
                elif is_zone_v:
                    msg_txt  = f"{L['zone_alert']}! {label} {L['in_zone']} {zone_label}"
                    msg_type = "warn"
                else:
                    msg_txt  = f"{label} {L['detected']} {dir_txt}, {dist_txt}"
                    msg_type = "safe"

                speak(msg_txt, priority=(is_danger or person_fallen))
                entry = {"text": msg_txt, "type": msg_type, "time": datetime.now().strftime("%H:%M:%S")}
                messages.append(entry)
                st.session_state.recent_messages.appendleft(entry)
                _obj_last_spoken[label] = now

        st.session_state.detection_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "count": len(detected_objects),
            "persons": person_count,
            "danger": int(danger_detected),
            "fall": int(fall_detected),
            "wet": int(wet_floor_detected),
        })

    # Cleanup stale spoken cache
    for obj in list(_obj_last_spoken.keys()):
        if obj not in detected_objects and obj != "wet_floor":
            del _obj_last_spoken[obj]

    # Fire combined alerts for YOLO danger events
    if danger_detected or fall_detected or zone_violation:
        alert_body = f"🚨 ALERT [{datetime.now().strftime('%H:%M:%S')}]\n"
        if fall_detected:   alert_body += "🆘 FALL DETECTED\n"
        if danger_detected: alert_body += f"⚠️ Dangerous objects: {', '.join(detected_objects & set(DANGEROUS_OBJECTS))}\n"
        if zone_violation:  alert_body += f"🚧 Zone violation in {zone_label}\n"
        fire_alerts(alert_body)

    return annotated, detected_objects, danger_detected, fall_detected, wet_floor_detected, zone_violation, person_count

# ===================== RENDER HELPERS =====================
def render_status_card(danger, fall, wet, zone_viol, count):
    L = LANGUAGES[language]
    if fall:
        card_class   = "status-fall"
        status_text  = L["fall"]
        status_color = "#ff8800"
    elif danger:
        card_class   = "status-danger"
        status_text  = L["danger"]
        status_color = "#ff4444"
    elif wet:
        card_class   = "status-wet"
        status_text  = L["wet"]
        status_color = "#00aaff"
    else:
        card_class   = "status-safe"
        status_text  = L["safe"]
        status_color = "#00cc66"

    zone_html = ""
    if zone_viol:
        zone_html = f'<div style="color:#ffaa00;font-size:0.82rem;margin-top:4px">⚠️ Zone Violation: {zone_label}</div>'

    wet_html = ""
    if wet:
        wet_html = f'<div style="color:#00aaff;font-size:0.82rem;margin-top:4px">💧 Wet Floor / Slip Risk Detected</div>'

    return f"""
    <div class="{card_class}">
        <div style="font-size:1.4rem;font-weight:700;color:{status_color}">{status_text}</div>
        <div style="color:#7090b0;font-size:0.82rem;margin-top:6px">
            👥 {L['persons']}: <b style="color:#00d4ff">{count}</b>
        </div>
        {zone_html}{wet_html}
    </div>
    """

def render_metrics_html():
    s = st.session_state.stats
    return f"""
    <div class="metric-card">
        <div class="metric-value">{s['total_detections']}</div>
        <div class="metric-label">Total Detections</div>
    </div>
    <div class="metric-card">
        <div class="metric-value" style="color:#ff4444">{s['danger_events']}</div>
        <div class="metric-label">Danger Events</div>
    </div>
    <div class="metric-card">
        <div class="metric-value" style="color:#ff8800">{s['fall_events']}</div>
        <div class="metric-label">Fall Events</div>
    </div>
    <div class="metric-card">
        <div class="metric-value" style="color:#00aaff">{s['wet_floor_events']}</div>
        <div class="metric-label">Wet Floor Events</div>
    </div>
    <div class="metric-card">
        <div class="metric-value" style="color:#ffaa00">{s['alerts_sent']}</div>
        <div class="metric-label">Alerts Sent</div>
    </div>
    """

def render_objects_html(objects):
    if not objects:
        return '<span style="color:#7090b0;font-size:0.8rem">No objects detected</span>'
    tags = ""
    for obj in objects:
        if obj in DANGEROUS_OBJECTS:
            tags += f'<span class="object-tag tag-danger">⚠ {obj}</span>'
        elif restricted_zone and obj in zone_objects:
            tags += f'<span class="object-tag tag-warn">🚧 {obj}</span>'
        elif obj == "person":
            tags += f'<span class="object-tag tag-fall">👤 {obj}</span>'
        else:
            tags += f'<span class="object-tag tag-safe">✓ {obj}</span>'
    return tags

def render_messages_html():
    html = '<div class="section-header" style="margin-top:10px">📢 Voice Log</div>'
    for m in list(st.session_state.recent_messages)[:10]:
        html += f'<div class="log-entry {m["type"]}"><span style="color:#556677">[{m["time"]}]</span> {m["text"]}</div>'
    return html

# ===================== MAIN UI =====================
init_log()

st.markdown("""
<div class="main-header">
    <h1>🏥 Hospital Safety System PRO MAX</h1>
    <p>[ Real-time Detection · Fall Alert · Wet Floor / Slip Zone · Multi-Alert · Zone Monitor · Analytics ]</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📹 Live Monitor", "📊 Analytics", "🗺️ Heatmap", "📋 Reports"])

# ===================== TAB 1: LIVE MONITOR =====================
with tab1:
    col_feed, col_stats = st.columns([3, 1])

    with col_feed:
        mode = st.radio("Input Mode", ["Webcam", "Video File", "URL"], horizontal=True)
        frame_ph = st.empty()

        if mode == "Video File":
            uploaded_file = st.file_uploader("Upload Video", type=["mp4", "avi", "mov", "mkv", "mpeg4"])
        elif mode == "URL":
            video_url = st.text_input("Video Stream URL")

    with col_stats:
        st.markdown('<div class="section-header">📡 Live Stats</div>', unsafe_allow_html=True)
        status_ph  = st.empty()
        metrics_ph = st.empty()
        objects_ph = st.empty()
        msgs_ph    = st.empty()

    c1, c2 = st.columns(2)
    with c1:
        start_btn = st.button("▶ Start Detection", use_container_width=True)
    with c2:
        stop_btn  = st.button("⏹ Stop", use_container_width=True)

    if stop_btn:
        st.session_state.running = False

    def run_detection(source):
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            st.error("Cannot open video source.")
            return
        st.session_state.running = True

        while st.session_state.running:
            ret, frame = cap.read()
            if not ret:
                break

            annotated, objects, danger, fall, wet, zone_viol, count = process_frame(frame)

            frame_ph.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_container_width=True)
            status_ph.markdown(render_status_card(danger, fall, wet, zone_viol, count), unsafe_allow_html=True)
            metrics_ph.markdown(render_metrics_html(), unsafe_allow_html=True)
            objects_ph.markdown(
                '<div class="section-header">🎯 Detected Objects</div>' + render_objects_html(objects),
                unsafe_allow_html=True
            )
            msgs_ph.markdown(render_messages_html(), unsafe_allow_html=True)
            time.sleep(0.03)

        cap.release()
        st.session_state.running = False

    if start_btn:
        if mode == "Webcam":
            run_detection(0)
        elif mode == "Video File":
            if 'uploaded_file' in locals() and uploaded_file:
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
                tfile.write(uploaded_file.read())
                tfile.flush()
                run_detection(tfile.name)
            else:
                st.warning("Please upload a video file first.")
        elif mode == "URL":
            if 'video_url' in locals() and video_url:
                urllib.request.urlretrieve(video_url, "temp_stream.mp4")
                run_detection("temp_stream.mp4")
            else:
                st.warning("Please enter a video URL.")

# ===================== TAB 2: ANALYTICS =====================
with tab2:
    st.markdown('<div class="section-header">📊 Detection Analytics</div>', unsafe_allow_html=True)

    if st.session_state.detection_history:
        df_h = pd.DataFrame(list(st.session_state.detection_history))
        x    = list(range(len(df_h)))

        col_a, col_b = st.columns(2)
        with col_a:
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=x, y=df_h["count"], mode="lines", name="Objects",
                line=dict(color="#00d4ff", width=2), fill="tozeroy", fillcolor="rgba(0,212,255,0.08)"))
            fig1.add_trace(go.Scatter(x=x, y=df_h["persons"], mode="lines", name="Persons",
                line=dict(color="#00ff99", width=2)))
            fig1.update_layout(title="Detection Timeline",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,27,42,0.8)",
                font=dict(color="#a0b8d0"), xaxis=dict(gridcolor="#1a3a5c"),
                yaxis=dict(gridcolor="#1a3a5c"), legend=dict(bgcolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            if st.session_state.object_counts:
                odf = pd.DataFrame(list(st.session_state.object_counts.items()),
                                   columns=["Object", "Count"]).sort_values("Count", ascending=False)
                colors = [
                    "#ff4444" if o in DANGEROUS_OBJECTS else
                    "#00aaff" if o == SLIP_ZONE_LABEL else
                    "#ff8800" if o == "person" else "#00d4ff"
                    for o in odf["Object"]
                ]
                fig2 = go.Figure(go.Bar(x=odf["Object"], y=odf["Count"], marker_color=colors))
                fig2.update_layout(title="Object Frequency",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,27,42,0.8)",
                    font=dict(color="#a0b8d0"), xaxis=dict(gridcolor="#1a3a5c"),
                    yaxis=dict(gridcolor="#1a3a5c"))
                st.plotly_chart(fig2, use_container_width=True)

        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=x, y=df_h["danger"], name="Danger", marker_color="#ff4444"))
        fig3.add_trace(go.Bar(x=x, y=df_h["fall"],   name="Fall",   marker_color="#ff8800"))
        if "wet" in df_h.columns:
            fig3.add_trace(go.Bar(x=x, y=df_h["wet"], name="Wet Floor", marker_color="#00aaff"))
        fig3.update_layout(title="Danger, Fall & Wet Floor Event Timeline", barmode="overlay",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,27,42,0.8)",
            font=dict(color="#a0b8d0"), xaxis=dict(gridcolor="#1a3a5c"),
            yaxis=dict(gridcolor="#1a3a5c"), legend=dict(bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No detection data yet. Start the detector to see analytics.")

# ===================== TAB 3: HEATMAP =====================
with tab3:
    st.markdown('<div class="section-header">🗺️ Activity Heatmap</div>', unsafe_allow_html=True)
    st.caption("Brighter = more activity. Wet floor events are weighted 2× on the heatmap.")

    grid = st.session_state.heatmap_grid
    if grid.max() > 0:
        fig_h = go.Figure(data=go.Heatmap(
            z=grid,
            colorscale=[[0,"#0a0e1a"],[0.3,"#003366"],[0.5,"#005599"],[0.7,"#00aaff"],[0.9,"#00ffcc"],[1.0,"#ff4444"]],
            showscale=True, colorbar=dict(tickfont=dict(color="#a0b8d0"))
        ))
        fig_h.update_layout(title="Spatial Activity Heatmap (incl. Slip Zones)",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,27,42,0.8)",
            font=dict(color="#a0b8d0"), height=420,
            xaxis=dict(showgrid=False, title="Horizontal Zone"),
            yaxis=dict(showgrid=False, title="Vertical Zone", autorange="reversed"))
        st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.info("Heatmap will appear after detection starts.")

    if st.button("Reset Heatmap"):
        st.session_state.heatmap_grid = np.zeros((10, 10), dtype=np.float32)
        st.rerun()

# ===================== TAB 4: REPORTS =====================
with tab4:
    st.markdown('<div class="section-header">📋 Detection Reports</div>', unsafe_allow_html=True)
    s = st.session_state.stats
    dur = str(datetime.now() - s["session_start"]).split(".")[0]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    for col, val, label, color in [
        (c1, s["total_detections"],  "Total Detections", "#00d4ff"),
        (c2, s["danger_events"],     "Danger Events",    "#ff4444"),
        (c3, s["fall_events"],       "Fall Events",      "#ff8800"),
        (c4, s["wet_floor_events"],  "Wet Floor Events", "#00aaff"),
        (c5, s["alerts_sent"],       "Alerts Sent",      "#ffaa00"),
        (c6, dur,                    "Session Duration", "#00cc66"),
    ]:
        col.markdown(f"""<div class="metric-card">
            <div class="metric-value" style="color:{color}">{val}</div>
            <div class="metric-label">{label}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    if os.path.exists(LOG_FILE):
        try:
            df_r = pd.read_csv(LOG_FILE, on_bad_lines='skip')
            if not df_r.empty:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    statuses = df_r["Status"].unique().tolist() if "Status" in df_r.columns else []
                    sel_status = st.multiselect("Filter Status", statuses, default=statuses)
                with col_f2:
                    objs = df_r["Object"].unique().tolist() if "Object" in df_r.columns else []
                    sel_obj = st.multiselect("Filter Object", objs, default=objs)

                filtered = df_r[df_r["Status"].isin(sel_status) & df_r["Object"].isin(sel_obj)]

                # Color-code the dataframe
                def highlight_status(row):
                    if row.get("Status") == "DANGER":
                        return ["background-color: #1a0a0a; color: #ff6666"] * len(row)
                    elif row.get("Status") == "FALL":
                        return ["background-color: #1a0a00; color: #ffaa44"] * len(row)
                    elif row.get("Status") == "WET":
                        return ["background-color: #0a1020; color: #44ccff"] * len(row)
                    return [""] * len(row)

                st.dataframe(
                    filtered.style.apply(highlight_status, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
                st.download_button("⬇ Download CSV",
                    data=filtered.to_csv(index=False),
                    file_name=f"safety_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv", use_container_width=True)
        except Exception as e:
            st.error(f"Error reading log: {e}")
    else:
        st.info("No log data yet.")

    if st.button("🗑 Clear Session Stats", use_container_width=True):
        st.session_state.stats = {
            "total_detections": 0, "danger_events": 0,
            "fall_events": 0, "wet_floor_events": 0,
            "persons_detected": 0, "alerts_sent": 0,
            "session_start": datetime.now()
        }
        st.session_state.detection_history.clear()
        st.session_state.object_counts.clear()
        st.rerun()