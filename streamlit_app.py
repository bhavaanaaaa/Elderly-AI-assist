"""
╔══════════════════════════════════════════════════════════════════╗
║        HOSPITAL SAFETY SYSTEM — ULTIMATE EDITION                ║
║  Features:                                                       ║
║  ✅ YOLOv8 Object Detection (all classes)                       ║
║  ✅ Wet Floor / Slip Zone Detection (HSV analysis)              ║
║  ✅ Pose-based Fall Detection (MediaPipe skeleton)              ║
║  ✅ PPE Detection (hard hat, mask, gloves, gown)                ║
║  ✅ DeepSORT Person Tracking (persistent IDs)                   ║
║  ✅ Multi-Camera RTSP Support                                   ║
║  ✅ Crowd Density Zone Alerts                                   ║
║  ✅ Claude AI Incident Report Generator                         ║
║  ✅ PostgreSQL / SQLite Logging                                 ║
║  ✅ SMS / Email / WhatsApp Alerts (Twilio)                      ║
║  ✅ Voice Alerts (multi-language)                               ║
║  ✅ Live Heatmap + Analytics                                    ║
║  ✅ Downloadable PDF/CSV Reports                                ║
╚══════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import cv2
import tempfile
import time
import os
import threading
import smtplib
import json
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ultralytics import YOLO
import csv
from datetime import datetime
import urllib.request
import pyttsx3
import queue
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from collections import defaultdict, deque
import numpy as np
import anthropic

# Optional imports with graceful fallback
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# MediaPipe with safe fallback
try:
    import mediapipe as mp

    try:
        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils
        MEDIAPIPE_AVAILABLE = True
        print("✅ MediaPipe loaded successfully")

    except Exception as e:
        print("❌ MediaPipe solutions error:", e)

        MEDIAPIPE_AVAILABLE = False
        mp_pose = None
        mp_drawing = None

except Exception as e:
    print("❌ MediaPipe import error:", e)

    MEDIAPIPE_AVAILABLE = False
    mp_pose = None
    mp_drawing = None
 
# DeepSORT Tracking
try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
    print("✅ DeepSORT loaded successfully")

except Exception as e:
    print("❌ DeepSORT import error:", e)

    DEEPSORT_AVAILABLE = False
    DeepSort = None   

# ===================== PAGE CONFIG =====================
st.set_page_config(
    page_title="Hospital Safety ULTIMATE",
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
.main-header p { color: #7090b0; font-size: 0.85rem; margin: 6px 0 0 0; font-family: 'JetBrains Mono', monospace; }
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
.metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, #00d4ff, #0066ff); }
.metric-value { font-size: 2rem; font-weight: 700; color: #00d4ff; font-family: 'JetBrains Mono', monospace; }
.metric-label { font-size: 0.72rem; color: #7090b0; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }
.status-danger { background: linear-gradient(135deg, #1a0a0a, #2a0f0f); border: 2px solid #ff4444; border-radius: 12px; padding: 14px 20px; margin-bottom: 10px; animation: pulse-danger 1.5s infinite; }
.status-safe   { background: linear-gradient(135deg, #0a1a0f, #0f2a15); border: 1px solid #00cc66; border-radius: 12px; padding: 14px 20px; margin-bottom: 10px; }
.status-fall   { background: linear-gradient(135deg, #1a0a00, #2a1500); border: 2px solid #ff8800; border-radius: 12px; padding: 14px 20px; margin-bottom: 10px; animation: pulse-danger 1s infinite; }
.status-wet    { background: linear-gradient(135deg, #0a1020, #0f1a35); border: 2px solid #00aaff; border-radius: 12px; padding: 14px 20px; margin-bottom: 10px; animation: pulse-wet 1.2s infinite; }
.status-ppe    { background: linear-gradient(135deg, #1a1500, #2a2000); border: 2px solid #ffdd00; border-radius: 12px; padding: 14px 20px; margin-bottom: 10px; animation: pulse-danger 1.3s infinite; }
.status-crowd  { background: linear-gradient(135deg, #10001a, #1a0030); border: 2px solid #cc44ff; border-radius: 12px; padding: 14px 20px; margin-bottom: 10px; animation: pulse-danger 1.1s infinite; }
@keyframes pulse-danger { 0%,100%{box-shadow:0 0 0 0 #ff444433} 50%{box-shadow:0 0 0 10px #ff444400} }
@keyframes pulse-wet    { 0%,100%{box-shadow:0 0 0 0 #00aaff33} 50%{box-shadow:0 0 0 10px #00aaff00} }
.object-tag { display:inline-block; padding:4px 12px; border-radius:20px; font-size:0.75rem; font-weight:500; margin:3px; font-family:'JetBrains Mono',monospace; }
.tag-danger { background:#ff000020; border:1px solid #ff4444; color:#ff6666; }
.tag-safe   { background:#00cc6620; border:1px solid #00cc66; color:#00ee88; }
.tag-warn   { background:#ffaa0020; border:1px solid #ffaa00; color:#ffcc44; }
.tag-fall   { background:#ff880020; border:1px solid #ff8800; color:#ffaa44; }
.tag-wet    { background:#00aaff20; border:1px solid #00aaff; color:#44ccff; }
.tag-ppe    { background:#ffdd0020; border:1px solid #ffdd00; color:#ffee66; }
.tag-crowd  { background:#cc44ff20; border:1px solid #cc44ff; color:#dd88ff; }
.tag-track  { background:#00ffcc20; border:1px solid #00ffcc; color:#44ffdd; }
.log-entry { background:#0d1b2a; border-left:3px solid #00d4ff; padding:7px 12px; margin:3px 0; border-radius:0 8px 8px 0; font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#a0b8d0; }
.log-entry.danger { border-left-color:#ff4444; color:#ff8888; }
.log-entry.warn   { border-left-color:#ffaa00; color:#ffcc66; }
.log-entry.fall   { border-left-color:#ff8800; color:#ffaa44; }
.log-entry.wet    { border-left-color:#00aaff; color:#44ccff; }
.log-entry.ppe    { border-left-color:#ffdd00; color:#ffee66; }
.log-entry.crowd  { border-left-color:#cc44ff; color:#dd88ff; }
.section-header { font-size:0.68rem; font-weight:600; text-transform:uppercase; letter-spacing:2px; color:#00d4ff; margin-bottom:10px; padding-bottom:5px; border-bottom:1px solid #00d4ff22; }
div[data-testid="stSidebarContent"] { background:linear-gradient(180deg,#080e18,#0a1220); border-right:1px solid #1a3a5c; }
.stButton>button { background:linear-gradient(90deg,#0066ff,#00aaff)!important; color:white!important; border:none!important; border-radius:8px!important; font-weight:600!important; padding:10px 24px!important; }
.stButton>button:hover { transform:translateY(-1px)!important; box-shadow:0 4px 20px #0066ff55!important; }
.person-track { background:#00ffcc15; border:1px solid #00ffcc44; border-radius:8px; padding:6px 10px; margin:3px 0; font-family:'JetBrains Mono',monospace; font-size:0.72rem; color:#00ffcc; }
.ai-report { background:#0a1a0a; border:1px solid #00cc6644; border-radius:12px; padding:16px; margin-top:10px; font-size:0.82rem; color:#a0d0a0; line-height:1.6; }
</style>
""", unsafe_allow_html=True)

# ===================== LANGUAGE CONFIG =====================
LANGUAGES = {
    "English": {
        "warning": "Warning", "detected": "detected",
        "fall_alert": "Fall detected! Person is on the ground!",
        "wet_floor": "Wet floor hazard! Slip risk detected!",
        "ppe_alert": "PPE violation! Staff missing protective equipment!",
        "crowd_alert": "Crowd density alert! Too many people in zone!",
        "zone_alert": "Zone alert", "in_zone": "in zone",
        "direction": {"left":"on the left","right":"on the right","front":"in front"},
        "distance":  {"very close":"very close","near":"nearby","far":"far away"},
        "safe":"✅ SAFE","danger":"🚨 DANGER","fall":"🆘 FALL DETECTED",
        "wet":"💧 WET FLOOR","ppe":"🦺 PPE VIOLATION","crowd":"👥 CROWD ALERT","persons":"Persons",
    },
    "Tamil": {
        "warning":"எச்சரிக்கை","detected":"கண்டறியப்பட்டது",
        "fall_alert":"விழுகை கண்டறியப்பட்டது! நபர் தரையில் இருக்கிறார்!",
        "wet_floor":"ஈரமான தரை ஆபத்து! வழுக்கல் அபாயம்!",
        "ppe_alert":"PPE மீறல்! பணியாளர் பாதுகாப்பு உபகரணம் இல்லை!",
        "crowd_alert":"கூட்ட அடர்த்தி எச்சரிக்கை! மண்டலத்தில் அதிக நபர்கள்!",
        "zone_alert":"மண்டல எச்சரிக்கை","in_zone":"மண்டலத்தில்",
        "direction":{"left":"இடதுபுறம்","right":"வலதுபுறம்","front":"முன்புறம்"},
        "distance":{"very close":"மிக அருகில்","near":"அருகில்","far":"தொலைவில்"},
        "safe":"✅ பாதுகாப்பு","danger":"🚨 அபாயம்","fall":"🆘 விழுகை",
        "wet":"💧 ஈரமான தரை","ppe":"🦺 PPE மீறல்","crowd":"👥 கூட்ட எச்சரிக்கை","persons":"நபர்கள்",
    },
    "Hindi": {
        "warning":"चेतावनी","detected":"पता चला",
        "fall_alert":"गिरावट पता चली! व्यक्ति जमीन पर है!",
        "wet_floor":"गीला फर्श खतरा! फिसलन का खतरा!",
        "ppe_alert":"PPE उल्लंघन! कर्मचारी सुरक्षा उपकरण के बिना!",
        "crowd_alert":"भीड़ घनत्व चेतावनी! क्षेत्र में बहुत अधिक लोग!",
        "zone_alert":"ज़ोन अलर्ट","in_zone":"ज़ोन में",
        "direction":{"left":"बाईं ओर","right":"दाईं ओर","front":"सामने"},
        "distance":{"very close":"बहुत पास","near":"पास","far":"दूर"},
        "safe":"✅ सुरक्षित","danger":"🚨 खतरा","fall":"🆘 गिरावट",
        "wet":"💧 गीला फर्श","ppe":"🦺 PPE उल्लंघन","crowd":"👥 भीड़ चेतावनी","persons":"व्यक्ति",
    },
    "Kannada": {
        "warning":"ಎಚ್ಚರಿಕೆ","detected":"ಕಂಡುಬಂದಿದೆ",
        "fall_alert":"ಬಿದ್ದುಹೋಗಿರುವುದು ಕಂಡುಬಂದಿದೆ!",
        "wet_floor":"ಒದ್ದೆ ನೆಲದ ಅಪಾಯ! ಜಾರುವ ಅಪಾಯ!",
        "ppe_alert":"PPE ಉಲ್ಲಂಘನೆ! ಸಿಬ್ಬಂದಿ ರಕ್ಷಣಾ ಸಾಧನಗಳಿಲ್ಲ!",
        "crowd_alert":"ಜನಸಂದಣಿ ಎಚ್ಚರಿಕೆ! ಪ್ರದೇಶದಲ್ಲಿ ತುಂಬಾ ಜನರಿದ್ದಾರೆ!",
        "zone_alert":"ಪ್ರದೇಶ ಎಚ್ಚರಿಕೆ","in_zone":"ಪ್ರದೇಶದಲ್ಲಿ",
        "direction":{"left":"ಎಡಭಾಗದಲ್ಲಿ","right":"ಬಲಭಾಗದಲ್ಲಿ","front":"ಮುಂದೆ"},
        "distance":{"very close":"ತುಂಬಾ ಹತ್ತಿರ","near":"ಹತ್ತಿರ","far":"ದೂರದಲ್ಲಿ"},
        "safe":"✅ ಸುರಕ್ಷಿತ","danger":"🚨 ಅಪಾಯ","fall":"🆘 ಬಿದ್ದುಹೋಗಿರುವುದು",
        "wet":"💧 ಒದ್ದೆ ನೆಲ","ppe":"🦺 PPE ಉಲ್ಲಂಘನೆ","crowd":"👥 ಜನಸಂದಣಿ","persons":"ವ್ಯಕ್ತಿಗಳು",
    },
    "French": {
        "warning":"Attention","detected":"détecté",
        "fall_alert":"Chute détectée! La personne est au sol!",
        "wet_floor":"Sol mouillé! Risque de glissade!",
        "ppe_alert":"Violation EPI! Personnel sans équipement de protection!",
        "crowd_alert":"Alerte densité de foule! Trop de personnes dans la zone!",
        "zone_alert":"Alerte de zone","in_zone":"dans la zone",
        "direction":{"left":"à gauche","right":"à droite","front":"devant"},
        "distance":{"very close":"très proche","near":"proche","far":"loin"},
        "safe":"✅ SÛR","danger":"🚨 DANGER","fall":"🆘 CHUTE",
        "wet":"💧 SOL MOUILLÉ","ppe":"🦺 VIOLATION EPI","crowd":"👥 ALERTE FOULE","persons":"Personnes",
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
            if text is None: break
            try:
                _engine.say(text)
                _engine.runAndWait()
            except Exception as e: print("Speech error:", e)
            st.session_state.speech_queue.task_done()
    threading.Thread(target=_speech_worker, daemon=True).start()
    st.session_state.speech_system = True

def speak(text, priority=False):
    if not st.session_state.get("voice_enabled", True): return
    now = time.time()
    if not priority and now - st.session_state.last_global_speak < 2: return
    st.session_state.last_global_speak = now
    st.session_state.speech_queue.put(text)

# ===================== SESSION STATE =====================
defaults = {
    "detection_history": deque(maxlen=500),
    "heatmap_grid":      np.zeros((10, 10), dtype=np.float32),
    "stats": {
        "total_detections": 0, "danger_events": 0, "fall_events": 0,
        "wet_floor_events": 0, "ppe_violations": 0, "crowd_alerts": 0,
        "persons_detected": 0, "alerts_sent": 0,
        "unique_persons": set(),
        "session_start": datetime.now()
    },
    "recent_messages":  deque(maxlen=30),
    "object_counts":    defaultdict(int),
    "running":          False,
    "voice_enabled":    True,
    "track_history":    defaultdict(lambda: deque(maxlen=30)),
    "incident_log":     [],
    "ai_report":        "",
    "multi_cam_frames": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ===================== CONSTANTS =====================
DB_FILE  = "hospital_safety.db"
LOG_FILE = "detection_log.csv"
SAFE_OBJECTS = [
    "person","chair","bed","couch","sofa","cup","bottle",
    "cell phone","laptop","clock","vase","book","remote",
    "keyboard","mouse","tv","monitor","potted plant","teddy bear"
]
DANGEROUS_OBJECTS = ["knife","scissors","gun","baseball bat","fire","smoke"]
PPE_CLASSES = {
    "NO-Hardhat": "hard hat missing",
    "NO-Mask":    "mask missing",
    "NO-Gloves":  "gloves missing",
    "NO-Safety Vest": "safety vest missing",
}
ALL_TRACKED  = list(set(SAFE_OBJECTS + DANGEROUS_OBJECTS))
SPEAK_COOLDOWN = 4
SLIP_ZONE_LABEL = "WET FLOOR"

# ===================== DATABASE =====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, object TEXT, direction TEXT,
            distance TEXT, status TEXT, person_count INTEGER,
            zone TEXT, track_id INTEGER, confidence REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, type TEXT, description TEXT, severity TEXT
        )
    """)
    conn.commit()
    conn.close()

def db_log(label, direction, distance, status, person_count, zone="General", track_id=-1, confidence=0.0):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            INSERT INTO detections (timestamp,object,direction,distance,status,person_count,zone,track_id,confidence)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), label, direction, distance,
              status, person_count, zone, track_id, round(confidence, 3)))
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB error:", e)

def db_log_incident(type_, description, severity="MEDIUM"):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            INSERT INTO incidents (timestamp,type,description,severity)
            VALUES (?,?,?,?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), type_, description, severity))
        conn.commit()
        conn.close()
        st.session_state.incident_log.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": type_, "desc": description, "severity": severity
        })
    except Exception as e:
        print("DB incident error:", e)

def init_csv():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "Timestamp","Object","Direction","Distance",
                "Status","PersonCount","Zone","TrackID","Confidence"
            ])

def log_event(label, direction, distance, status, person_count, zone="General", track_id=-1, confidence=0.0):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            label, direction, distance, status, person_count, zone, track_id, round(confidence, 3)
        ])
    db_log(label, direction, distance, status, person_count, zone, track_id, confidence)
    s = st.session_state.stats
    s["total_detections"] += 1
    if status == "DANGER":   s["danger_events"]   += 1
    elif status == "FALL":   s["fall_events"]     += 1
    elif status == "WET":    s["wet_floor_events"] += 1
    elif status == "PPE":    s["ppe_violations"]  += 1
    elif status == "CROWD":  s["crowd_alerts"]    += 1
    st.session_state.object_counts[label] += 1

# ===================== SIDEBAR =====================
with st.sidebar:
    st.markdown('<div class="section-header">⚙️ System Configuration</div>', unsafe_allow_html=True)
    language       = st.selectbox("🌐 Language", list(LANGUAGES.keys()), index=0)
    L              = LANGUAGES[language]
    model_size     = model_size = st.selectbox(
    "YOLO Model",
    ["wet_floor.pt", "yolov8n.pt"],
    index=0
    )
    conf_threshold = st.slider("Confidence Threshold", 0.2, 0.9, 0.4, 0.05)
    imgsz          = st.select_slider("Inference Size", [160,320,480,640], value=320)

    st.markdown('<div class="section-header" style="margin-top:16px">🔔 Alert Settings</div>', unsafe_allow_html=True)
    enable_sms = st.toggle("SMS Alerts (Twilio)", False)
    twilio_sid = twilio_token = twilio_from = nurse_phone = ""
    if enable_sms:
        twilio_sid   = st.text_input("Twilio SID",   type="password")
        twilio_token = st.text_input("Twilio Token", type="password")
        twilio_from  = st.text_input("From Number",  "+1234567890")
        nurse_phone  = st.text_input("Nurse Phone",  "+919876543210")

    enable_email = st.toggle("Email Alerts", False)
    email_sender = email_password = email_receiver = ""
    if enable_email:
        email_sender   = st.text_input("Sender Email")
        email_password = st.text_input("Email Password", type="password")
        email_receiver = st.text_input("Receiver Email")

    enable_whatsapp = st.toggle("WhatsApp (Twilio)", False)
    wa_sid = wa_token = wa_from = wa_to = ""
    if enable_whatsapp:
        wa_sid   = st.text_input("WA SID",   type="password", key="wa_sid")
        wa_token = st.text_input("WA Token", type="password", key="wa_tok")
        wa_from  = st.text_input("WA From",  "whatsapp:+14155238886")
        wa_to    = st.text_input("WA To",    "whatsapp:+919876543210")

    alert_cooldown = st.slider("Alert Cooldown (sec)", 5, 120, 30)

    st.markdown('<div class="section-header" style="margin-top:16px">🚧 Zone Settings</div>', unsafe_allow_html=True)
    restricted_zone = st.toggle("Restricted Zone Detection", False)
    zone_label = "General"
    zone_objects = []
    if restricted_zone:
        zone_label   = st.text_input("Zone Name", "ICU")
        zone_objects = st.multiselect("Alert objects in zone", ALL_TRACKED, default=DANGEROUS_OBJECTS)

    st.markdown('<div class="section-header" style="margin-top:16px">💧 Wet Floor Detection</div>', unsafe_allow_html=True)
    enable_wet_detection  = st.toggle("Wet Floor / Slip Detection", True)
    wet_area_ratio        = st.slider("Min Spill Size (% of frame)", 1, 20, 3) / 100
    wet_sensitivity       = st.slider("Detection Sensitivity", 1, 5, 3,
                                       help="Higher = detects more (may have false positives). "
                                            "Lower = only very obvious wet areas.")
    wet_show_debug        = st.toggle("Show Detection Debug Mask", False,
                                       help="Overlay the raw detection mask on frame for tuning")
    # Derive thresholds from sensitivity slider
    wet_brightness_thresh = max(60,  200 - wet_sensitivity * 25)   # 175→75
    wet_saturation_thresh = min(120, 20  + wet_sensitivity * 15)   # 35→95

    st.markdown('<div class="section-header" style="margin-top:16px">🦴 Pose & Fall Detection</div>', unsafe_allow_html=True)
    enable_pose     = st.toggle("Pose-based Fall Detection (MediaPipe)", MEDIAPIPE_AVAILABLE)
    fall_sensitivity = st.slider("Fall Sensitivity (bbox fallback)", 1, 5, 3)

    st.markdown('<div class="section-header" style="margin-top:16px">🦺 PPE Detection</div>', unsafe_allow_html=True)
    enable_ppe        = st.toggle("PPE Violation Detection", True)
    ppe_model_path    = st.text_input("PPE Model Path (optional)", "ppe_yolov8.pt",
                                       help="Leave default to use base YOLO; train custom for best results")

    st.markdown('<div class="section-header" style="margin-top:16px">👥 Crowd Control</div>', unsafe_allow_html=True)
    enable_crowd      = st.toggle("Crowd Density Alerts", True)
    crowd_threshold   = st.slider("Max Persons per Zone", 2, 20, 5)

    st.markdown('<div class="section-header" style="margin-top:16px">🎯 Tracking</div>', unsafe_allow_html=True)
    enable_tracking   = st.toggle("DeepSORT Person Tracking", DEEPSORT_AVAILABLE)

    st.markdown('<div class="section-header" style="margin-top:16px">📹 Multi-Camera</div>', unsafe_allow_html=True)
    enable_multicam   = st.toggle("Multi-Camera Mode", False)
    cam_urls          = []
    if enable_multicam:
        cam_str = st.text_area("Camera URLs (one per line)", "0\nrtsp://cam2\nrtsp://cam3")
        cam_urls = [c.strip() for c in cam_str.strip().split("\n") if c.strip()]

    st.markdown('<div class="section-header" style="margin-top:16px">🤖 Claude AI Reports</div>', unsafe_allow_html=True)
    enable_ai_report  = st.toggle("AI Incident Reports (Claude)", True)
    anthropic_key     = st.text_input("Anthropic API Key", type="password",
                                       help="Required for AI report generation")

    st.markdown('<div class="section-header" style="margin-top:16px">🎨 Display</div>', unsafe_allow_html=True)
    enable_voice      = st.toggle("Voice Alerts", True)
    st.session_state.voice_enabled = enable_voice

# ===================== MODEL LOADING =====================
@st.cache_resource
def load_model(size):
    return YOLO(size)

@st.cache_resource
def load_ppe_model(path):
    if os.path.exists(path):
        return YOLO(path)
    return None

@st.cache_resource
def load_tracker():
    if DEEPSORT_AVAILABLE:
        return DeepSort(max_age=30, n_init=2, nms_max_overlap=0.7, max_cosine_distance=0.3)
    return None

@st.cache_resource
def load_pose():
    if MEDIAPIPE_AVAILABLE:
        return mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5)
    return None

model     = load_model(model_size)
ppe_model = load_ppe_model(ppe_model_path) if enable_ppe else None
tracker   = load_tracker() if enable_tracking else None
pose_det  = load_pose() if enable_pose else None

# ===================== HELPERS =====================
def get_direction(cx, w):
    if cx < w / 3:   return "left"
    if cx > 2*w / 3: return "right"
    return "front"

def get_distance_ratio(box_area, frame_area):
    ratio = box_area / frame_area
    if ratio > 0.3:  return "very close"
    if ratio > 0.1:  return "near"
    return "far"

def update_heatmap(cx, cy, w, h, weight=1):
    gx = min(int(cx / w * 10), 9)
    gy = min(int(cy / h * 10), 9)
    st.session_state.heatmap_grid[gy][gx] += weight

# ===================== WET FLOOR DETECTION (MULTI-METHOD) =====================
def _method_glossy_reflection(hsv, floor_mask):
    """
    Method 1 — Indoor glossy spill:
    High brightness + low saturation = colorless reflective liquid (water on tiles).
    """
    low_sat  = cv2.inRange(hsv[:,:,1], 0, 40)
    high_val = cv2.inRange(hsv[:,:,2], 180, 255)
    mask = cv2.bitwise_and(low_sat, high_val)
    return cv2.bitwise_and(mask, floor_mask)

def _method_dark_wet_ground(hsv, floor_mask):
    """
    Method 2 — Outdoor / dark wet surface:
    Wet outdoor ground (like your video) is DARKER than dry ground,
    has mid-range saturation (brownish/grey tones), and shows
    high local variance due to reflections of surroundings.
    Detects water puddles, flooded corridors, wet concrete/tiles.
    """
    h_ch, s_ch, v_ch = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]
    # Wet outdoor ground: mid brightness (not too dark, not too bright)
    mid_val  = cv2.inRange(v_ch, 40, 180)
    # Low-mid saturation (grey-ish wet ground, not dry brown dirt)
    low_sat  = cv2.inRange(s_ch, 0, 80)
    base     = cv2.bitwise_and(mid_val, low_sat)
    base     = cv2.bitwise_and(base, floor_mask)
    return base

def _method_reflection_mirror(gray, floor_mask):
    """
    Method 3 — Mirror/puddle reflection detection:
    Water puddles create near-perfect horizontal mirror reflections.
    We detect by finding vertically symmetric bright patches.
    Works best on standing water and flooded floors.
    """
    h = gray.shape[0]
    # Compare top half of floor region with flipped version
    floor_start = int(h * 0.4)
    floor_gray  = gray[floor_start:, :]
    fh = floor_gray.shape[0]
    if fh < 10:
        return np.zeros_like(gray)
    mid  = fh // 2
    top  = floor_gray[:mid, :]
    bot  = floor_gray[mid:fh, :]
    bot_flipped = cv2.flip(bot[:min(mid, bot.shape[0]),:], 0)
    diff = cv2.absdiff(top[:bot_flipped.shape[0],:], bot_flipped)
    # Low diff = mirror-like = water
    mirror_mask = cv2.inRange(diff, 0, 35)
    # Expand back to full frame size
    full_mask = np.zeros_like(gray)
    full_mask[floor_start:floor_start + mirror_mask.shape[0], :] = mirror_mask
    return cv2.bitwise_and(full_mask, floor_mask)

def _method_local_variance(gray, floor_mask):
    """
    Method 4 — High local variance (ripples / texture noise):
    Water surfaces have characteristic fine-grained variance —
    ripples, reflections, surface distortions.
    Uses local standard deviation as a texture feature.
    """
    gray_f   = gray.astype(np.float32)
    mean_sq  = cv2.blur(gray_f**2, (9,9))
    mean_    = cv2.blur(gray_f,    (9,9))
    variance = np.clip(mean_sq - mean_**2, 0, None)
    std_map  = np.sqrt(variance).astype(np.uint8)
    # Water: moderate variance (not flat = 0, not noisy = 255)
    var_mask = cv2.inRange(std_map, 8, 55)
    return cv2.bitwise_and(var_mask, floor_mask)

def _method_blue_hue_water(hsv, floor_mask):
    """
    Method 5 — Blue/cyan hue detection:
    Water often reflects the sky (outdoors) or fluorescent lights (indoors),
    giving a characteristic blue-cyan tint.
    """
    # Blue-cyan hue range in HSV (hue 90–130)
    blue_mask = cv2.inRange(hsv, (90,10,40), (130,180,240))
    return cv2.bitwise_and(blue_mask, floor_mask)

def detect_wet_floor(frame):
    """
    Robust wet floor detection combining 5 complementary methods:
      1. Glossy indoor reflection  (bright + desaturated)
      2. Dark wet outdoor ground   (mid-brightness + low saturation)
      3. Mirror/puddle reflection  (vertical symmetry)
      4. Local variance texture    (water ripple noise)
      5. Blue-hue water tint       (sky/light reflection colour)

    A pixel is flagged wet if ANY 2+ methods agree on it.
    This handles: indoor spills, outdoor puddles, flooded corridors,
    wet concrete, water on tiles, and standing water.
    """
    h, w = frame.shape[:2]

    # Pre-compute colour spaces once
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Floor region mask — lower 60% of frame
    floor_mask = np.zeros((h, w), dtype=np.uint8)
    floor_mask[int(h * 0.38):, :] = 255

    # Run all 5 methods
    m1 = _method_glossy_reflection(hsv, floor_mask)
    m2 = _method_dark_wet_ground(hsv, floor_mask)
    m3 = _method_reflection_mirror(gray, floor_mask)
    m4 = _method_local_variance(gray, floor_mask)
    m5 = _method_blue_hue_water(hsv, floor_mask)

    # Vote: pixel is wet if 2 or more methods flag it
    vote = (
        (m1 > 0).astype(np.uint8) +
        (m2 > 0).astype(np.uint8) +
        (m3 > 0).astype(np.uint8) +
        (m4 > 0).astype(np.uint8) +
        (m5 > 0).astype(np.uint8)
    )
    combined = np.where(vote >= 2, 255, 0).astype(np.uint8)

    # Morphological cleanup
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12, 12))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_close)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  k_open)

    # Find and filter contours by size
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    spill_regions = []
    min_area = w * h * wet_area_ratio
    for cnt in contours:
        if cv2.contourArea(cnt) > min_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Reject very thin vertical slivers (likely wall/object edges, not floor)
            aspect = bw / max(bh, 1)
            if aspect > 0.4:  # wet areas are wider than tall
                spill_regions.append((x, y, x + bw, y + bh))

    return spill_regions

def draw_slip_zones(frame, spill_regions):
    for i, (x1,y1,x2,y2) in enumerate(spill_regions):
        overlay = frame.copy()
        # Cyan-blue fill for water
        cv2.rectangle(overlay, (x1,y1), (x2,y2), (200, 160, 0), -1)
        cv2.addWeighted(overlay, 0.30, frame, 0.70, 0, frame)

        # Diagonal hatching (water ripple visual cue)
        hatch_gap = 16
        region_h = y2 - y1
        for xh in range(x1 - region_h, x2 + region_h, hatch_gap):
            px1 = max(x1, xh)
            py1 = y1 + max(0, x1 - xh)
            px2 = min(x2, xh + region_h)
            py2 = y1 + min(region_h, (xh + region_h) - x1)
            if px1 < px2 and py1 < py2:
                cv2.line(frame, (px1, py1), (px2, py2), (160, 210, 255), 1, cv2.LINE_AA)

        # Thick glowing border
        cv2.rectangle(frame, (x1,y1), (x2,y2), (0, 255, 255), 3)
        cv2.rectangle(frame, (x1-1,y1-1), (x2+1,y2+1), (0, 180, 220), 1)

        # Label pill
        label = f"WET FLOOR / SLIP RISK #{i+1}"
        font_scale = 0.65
        thickness  = 2
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        lx1, ly1 = x1, max(0, y1 - th - 14)
        lx2, ly2 = x1 + tw + 14, y1
        cv2.rectangle(frame, (lx1, ly1), (lx2, ly2), (0, 160, 200), -1)
        cv2.rectangle(frame, (lx1, ly1), (lx2, ly2), (0, 220, 255), 1)
        cv2.putText(frame, label, (lx1 + 6, ly2 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        # Water-drop icons in corner
        for dot_x, dot_y, r in [(x2-14, y1+14, 6), (x2-28, y1+20, 4), (x2-8, y1+26, 4)]:
            if x1 < dot_x < x2 and y1 < dot_y < y2:
                cv2.circle(frame, (dot_x, dot_y), r, (0, 230, 255), -1)

    return frame

# ===================== POSE-BASED FALL DETECTION =====================
def detect_fall_pose(frame, pose_detector):
    """Use MediaPipe skeleton to detect falls — hip Y > shoulder Y = fallen."""
    if pose_detector is None:
        return False, frame
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose_detector.process(rgb)
    fallen = False
    if results.pose_landmarks:
        lm = results.pose_landmarks.landmark
        h, w = frame.shape[:2]
        # Key landmarks
        left_shoulder  = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        left_hip       = lm[mp_pose.PoseLandmark.LEFT_HIP]
        right_hip      = lm[mp_pose.PoseLandmark.RIGHT_HIP]
        shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
        hip_y      = (left_hip.y     + right_hip.y)      / 2
        # If hips are at same level or above shoulders → fallen / lying
        if hip_y >= shoulder_y - 0.08:
            fallen = True
            cv2.putText(frame, "⚠ FALL POSE DETECTED", (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,80,255), 2, cv2.LINE_AA)
        # Draw skeleton overlay
        mp_drawing.draw_landmarks(
            frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0,200,255), thickness=2, circle_radius=2),
            mp_drawing.DrawingSpec(color=(0,255,180), thickness=2),
        )
    return fallen, frame

def is_person_fallen_bbox(box, w, h):
    """Fallback bbox-based fall detection when MediaPipe not available."""
    x1,y1,x2,y2 = [float(v) for v in box.xyxy[0]]
    bw, bh = x2-x1, y2-y1
    if bh == 0: return False
    aspect_ratio = bw / bh
    center_y     = (y1+y2) / 2
    threshold    = 0.8 + (5-fall_sensitivity) * 0.15
    return aspect_ratio > threshold and center_y > h * 0.35

# ===================== PPE DETECTION =====================
def detect_ppe_violations(frame, ppe_model_instance):
    """Detect missing PPE using a custom-trained YOLO model."""
    violations = []
    if ppe_model_instance is None:
        return violations, frame
    results = ppe_model_instance.predict(frame, conf=0.45, imgsz=320, verbose=False)
    for box in (results[0].boxes or []):
        label = ppe_model_instance.names[int(box.cls[0])]
        if label in PPE_CLASSES:
            x1,y1,x2,y2 = [int(v) for v in box.xyxy[0]]
            violations.append({"label": label, "desc": PPE_CLASSES[label],
                                "cx": (x1+x2)//2, "cy": (y1+y2)//2})
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,230,255), 2)
            cv2.rectangle(frame, (x1, y1-26), (x1+len(label)*10+10, y1), (0,180,200), -1)
            cv2.putText(frame, f"NO PPE: {label}", (x1+4, y1-8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1, cv2.LINE_AA)
    return violations, frame

# ===================== CROWD DENSITY =====================
def check_crowd_density(person_boxes, frame_w, frame_h):
    """Divide frame into 4 quadrants and check if any exceeds threshold."""
    zones = {
        "Top-Left":     (0, 0, frame_w//2, frame_h//2),
        "Top-Right":    (frame_w//2, 0, frame_w, frame_h//2),
        "Bottom-Left":  (0, frame_h//2, frame_w//2, frame_h),
        "Bottom-Right": (frame_w//2, frame_h//2, frame_w, frame_h),
    }
    alerts = []
    for zone_name, (zx1,zy1,zx2,zy2) in zones.items():
        count = 0
        for (px1,py1,px2,py2) in person_boxes:
            cx, cy = (px1+px2)//2, (py1+py2)//2
            if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                count += 1
        if count > crowd_threshold:
            alerts.append({"zone": zone_name, "count": count})
    return alerts

def draw_crowd_overlay(frame, crowd_alerts, frame_w, frame_h):
    zone_rects = {
        "Top-Left":     (0,0,frame_w//2,frame_h//2),
        "Top-Right":    (frame_w//2,0,frame_w,frame_h//2),
        "Bottom-Left":  (0,frame_h//2,frame_w//2,frame_h),
        "Bottom-Right": (frame_w//2,frame_h//2,frame_w,frame_h),
    }
    for alert in crowd_alerts:
        rx1,ry1,rx2,ry2 = zone_rects[alert["zone"]]
        overlay = frame.copy()
        cv2.rectangle(overlay, (rx1,ry1), (rx2,ry2), (180,0,255), -1)
        cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
        cv2.rectangle(frame, (rx1,ry1), (rx2,ry2), (200,0,255), 2)
        cv2.putText(frame, f"CROWD: {alert['count']} persons", (rx1+8, ry1+28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220,80,255), 2, cv2.LINE_AA)
    return frame

# ===================== DEEPSORT TRACKING =====================
def run_tracking(boxes_data, frame):
    """Convert YOLO boxes to DeepSORT detections and update tracker."""
    if tracker is None or not enable_tracking:
        return {}
    detections = []
    for (x1,y1,x2,y2,conf,cls_id) in boxes_data:
        if model.names[int(cls_id)] == "person":
            detections.append(([x1,y1,x2-x1,y2-y1], conf, "person"))
    tracks = tracker.update_tracks(detections, frame=frame)
    result = {}
    for track in tracks:
        if not track.is_confirmed(): continue
        tid = track.track_id
        ltrb = track.to_ltrb()
        result[tid] = [int(v) for v in ltrb]
        st.session_state.stats["unique_persons"].add(tid)
        cx = (ltrb[0]+ltrb[2])//2
        cy = (ltrb[1]+ltrb[3])//2
        st.session_state.track_history[tid].append((int(cx), int(cy)))
    return result

def draw_tracks(frame, track_map):
    """Draw track IDs and motion trails."""

    for tid, (x1, y1, x2, y2) in track_map.items():

        # Convert track ID safely to integer
        try:
            tid_num = int(tid)
        except:
            tid_num = 0

        # Generate unique color for each person
        color = (
            (tid_num * 47) % 256,
            (tid_num * 83) % 256,
            (tid_num * 131) % 256
        )

        # Draw tracking box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        # Label background
        cv2.rectangle(frame, (x1, y1 - 22), (x1 + 70, y1), color, -1)

        # Person ID text
        cv2.putText(
            frame,
            f"ID:{tid_num}",
            (x1 + 4, y1 - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA
        )

        # Motion trail
        hist = list(st.session_state.track_history[tid])

        for i in range(1, len(hist)):
            alpha = i / len(hist)

            trail_color = (
                int(color[0] * alpha),
                int(color[1] * alpha),
                int(color[2] * alpha)
            )

            cv2.line(frame, hist[i - 1], hist[i], trail_color, 2)

    return frame

# ===================== ALERT SYSTEM =====================
_alert_last = {"sms": 0, "email": 0, "wa": 0}

def _send_sms(msg):
    if not enable_sms or not TWILIO_AVAILABLE or not twilio_sid: return
    if time.time() - _alert_last["sms"] < alert_cooldown: return
    try:
        TwilioClient(twilio_sid, twilio_token).messages.create(
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
    if not enable_whatsapp or not TWILIO_AVAILABLE or not wa_sid: return
    if time.time() - _alert_last["wa"] < alert_cooldown: return
    try:
        TwilioClient(wa_sid, wa_token).messages.create(
            body=msg, from_=wa_from, to=wa_to)
        _alert_last["wa"] = time.time()
        st.session_state.stats["alerts_sent"] += 1
    except Exception as e: print("WA:", e)

def fire_alerts(message):
    threading.Thread(target=_send_sms,   args=(message,), daemon=True).start()
    threading.Thread(target=_send_email, args=(message,), daemon=True).start()
    threading.Thread(target=_send_wa,    args=(message,), daemon=True).start()

# ===================== CLAUDE AI REPORT =====================
def generate_ai_report(incident_data: list, stats: dict) -> str:
    """Generate a human-readable incident report using Claude API."""
    if not enable_ai_report or not anthropic_key:
        return "⚠️ Enable AI Reports and provide Anthropic API key in sidebar."
    if not incident_data:
        return "No incidents recorded yet. Start detection to generate reports."
    try:
        client = anthropic.Anthropic(api_key=anthropic_key)
        prompt = f"""You are a hospital safety officer. Generate a professional incident report based on the following detection data.

DETECTION STATISTICS:
- Total detections: {stats['total_detections']}
- Danger events: {stats['danger_events']}
- Fall events: {stats['fall_events']}
- Wet floor events: {stats['wet_floor_events']}
- PPE violations: {stats['ppe_violations']}
- Crowd alerts: {stats['crowd_alerts']}
- Unique persons tracked: {len(stats['unique_persons'])}
- Alerts sent: {stats['alerts_sent']}
- Session start: {stats['session_start'].strftime('%Y-%m-%d %H:%M:%S')}

INCIDENTS LOG:
{json.dumps(incident_data[-20:], indent=2)}

Write a concise, professional hospital safety incident report including:
1. Executive Summary
2. Key Findings
3. High-Priority Incidents
4. Risk Assessment
5. Recommended Actions

Keep it under 400 words. Use clear medical/safety language."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"AI report error: {str(e)}\nCheck your Anthropic API key."

# ===================== MAIN FRAME PROCESSOR =====================
_obj_last_spoken = {}

def process_frame(frame, cam_id=0):
    global _obj_last_spoken
    h, w = frame.shape[:2]
    now = time.time()
    detected_objects  = set()
    danger_detected   = False
    fall_detected     = False
    wet_floor_detected= False
    ppe_violated      = False
    crowd_alerted     = False
    person_boxes_raw  = []

    # ── 1. YOLO Detection ──────────────────────────────────────────
    results  = model.predict(frame, conf=conf_threshold, imgsz=imgsz, verbose=False)
    annotated = results[0].plot()
    boxes_data = []
    person_count = 0

    if results[0].boxes is not None:
        for box in results[0].boxes:
            label = model.names[int(box.cls[0])]
            x1,y1,x2,y2 = [int(v) for v in box.xyxy[0]]
            conf_val = float(box.conf[0])
            boxes_data.append((x1,y1,x2,y2,conf_val,int(box.cls[0])))
            if label == "person":
                person_count += 1
                person_boxes_raw.append((x1,y1,x2,y2))
            detected_objects.add(label)
            cx, cy = (x1+x2)//2, (y1+y2)//2
            update_heatmap(cx, cy, w, h)

        st.session_state.stats["persons_detected"] = max(
            st.session_state.stats["persons_detected"], person_count)

    # ── 2. DeepSORT Tracking ───────────────────────────────────────
    track_map = {}
    if enable_tracking and DEEPSORT_AVAILABLE:
        track_map = run_tracking(boxes_data, frame)
        annotated = draw_tracks(annotated, track_map)

    # ── 3. Wet Floor Detection ─────────────────────────────────────
    if enable_wet_detection:
        spill_regions = detect_wet_floor(frame)
        wet_floor_detected = len(spill_regions) > 0

        # Debug mask overlay — shows exactly what the detector sees
        if wet_show_debug:
            hsv_dbg  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            gray_dbg = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            fmask    = np.zeros((h,w), dtype=np.uint8)
            fmask[int(h*0.38):,:] = 255
            m1 = _method_glossy_reflection(hsv_dbg, fmask)
            m2 = _method_dark_wet_ground(hsv_dbg, fmask)
            m3 = _method_reflection_mirror(gray_dbg, fmask)
            m4 = _method_local_variance(gray_dbg, fmask)
            m5 = _method_blue_hue_water(hsv_dbg, fmask)
            vote = ((m1>0).astype(np.uint8)+(m2>0).astype(np.uint8)+
                    (m3>0).astype(np.uint8)+(m4>0).astype(np.uint8)+(m5>0).astype(np.uint8))
            debug_color = np.zeros_like(annotated)
            debug_color[vote>=1] = [0,80,0]    # 1 vote  = dark green
            debug_color[vote>=2] = [0,180,120] # 2 votes = teal (flagged)
            debug_color[vote>=3] = [0,230,255] # 3+ votes = cyan (strong)
            cv2.addWeighted(debug_color, 0.45, annotated, 0.55, 0, annotated)
            # Legend
            for i,(txt,col) in enumerate([("1 vote (weak)","#004d00"),
                                           ("2+ votes (WET)","#00b478"),
                                           ("3+ votes (STRONG)","#00e6ff")]):
                cv2.putText(annotated, txt, (8, 18+i*20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            tuple(int(col[i:i+2],16) for i in (5,3,1)), 1, cv2.LINE_AA)

        if wet_floor_detected:
            annotated = draw_slip_zones(annotated, spill_regions)
            for (x1,y1,x2,y2) in spill_regions:
                update_heatmap((x1+x2)//2, (y1+y2)//2, w, h, weight=2)
            if now - _obj_last_spoken.get("wet_floor", 0) > SPEAK_COOLDOWN:
                msg = L["wet_floor"]
                speak(msg, priority=True)
                st.session_state.recent_messages.appendleft(
                    {"text": msg, "type": "wet", "time": datetime.now().strftime("%H:%M:%S")})
                _obj_last_spoken["wet_floor"] = now
                log_event(SLIP_ZONE_LABEL,"center","very close","WET",person_count,
                          zone_label if restricted_zone else "General")
                db_log_incident("WET_FLOOR", f"Wet floor detected — {len(spill_regions)} zone(s)", "HIGH")
                fire_alerts(f"💧 WET FLOOR detected [{datetime.now().strftime('%H:%M:%S')}] — Cam {cam_id}")

    # ── 4. Pose-based Fall Detection ───────────────────────────────
    if enable_pose and MEDIAPIPE_AVAILABLE and pose_det is not None:
        fallen_pose, annotated = detect_fall_pose(annotated, pose_det)
        if fallen_pose:
            fall_detected = True
    # Bbox fallback
    if not fall_detected and results[0].boxes is not None:
        for box in results[0].boxes:
            if model.names[int(box.cls[0])] == "person":
                if is_person_fallen_bbox(box, w, h):
                    fall_detected = True
                    break
    if fall_detected and now - _obj_last_spoken.get("fall", 0) > SPEAK_COOLDOWN:
        msg = L["fall_alert"]
        speak(msg, priority=True)
        st.session_state.recent_messages.appendleft(
            {"text": msg, "type": "fall", "time": datetime.now().strftime("%H:%M:%S")})
        _obj_last_spoken["fall"] = now
        log_event("person","center","very close","FALL",person_count,
                  zone_label if restricted_zone else "General")
        db_log_incident("FALL", f"Person fall detected — Cam {cam_id}", "CRITICAL")
        fire_alerts(f"🆘 FALL DETECTED [{datetime.now().strftime('%H:%M:%S')}] — Cam {cam_id}")

    # ── 5. PPE Detection ───────────────────────────────────────────
    if enable_ppe and ppe_model is not None:
        violations, annotated = detect_ppe_violations(annotated, ppe_model)
        if violations:
            ppe_violated = True
            for v in violations:
                if now - _obj_last_spoken.get(f"ppe_{v['label']}", 0) > SPEAK_COOLDOWN * 2:
                    speak(L["ppe_alert"], priority=True)
                    _obj_last_spoken[f"ppe_{v['label']}"] = now
                    st.session_state.recent_messages.appendleft(
                        {"text": f"PPE: {v['desc']}", "type": "ppe",
                         "time": datetime.now().strftime("%H:%M:%S")})
                    log_event(v["label"],"center","near","PPE",person_count,
                              zone_label if restricted_zone else "General")
                    db_log_incident("PPE_VIOLATION", f"{v['desc']} — Cam {cam_id}", "MEDIUM")

    # ── 6. Crowd Density ──────────────────────────────────────────
    if enable_crowd and person_boxes_raw:
        crowd_alerts_list = check_crowd_density(person_boxes_raw, w, h)
        if crowd_alerts_list:
            crowd_alerted = True
            annotated = draw_crowd_overlay(annotated, crowd_alerts_list, w, h)
            if now - _obj_last_spoken.get("crowd", 0) > SPEAK_COOLDOWN * 2:
                speak(L["crowd_alert"], priority=True)
                _obj_last_spoken["crowd"] = now
                for ca in crowd_alerts_list:
                    st.session_state.recent_messages.appendleft(
                        {"text": f"Crowd: {ca['count']} in {ca['zone']}",
                         "type": "crowd", "time": datetime.now().strftime("%H:%M:%S")})
                    log_event("crowd",ca["zone"],"zone","CROWD",ca["count"],ca["zone"])
                    db_log_incident("CROWD_DENSITY",
                                    f"{ca['count']} persons in {ca['zone']} — Cam {cam_id}", "MEDIUM")

    # ── 7. YOLO Object-level logic (danger / zone) ─────────────────
    if results[0].boxes is not None:
        for box in results[0].boxes:
            label    = model.names[int(box.cls[0])]
            conf_val = float(box.conf[0])
            x1,y1,x2,y2 = [int(v) for v in box.xyxy[0]]
            cx, cy   = (x1+x2)//2, (y1+y2)//2
            direction= get_direction(cx, w)
            distance = get_distance_ratio((x2-x1)*(y2-y1), w*h)
            is_danger= label in DANGEROUS_OBJECTS
            is_zone_v= restricted_zone and label in zone_objects
            if is_danger: danger_detected = True
            status = "DANGER" if is_danger else "SAFE"
            log_event(label, direction, distance, status, person_count,
                      zone_label if restricted_zone else "General",
                      confidence=conf_val)
            last_t = _obj_last_spoken.get(label, 0)
            if now - last_t > SPEAK_COOLDOWN:
                dir_txt  = L["direction"].get(direction, direction)
                dist_txt = L["distance"].get(distance, distance)
                if is_danger:
                    msg = f"{L['warning']}! {label} {L['detected']} {dir_txt}, {dist_txt}"
                    speak(msg, priority=True)
                    st.session_state.recent_messages.appendleft(
                        {"text": msg, "type": "danger", "time": datetime.now().strftime("%H:%M:%S")})
                    db_log_incident("DANGEROUS_OBJECT",
                                    f"{label} detected {dir_txt} — Cam {cam_id}", "HIGH")
                    fire_alerts(f"⚠️ DANGER: {label} detected [{datetime.now().strftime('%H:%M:%S')}]")
                elif is_zone_v:
                    msg = f"{L['zone_alert']}! {label} {L['in_zone']} {zone_label}"
                    speak(msg, priority=True)
                    st.session_state.recent_messages.appendleft(
                        {"text": msg, "type": "warn", "time": datetime.now().strftime("%H:%M:%S")})
                _obj_last_spoken[label] = now

    st.session_state.detection_history.append({
        "time":    datetime.now().strftime("%H:%M:%S"),
        "count":   len(detected_objects),
        "persons": person_count,
        "danger":  int(danger_detected),
        "fall":    int(fall_detected),
        "wet":     int(wet_floor_detected),
        "ppe":     int(ppe_violated),
        "crowd":   int(crowd_alerted),
    })

    for obj in list(_obj_last_spoken.keys()):
        if obj not in detected_objects and not obj.startswith(("ppe_","wet","fall","crowd")):
            del _obj_last_spoken[obj]

    return (annotated, detected_objects, danger_detected, fall_detected,
            wet_floor_detected, ppe_violated, crowd_alerted, person_count, track_map)

# ===================== RENDER HELPERS =====================
def render_status_card(danger, fall, wet, ppe, crowd, count, tracks):
    L = LANGUAGES[language]
    if fall:   card_class,status_text,color = "status-fall",  L["fall"],   "#ff8800"
    elif danger:card_class,status_text,color = "status-danger",L["danger"], "#ff4444"
    elif ppe:  card_class,status_text,color = "status-ppe",   L["ppe"],    "#ffdd00"
    elif crowd:card_class,status_text,color = "status-crowd", L["crowd"],  "#cc44ff"
    elif wet:  card_class,status_text,color = "status-wet",   L["wet"],    "#00aaff"
    else:      card_class,status_text,color = "status-safe",  L["safe"],   "#00cc66"

    extras = ""
    if wet:   extras += '<div style="color:#00aaff;font-size:0.78rem;margin-top:3px">💧 Wet Floor Detected</div>'
    if ppe:   extras += '<div style="color:#ffdd00;font-size:0.78rem;margin-top:3px">🦺 PPE Violation</div>'
    if crowd: extras += '<div style="color:#cc44ff;font-size:0.78rem;margin-top:3px">👥 Crowd Alert</div>'
    track_html = ""
    if tracks:
        track_html = f'<div style="color:#00ffcc;font-size:0.78rem;margin-top:3px">🎯 Tracking {len(tracks)} persons</div>'
    return f"""
    <div class="{card_class}">
        <div style="font-size:1.4rem;font-weight:700;color:{color}">{status_text}</div>
        <div style="color:#7090b0;font-size:0.82rem;margin-top:6px">
            👥 {L['persons']}: <b style="color:#00d4ff">{count}</b> &nbsp;|&nbsp;
            🆔 Unique: <b style="color:#00ffcc">{len(st.session_state.stats['unique_persons'])}</b>
        </div>
        {extras}{track_html}
    </div>"""

def render_metrics_html():
    s = st.session_state.stats
    return f"""
    <div class="metric-card"><div class="metric-value">{s['total_detections']}</div><div class="metric-label">Detections</div></div>
    <div class="metric-card"><div class="metric-value" style="color:#ff4444">{s['danger_events']}</div><div class="metric-label">Danger</div></div>
    <div class="metric-card"><div class="metric-value" style="color:#ff8800">{s['fall_events']}</div><div class="metric-label">Falls</div></div>
    <div class="metric-card"><div class="metric-value" style="color:#00aaff">{s['wet_floor_events']}</div><div class="metric-label">Wet Floor</div></div>
    <div class="metric-card"><div class="metric-value" style="color:#ffdd00">{s['ppe_violations']}</div><div class="metric-label">PPE Violations</div></div>
    <div class="metric-card"><div class="metric-value" style="color:#cc44ff">{s['crowd_alerts']}</div><div class="metric-label">Crowd Alerts</div></div>
    <div class="metric-card"><div class="metric-value" style="color:#ffaa00">{s['alerts_sent']}</div><div class="metric-label">Alerts Sent</div></div>"""

def render_objects_html(objects):
    if not objects:
        return '<span style="color:#7090b0;font-size:0.8rem">No objects detected</span>'
    tags = ""
    for obj in objects:
        if obj in DANGEROUS_OBJECTS:         tags += f'<span class="object-tag tag-danger">⚠ {obj}</span>'
        elif restricted_zone and obj in zone_objects: tags += f'<span class="object-tag tag-warn">🚧 {obj}</span>'
        elif obj == "person":                tags += f'<span class="object-tag tag-fall">👤 {obj}</span>'
        else:                                tags += f'<span class="object-tag tag-safe">✓ {obj}</span>'
    return tags

def render_messages_html():
    html = '<div class="section-header" style="margin-top:10px">📢 Alert Log</div>'
    for m in list(st.session_state.recent_messages)[:12]:
        html += f'<div class="log-entry {m["type"]}"><span style="color:#556677">[{m["time"]}]</span> {m["text"]}</div>'
    return html

# ===================== MAIN UI =====================
init_db()
init_csv()

st.markdown("""
<div class="main-header">
    <h1>🏥 Hospital Safety System — ULTIMATE EDITION</h1>
    <p>[ YOLOv8 · Pose Fall · Wet Floor · PPE · DeepSORT Tracking · Crowd Density · Multi-Cam · Claude AI Reports ]</p>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📹 Live Monitor", "🎥 Multi-Camera", "📊 Analytics",
    "🗺️ Heatmap", "📋 Reports", "🤖 AI Incident Report"
])

# ===================== TAB 1: LIVE MONITOR =====================
with tab1:
    col_feed, col_stats = st.columns([3,1])
    with col_feed:
        mode = st.radio("Input Mode", ["Webcam","Video File","URL"], horizontal=True)
        frame_ph = st.empty()
        if mode == "Video File":
            uploaded_file = st.file_uploader("Upload Video", type=["mp4","avi","mov","mkv","mpeg4"])
        elif mode == "URL":
            video_url = st.text_input("Video Stream URL")
    with col_stats:
        st.markdown('<div class="section-header">📡 Live Stats</div>', unsafe_allow_html=True)
        status_ph  = st.empty()
        metrics_ph = st.empty()
        objects_ph = st.empty()
        msgs_ph    = st.empty()

    c1, c2 = st.columns(2)
    with c1: start_btn = st.button("▶ Start Detection", use_container_width=True)
    with c2: stop_btn  = st.button("⏹ Stop",           use_container_width=True)
    if stop_btn: st.session_state.running = False

    def run_detection(source, cam_id=0):
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            st.error("Cannot open video source.")
            return
        st.session_state.running = True
        while st.session_state.running:
            ret, frame = cap.read()
            if not ret: break
            (annotated, objects, danger, fall, wet,
             ppe, crowd, count, tracks) = process_frame(frame, cam_id)
            frame_ph.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_container_width=True)
            status_ph.markdown(render_status_card(danger,fall,wet,ppe,crowd,count,tracks), unsafe_allow_html=True)
            metrics_ph.markdown(render_metrics_html(), unsafe_allow_html=True)
            objects_ph.markdown(
                '<div class="section-header">🎯 Detected Objects</div>' + render_objects_html(objects),
                unsafe_allow_html=True)
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
                tfile.write(uploaded_file.read()); tfile.flush()
                run_detection(tfile.name)
            else:
                st.warning("Please upload a video file first.")
        elif mode == "URL":
            if 'video_url' in locals() and video_url:
                urllib.request.urlretrieve(video_url, "temp_stream.mp4")
                run_detection("temp_stream.mp4")
            else:
                st.warning("Please enter a video URL.")

# ===================== TAB 2: MULTI-CAMERA =====================
with tab2:
    st.markdown('<div class="section-header">🎥 Multi-Camera Monitor</div>', unsafe_allow_html=True)
    if not enable_multicam:
        st.info("Enable Multi-Camera Mode in the sidebar and provide camera URLs.")
    else:
        st.caption(f"Monitoring {len(cam_urls)} cameras: {', '.join(cam_urls)}")
        mc_cols = st.columns(min(len(cam_urls), 3))
        mc_placeholders = [col.empty() for col in mc_cols]

        def run_single_cam(source, idx):
            src = int(source) if source.isdigit() else source
            cap = cv2.VideoCapture(src)
            while st.session_state.running:
                ret, frame = cap.read()
                if not ret: break
                frame = cv2.resize(frame, (640, 360))
                (annotated, _, danger, fall, wet, ppe, crowd, count, _) = process_frame(frame, cam_id=idx)
                rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                label = f"Cam {idx+1}"
                if fall:   label += " 🆘 FALL"
                elif danger: label += " 🚨 DANGER"
                elif wet:  label += " 💧 WET"
                mc_placeholders[idx % len(mc_placeholders)].image(rgb, caption=label, use_container_width=True)
                time.sleep(0.05)
            cap.release()

        mc1, mc2 = st.columns(2)
        with mc1:
            mc_start = st.button("▶ Start All Cameras", use_container_width=True)
        with mc2:
            mc_stop  = st.button("⏹ Stop All Cameras",  use_container_width=True)
        if mc_stop:  st.session_state.running = False
        if mc_start:
            st.session_state.running = True
            threads = []
            for i, url in enumerate(cam_urls[:3]):
                t = threading.Thread(target=run_single_cam, args=(url, i), daemon=True)
                t.start(); threads.append(t)
            for t in threads: t.join()

# ===================== TAB 3: ANALYTICS =====================
with tab3:
    st.markdown('<div class="section-header">📊 Detection Analytics</div>', unsafe_allow_html=True)
    if st.session_state.detection_history:
        df_h = pd.DataFrame(list(st.session_state.detection_history))
        x    = list(range(len(df_h)))

        col_a, col_b = st.columns(2)
        with col_a:
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=x,y=df_h["count"],  mode="lines",name="Objects",
                line=dict(color="#00d4ff",width=2),fill="tozeroy",fillcolor="rgba(0,212,255,0.08)"))
            fig1.add_trace(go.Scatter(x=x,y=df_h["persons"],mode="lines",name="Persons",
                line=dict(color="#00ff99",width=2)))
            fig1.update_layout(title="Detection Timeline",
                paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(13,27,42,0.8)",
                font=dict(color="#a0b8d0"),xaxis=dict(gridcolor="#1a3a5c"),
                yaxis=dict(gridcolor="#1a3a5c"),legend=dict(bgcolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            if st.session_state.object_counts:
                odf = pd.DataFrame(list(st.session_state.object_counts.items()),
                                   columns=["Object","Count"]).sort_values("Count",ascending=False)
                colors = ["#ff4444" if o in DANGEROUS_OBJECTS else
                          "#ffdd00" if o in PPE_CLASSES else
                          "#00aaff" if o == SLIP_ZONE_LABEL else
                          "#ff8800" if o == "person" else "#00d4ff" for o in odf["Object"]]
                fig2 = go.Figure(go.Bar(x=odf["Object"],y=odf["Count"],marker_color=colors))
                fig2.update_layout(title="Object Frequency",
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(13,27,42,0.8)",
                    font=dict(color="#a0b8d0"),xaxis=dict(gridcolor="#1a3a5c"),
                    yaxis=dict(gridcolor="#1a3a5c"))
                st.plotly_chart(fig2, use_container_width=True)

        fig3 = go.Figure()
        event_cols = [("danger","#ff4444","Danger"),("fall","#ff8800","Fall"),
                      ("wet","#00aaff","Wet Floor"),("ppe","#ffdd00","PPE"),("crowd","#cc44ff","Crowd")]
        for col,color,name in event_cols:
            if col in df_h.columns:
                fig3.add_trace(go.Bar(x=x,y=df_h[col],name=name,marker_color=color))
        fig3.update_layout(title="All Event Types Timeline",barmode="overlay",
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(13,27,42,0.8)",
            font=dict(color="#a0b8d0"),xaxis=dict(gridcolor="#1a3a5c"),
            yaxis=dict(gridcolor="#1a3a5c"),legend=dict(bgcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig3, use_container_width=True)

        # Pie chart for event distribution
        s = st.session_state.stats
        pie_vals  = [s["danger_events"],s["fall_events"],s["wet_floor_events"],s["ppe_violations"],s["crowd_alerts"]]
        pie_labels= ["Danger","Fall","Wet Floor","PPE","Crowd"]
        pie_colors= ["#ff4444","#ff8800","#00aaff","#ffdd00","#cc44ff"]
        if sum(pie_vals) > 0:
            fig4 = go.Figure(go.Pie(labels=pie_labels,values=pie_vals,
                marker=dict(colors=pie_colors),hole=0.4))
            fig4.update_layout(title="Event Distribution",
                paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#a0b8d0"),
                legend=dict(bgcolor="rgba(0,0,0,0)"))
            st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("No detection data yet. Start the detector to see analytics.")

# ===================== TAB 4: HEATMAP =====================
with tab4:
    st.markdown('<div class="section-header">🗺️ Activity Heatmap</div>', unsafe_allow_html=True)
    st.caption("Brighter = more activity. Wet floor events weighted 2×.")
    grid = st.session_state.heatmap_grid
    if grid.max() > 0:
        fig_h = go.Figure(data=go.Heatmap(
            z=grid,
            colorscale=[[0,"#0a0e1a"],[0.3,"#003366"],[0.5,"#005599"],
                        [0.7,"#00aaff"],[0.9,"#00ffcc"],[1.0,"#ff4444"]],
            showscale=True, colorbar=dict(tickfont=dict(color="#a0b8d0"))
        ))
        fig_h.update_layout(title="Spatial Activity Heatmap",
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(13,27,42,0.8)",
            font=dict(color="#a0b8d0"),height=450,
            xaxis=dict(showgrid=False,title="Horizontal Zone (0=Left, 9=Right)"),
            yaxis=dict(showgrid=False,title="Vertical Zone",autorange="reversed"))
        st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.info("Heatmap will appear after detection starts.")
    if st.button("Reset Heatmap"):
        st.session_state.heatmap_grid = np.zeros((10,10),dtype=np.float32)
        st.rerun()

# ===================== TAB 5: REPORTS =====================
with tab5:
    st.markdown('<div class="section-header">📋 Detection Reports</div>', unsafe_allow_html=True)
    s   = st.session_state.stats
    dur = str(datetime.now() - s["session_start"]).split(".")[0]

    cols = st.columns(8)
    metrics_data = [
        (s["total_detections"],  "Detections",   "#00d4ff"),
        (s["danger_events"],     "Danger",        "#ff4444"),
        (s["fall_events"],       "Falls",         "#ff8800"),
        (s["wet_floor_events"],  "Wet Floor",     "#00aaff"),
        (s["ppe_violations"],    "PPE Violations","#ffdd00"),
        (s["crowd_alerts"],      "Crowd Alerts",  "#cc44ff"),
        (s["alerts_sent"],       "Alerts Sent",   "#ffaa00"),
        (dur,                    "Duration",      "#00cc66"),
    ]
    for col,(val,label,color) in zip(cols, metrics_data):
        col.markdown(f"""<div class="metric-card">
            <div class="metric-value" style="color:{color}">{val}</div>
            <div class="metric-label">{label}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-header">🚨 Incident Log</div>', unsafe_allow_html=True)
    if st.session_state.incident_log:
        inc_df = pd.DataFrame(st.session_state.incident_log)
        def highlight_severity(row):
            if row.get("severity") == "CRITICAL": return ["background-color:#1a0505;color:#ff6666"]*len(row)
            if row.get("severity") == "HIGH":     return ["background-color:#1a0a00;color:#ffaa44"]*len(row)
            return [""]*len(row)
        st.dataframe(inc_df.style.apply(highlight_severity, axis=1),
                     use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown('<div class="section-header">📄 Raw Detection Log</div>', unsafe_allow_html=True)
    if os.path.exists(LOG_FILE):
        try:
            df_r = pd.read_csv(LOG_FILE, on_bad_lines='skip')
            if not df_r.empty:
                c1f, c2f = st.columns(2)
                with c1f:
                    statuses = df_r["Status"].unique().tolist() if "Status" in df_r.columns else []
                    sel_status = st.multiselect("Filter Status", statuses, default=statuses)
                with c2f:
                    objs = df_r["Object"].unique().tolist() if "Object" in df_r.columns else []
                    sel_obj = st.multiselect("Filter Object", objs, default=objs)
                filtered = df_r[df_r["Status"].isin(sel_status) & df_r["Object"].isin(sel_obj)]
                def highlight_rows(row):
                    if row.get("Status") == "DANGER": return ["background-color:#1a0a0a;color:#ff6666"]*len(row)
                    if row.get("Status") == "FALL":   return ["background-color:#1a0a00;color:#ffaa44"]*len(row)
                    if row.get("Status") == "WET":    return ["background-color:#0a1020;color:#44ccff"]*len(row)
                    if row.get("Status") == "PPE":    return ["background-color:#1a1500;color:#ffee66"]*len(row)
                    if row.get("Status") == "CROWD":  return ["background-color:#10001a;color:#dd88ff"]*len(row)
                    return [""]*len(row)
                st.dataframe(filtered.style.apply(highlight_rows, axis=1),
                             use_container_width=True, hide_index=True)
                st.download_button("⬇ Download CSV",
                    data=filtered.to_csv(index=False),
                    file_name=f"safety_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv", use_container_width=True)
        except Exception as e:
            st.error(f"Error reading log: {e}")
    else:
        st.info("No log data yet.")

    st.markdown("---")
    if st.button("🗑 Clear Session Stats", use_container_width=True):
        st.session_state.stats = {
            "total_detections": 0, "danger_events": 0, "fall_events": 0,
            "wet_floor_events": 0, "ppe_violations": 0, "crowd_alerts": 0,
            "persons_detected": 0, "alerts_sent": 0,
            "unique_persons": set(), "session_start": datetime.now()
        }
        st.session_state.detection_history.clear()
        st.session_state.object_counts.clear()
        st.session_state.incident_log.clear()
        st.rerun()

# ===================== TAB 6: AI INCIDENT REPORT =====================
with tab6:
    st.markdown('<div class="section-header">🤖 Claude AI Incident Report Generator</div>', unsafe_allow_html=True)
    st.caption("Uses Claude Sonnet to generate a professional hospital safety incident report from your session data.")

    col_btn, col_status = st.columns([1,2])
    with col_btn:
        gen_btn = st.button("🧠 Generate AI Report", use_container_width=True)
    with col_status:
        if not anthropic_key:
            st.warning("⚠️ Add your Anthropic API key in the sidebar to enable AI reports.")
        elif not st.session_state.incident_log:
            st.info("📋 No incidents yet — start detection to collect data.")
        else:
            st.success(f"✅ {len(st.session_state.incident_log)} incidents ready for analysis.")

    if gen_btn:
        with st.spinner("Claude is analyzing your safety data..."):
            report = generate_ai_report(
                st.session_state.incident_log,
                st.session_state.stats
            )
            st.session_state.ai_report = report

    if st.session_state.ai_report:
        st.markdown('<div class="ai-report">' +
                    st.session_state.ai_report.replace("\n","<br>") +
                    '</div>', unsafe_allow_html=True)
        st.download_button("⬇ Download Report (.txt)",
            data=st.session_state.ai_report,
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain", use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">📋 Recent Incidents</div>', unsafe_allow_html=True)
    if st.session_state.incident_log:
        for inc in list(reversed(st.session_state.incident_log))[:15]:
            sev_color = "#ff4444" if inc["severity"]=="CRITICAL" else "#ffaa00" if inc["severity"]=="HIGH" else "#00aaff"
            st.markdown(f"""
            <div class="log-entry" style="border-left-color:{sev_color}">
                <span style="color:#556677">[{inc['time']}]</span>
                <span style="color:{sev_color};font-weight:600"> {inc['severity']} · {inc['type']}</span>
                — {inc['desc']}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No incidents logged yet.")