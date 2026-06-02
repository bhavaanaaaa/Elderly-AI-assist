"""
╔══════════════════════════════════════════════════════════════╗
║   HOSPITAL SAFETY SYSTEM — FastAPI Backend                   ║
║   Drop this file into your  backend/  folder                 ║
║   Run:  uvicorn main:app --reload --port 8000                ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import base64
import csv
import json
import os
import queue
import smtplib
import sqlite3
import tempfile
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import anthropic
import cv2
import numpy as np
import pandas as pd
import pyttsx3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ultralytics import YOLO

# ── Optional dependencies with graceful fallback ────────────────────────────
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("⚠️  Twilio not installed — SMS/WhatsApp alerts disabled")

try:
    import mediapipe as mp
    mp_pose    = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
    MEDIAPIPE_AVAILABLE = True
    print("✅  MediaPipe loaded")
except Exception:
    MEDIAPIPE_AVAILABLE = False
    mp_pose = mp_drawing = None
    print("⚠️  MediaPipe not available — using bbox fall detection")

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    DEEPSORT_AVAILABLE = True
    print("✅  DeepSORT loaded")
except Exception:
    DEEPSORT_AVAILABLE = False
    DeepSort = None
    print("⚠️  DeepSORT not available — tracking disabled")

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
DB_FILE   = "hospital_safety.db"
LOG_FILE  = "detection_log.csv"
DANGEROUS_OBJECTS = ["knife", "scissors", "gun", "baseball bat", "fire", "smoke"]
PPE_CLASSES = {
    "NO-Hardhat": "hard hat missing",
    "NO-Mask":    "mask missing",
    "NO-Gloves":  "gloves missing",
    "NO-Safety Vest": "safety vest missing",
}
SLIP_ZONE_LABEL  = "WET FLOOR"
SPEAK_COOLDOWN   = 4

# ═══════════════════════════════════════════════════════════════════════════
#  GLOBAL STATE  (replaces st.session_state)
# ═══════════════════════════════════════════════════════════════════════════
app_state = {
    "stats": {
        "total_detections": 0,
        "danger_events":    0,
        "fall_events":      0,
        "wet_floor_events": 0,
        "ppe_violations":   0,
        "crowd_alerts":     0,
        "persons_detected": 0,
        "alerts_sent":      0,
        "unique_persons":   set(),
        "session_start":    datetime.now(),
    },
    "detection_history": deque(maxlen=500),
    "heatmap_grid":      np.zeros((10, 10), dtype=np.float32),
    "object_counts":     defaultdict(int),
    "incident_log":      [],
    "track_history":     defaultdict(lambda: deque(maxlen=30)),
    "recent_alerts":     deque(maxlen=30),

    # runtime config — updated via /api/config POST
    "config": {
        "conf_threshold":      0.4,
        "imgsz":               320,
        "fall_sensitivity":    3,
        "enable_wet":          True,
        "wet_area_ratio":      0.03,
        "wet_brightness":      180,
        "wet_saturation":      35,
        "wet_sensitivity":     3,
        "enable_pose":         True,
        "enable_ppe":          False,
        "ppe_model_path":      "ppe_yolov8.pt",
        "enable_crowd":        True,
        "crowd_threshold":     5,
        "enable_tracking":     False,
        "restricted_zone":     False,
        "zone_label":          "General",
        "zone_objects":        [],
        "enable_sms":          False,
        "twilio_sid":          "",
        "twilio_token":        "",
        "twilio_from":         "",
        "nurse_phone":         "",
        "enable_email":        False,
        "email_sender":        "",
        "email_password":      "",
        "email_receiver":      "",
        "enable_whatsapp":     False,
        "wa_sid":              "",
        "wa_token":            "",
        "wa_from":             "",
        "wa_to":               "",
        "alert_cooldown":      30,
        "anthropic_key":       "",
        "voice_enabled":       True,
    },
}

_obj_last_spoken: dict = {}
_alert_last       = {"sms": 0, "email": 0, "wa": 0}
_detection_active = False
_video_source     = None   # set by /api/start

# ═══════════════════════════════════════════════════════════════════════════
#  FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════
app = FastAPI(title="Hospital Safety API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
#  MODEL LOADING
# ═══════════════════════════════════════════════════════════════════════════
print("🔄 Loading YOLOv8n...")
yolo_model = YOLO("yolov8n.pt")
print("✅ YOLOv8n ready")

ppe_model: Optional[YOLO] = None

def _load_ppe_model():
    global ppe_model
    path = app_state["config"]["ppe_model_path"]
    if os.path.exists(path):
        ppe_model = YOLO(path)
        print(f"✅ PPE model loaded: {path}")
    else:
        print(f"⚠️  PPE model not found at {path}")

_load_ppe_model()

tracker       = DeepSort(max_age=30, n_init=2) if DEEPSORT_AVAILABLE else None
pose_detector = mp_pose.Pose(min_detection_confidence=0.5,
                              min_tracking_confidence=0.5) if MEDIAPIPE_AVAILABLE else None

# ═══════════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c    = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT,
            object       TEXT,
            direction    TEXT,
            distance     TEXT,
            status       TEXT,
            person_count INTEGER,
            zone         TEXT,
            track_id     INTEGER,
            confidence   REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT,
            type        TEXT,
            description TEXT,
            severity    TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


def db_log(label, direction, distance, status, person_count,
           zone="General", track_id=-1, confidence=0.0):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            INSERT INTO detections
            (timestamp,object,direction,distance,status,person_count,zone,track_id,confidence)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              label, direction, distance, status,
              person_count, zone, track_id, round(confidence, 3)))
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB error:", e)


def db_log_incident(type_: str, description: str, severity: str = "MEDIUM"):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            INSERT INTO incidents (timestamp,type,description,severity)
            VALUES (?,?,?,?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              type_, description, severity))
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB incident error:", e)

    app_state["incident_log"].append({
        "time":     datetime.now().strftime("%H:%M:%S"),
        "type":     type_,
        "desc":     description,
        "severity": severity,
    })


def init_csv():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "Timestamp", "Object", "Direction", "Distance",
                "Status", "PersonCount", "Zone", "TrackID", "Confidence"
            ])


init_csv()


def log_event(label, direction, distance, status, person_count,
              zone="General", track_id=-1, confidence=0.0):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            label, direction, distance, status,
            person_count, zone, track_id, round(confidence, 3)
        ])
    db_log(label, direction, distance, status, person_count, zone, track_id, confidence)

    s = app_state["stats"]
    s["total_detections"] += 1
    if status == "DANGER":  s["danger_events"]    += 1
    elif status == "FALL":  s["fall_events"]      += 1
    elif status == "WET":   s["wet_floor_events"] += 1
    elif status == "PPE":   s["ppe_violations"]   += 1
    elif status == "CROWD": s["crowd_alerts"]     += 1
    app_state["object_counts"][label] += 1


# ═══════════════════════════════════════════════════════════════════════════
#  SPEECH (optional, runs in background thread)
# ═══════════════════════════════════════════════════════════════════════════
_speech_q: queue.Queue = queue.Queue()
_last_spoke = 0.0


def _speech_worker():
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 155)
        while True:
            text = _speech_q.get()
            if text is None:
                break
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass
            _speech_q.task_done()
    except Exception:
        pass  # pyttsx3 may fail headlessly — not critical


threading.Thread(target=_speech_worker, daemon=True).start()


def speak(text: str, priority: bool = False):
    global _last_spoke
    if not app_state["config"]["voice_enabled"]:
        return
    now = time.time()
    if not priority and now - _last_spoke < 2:
        return
    _last_spoke = now
    _speech_q.put(text)


# ═══════════════════════════════════════════════════════════════════════════
#  ALERT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════
def fire_alerts(message: str):
    threading.Thread(target=_send_sms,   args=(message,), daemon=True).start()
    threading.Thread(target=_send_email, args=(message,), daemon=True).start()
    threading.Thread(target=_send_wa,    args=(message,), daemon=True).start()


def _send_sms(msg: str):
    cfg = app_state["config"]
    if not cfg["enable_sms"] or not TWILIO_AVAILABLE or not cfg["twilio_sid"]:
        return
    if time.time() - _alert_last["sms"] < cfg["alert_cooldown"]:
        return
    try:
        TwilioClient(cfg["twilio_sid"], cfg["twilio_token"]).messages.create(
            body=msg, from_=cfg["twilio_from"], to=cfg["nurse_phone"])
        _alert_last["sms"] = time.time()
        app_state["stats"]["alerts_sent"] += 1
    except Exception as e:
        print("SMS error:", e)


def _send_email(msg: str):
    cfg = app_state["config"]
    if not cfg["enable_email"] or not cfg["email_sender"]:
        return
    if time.time() - _alert_last["email"] < cfg["alert_cooldown"]:
        return
    try:
        m = MIMEMultipart()
        m["From"]    = cfg["email_sender"]
        m["To"]      = cfg["email_receiver"]
        m["Subject"] = "🚨 Hospital Safety ALERT"
        m.attach(MIMEText(msg, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(cfg["email_sender"], cfg["email_password"])
            s.sendmail(cfg["email_sender"], cfg["email_receiver"], m.as_string())
        _alert_last["email"] = time.time()
        app_state["stats"]["alerts_sent"] += 1
    except Exception as e:
        print("Email error:", e)


def _send_wa(msg: str):
    cfg = app_state["config"]
    if not cfg["enable_whatsapp"] or not TWILIO_AVAILABLE or not cfg["wa_sid"]:
        return
    if time.time() - _alert_last["wa"] < cfg["alert_cooldown"]:
        return
    try:
        TwilioClient(cfg["wa_sid"], cfg["wa_token"]).messages.create(
            body=msg, from_=cfg["wa_from"], to=cfg["wa_to"])
        _alert_last["wa"] = time.time()
        app_state["stats"]["alerts_sent"] += 1
    except Exception as e:
        print("WA error:", e)


# ═══════════════════════════════════════════════════════════════════════════
#  CV HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def get_direction(cx: int, w: int) -> str:
    if cx < w / 3:      return "left"
    if cx > 2 * w / 3:  return "right"
    return "front"


def get_distance(box_area: float, frame_area: float) -> str:
    r = box_area / frame_area
    if r > 0.3:  return "very close"
    if r > 0.1:  return "near"
    return "far"


def update_heatmap(cx: int, cy: int, w: int, h: int, weight: int = 1):
    gx = min(int(cx / w * 10), 9)
    gy = min(int(cy / h * 10), 9)
    app_state["heatmap_grid"][gy][gx] += weight


# ═══════════════════════════════════════════════════════════════════════════
#  WET FLOOR DETECTION  (5-method voting)
# ═══════════════════════════════════════════════════════════════════════════
def _m1_glossy(hsv, fmask):
    return cv2.bitwise_and(
        cv2.bitwise_and(cv2.inRange(hsv[:, :, 1], 0, 40),
                        cv2.inRange(hsv[:, :, 2], 180, 255)),
        fmask)


def _m2_dark_wet(hsv, fmask):
    base = cv2.bitwise_and(cv2.inRange(hsv[:, :, 2], 40, 180),
                           cv2.inRange(hsv[:, :, 1], 0, 80))
    return cv2.bitwise_and(base, fmask)


def _m3_mirror(gray, fmask):
    h    = gray.shape[0]
    fstart = int(h * 0.4)
    fg   = gray[fstart:, :]
    fh   = fg.shape[0]
    if fh < 10:
        return np.zeros_like(gray)
    mid  = fh // 2
    top  = fg[:mid, :]
    bot  = fg[mid:fh, :]
    bf   = cv2.flip(bot[:min(mid, bot.shape[0]), :], 0)
    diff = cv2.absdiff(top[:bf.shape[0], :], bf)
    mm   = cv2.inRange(diff, 0, 35)
    full = np.zeros_like(gray)
    full[fstart:fstart + mm.shape[0], :] = mm
    return cv2.bitwise_and(full, fmask)


def _m4_variance(gray, fmask):
    gf      = gray.astype(np.float32)
    msq     = cv2.blur(gf ** 2, (9, 9))
    mn      = cv2.blur(gf,      (9, 9))
    var     = np.clip(msq - mn ** 2, 0, None)
    std_map = np.sqrt(var).astype(np.uint8)
    return cv2.bitwise_and(cv2.inRange(std_map, 8, 55), fmask)


def _m5_blue_hue(hsv, fmask):
    return cv2.bitwise_and(
        cv2.inRange(hsv, np.array([90, 10, 40]), np.array([130, 180, 240])),
        fmask)


def detect_wet_floor(frame: np.ndarray) -> list[tuple]:
    cfg = app_state["config"]
    h, w = frame.shape[:2]
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    fmask = np.zeros((h, w), dtype=np.uint8)
    fmask[int(h * 0.38):, :] = 255

    vote = (
        (_m1_glossy(hsv, fmask)  > 0).astype(np.uint8) +
        (_m2_dark_wet(hsv, fmask) > 0).astype(np.uint8) +
        (_m3_mirror(gray, fmask)  > 0).astype(np.uint8) +
        (_m4_variance(gray, fmask) > 0).astype(np.uint8) +
        (_m5_blue_hue(hsv, fmask) > 0).astype(np.uint8)
    )
    combined = np.where(vote >= 2, 255, 0).astype(np.uint8)

    k_c = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    k_o = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (12, 12))
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_c)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  k_o)

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    min_area = w * h * cfg["wet_area_ratio"]
    for cnt in contours:
        if cv2.contourArea(cnt) > min_area:
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw / max(bh, 1) > 0.4:
                regions.append((x, y, x + bw, y + bh))
    return regions


def draw_slip_zones(frame: np.ndarray, regions: list) -> np.ndarray:
    for i, (x1, y1, x2, y2) in enumerate(regions):
        ov = frame.copy()
        cv2.rectangle(ov, (x1, y1), (x2, y2), (200, 160, 0), -1)
        cv2.addWeighted(ov, 0.30, frame, 0.70, 0, frame)
        hg = 16
        rh = y2 - y1
        for xh in range(x1 - rh, x2 + rh, hg):
            px1 = max(x1, xh);          py1 = y1 + max(0, x1 - xh)
            px2 = min(x2, xh + rh);     py2 = y1 + min(rh, (xh + rh) - x1)
            if px1 < px2 and py1 < py2:
                cv2.line(frame, (px1, py1), (px2, py2), (160, 210, 255), 1, cv2.LINE_AA)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 3)
        lbl = f"WET FLOOR / SLIP RISK #{i + 1}"
        (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        cv2.rectangle(frame, (x1, max(0, y1 - th - 14)), (x1 + tw + 14, y1), (0, 160, 200), -1)
        cv2.putText(frame, lbl, (x1 + 6, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    return frame


# ═══════════════════════════════════════════════════════════════════════════
#  FALL DETECTION
# ═══════════════════════════════════════════════════════════════════════════
def detect_fall_pose(frame: np.ndarray):
    if pose_detector is None:
        return False, frame
    rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose_detector.process(rgb)
    fallen  = False
    if results.pose_landmarks:
        lm  = results.pose_landmarks.landmark
        ls  = lm[mp_pose.PoseLandmark.LEFT_SHOULDER]
        rs  = lm[mp_pose.PoseLandmark.RIGHT_SHOULDER]
        lh  = lm[mp_pose.PoseLandmark.LEFT_HIP]
        rh  = lm[mp_pose.PoseLandmark.RIGHT_HIP]
        sy  = (ls.y + rs.y) / 2
        hy  = (lh.y + rh.y) / 2
        if hy >= sy - 0.08:
            fallen = True
            cv2.putText(frame, "FALL POSE DETECTED", (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 80, 255), 2, cv2.LINE_AA)
        mp_drawing.draw_landmarks(
            frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0, 200, 255), thickness=2, circle_radius=2),
            mp_drawing.DrawingSpec(color=(0, 255, 180), thickness=2),
        )
    return fallen, frame


def is_fallen_bbox(box, w: int, h: int) -> bool:
    cfg = app_state["config"]
    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
    bw, bh = x2 - x1, y2 - y1
    if bh == 0:
        return False
    threshold = 0.8 + (5 - cfg["fall_sensitivity"]) * 0.15
    return (bw / bh) > threshold and (y1 + y2) / 2 > h * 0.35


# ═══════════════════════════════════════════════════════════════════════════
#  PPE DETECTION
# ═══════════════════════════════════════════════════════════════════════════
def detect_ppe(frame: np.ndarray):
    violations = []
    if ppe_model is None:
        return violations, frame
    results = ppe_model.predict(frame, conf=0.45, imgsz=320, verbose=False)
    for box in (results[0].boxes or []):
        label = ppe_model.names[int(box.cls[0])]
        if label in PPE_CLASSES:
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            violations.append({"label": label, "desc": PPE_CLASSES[label]})
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 230, 255), 2)
            cv2.putText(frame, f"NO PPE: {label}", (x1 + 4, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return violations, frame


# ═══════════════════════════════════════════════════════════════════════════
#  CROWD DENSITY
# ═══════════════════════════════════════════════════════════════════════════
def check_crowd(person_boxes: list, fw: int, fh: int) -> list:
    cfg    = app_state["config"]
    zones  = {
        "Top-Left":     (0, 0, fw // 2, fh // 2),
        "Top-Right":    (fw // 2, 0, fw, fh // 2),
        "Bottom-Left":  (0, fh // 2, fw // 2, fh),
        "Bottom-Right": (fw // 2, fh // 2, fw, fh),
    }
    alerts = []
    for zname, (zx1, zy1, zx2, zy2) in zones.items():
        count = sum(
            1 for (px1, py1, px2, py2) in person_boxes
            if zx1 <= (px1 + px2) // 2 <= zx2 and zy1 <= (py1 + py2) // 2 <= zy2
        )
        if count > cfg["crowd_threshold"]:
            alerts.append({"zone": zname, "count": count})
    return alerts


def draw_crowd(frame: np.ndarray, alerts: list, fw: int, fh: int) -> np.ndarray:
    rects = {
        "Top-Left":     (0, 0, fw // 2, fh // 2),
        "Top-Right":    (fw // 2, 0, fw, fh // 2),
        "Bottom-Left":  (0, fh // 2, fw // 2, fh),
        "Bottom-Right": (fw // 2, fh // 2, fw, fh),
    }
    for a in alerts:
        rx1, ry1, rx2, ry2 = rects[a["zone"]]
        ov = frame.copy()
        cv2.rectangle(ov, (rx1, ry1), (rx2, ry2), (180, 0, 255), -1)
        cv2.addWeighted(ov, 0.2, frame, 0.8, 0, frame)
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (200, 0, 255), 2)
        cv2.putText(frame, f"CROWD: {a['count']}", (rx1 + 8, ry1 + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (220, 80, 255), 2, cv2.LINE_AA)
    return frame


# ═══════════════════════════════════════════════════════════════════════════
#  DEEPSORT TRACKING
# ═══════════════════════════════════════════════════════════════════════════
def run_tracking(boxes_data: list, frame: np.ndarray) -> dict:
    if tracker is None or not app_state["config"]["enable_tracking"]:
        return {}
    detections = [
        ([x1, y1, x2 - x1, y2 - y1], conf, "person")
        for (x1, y1, x2, y2, conf, cls_id) in boxes_data
        if yolo_model.names[int(cls_id)] == "person"
    ]
    tracks = tracker.update_tracks(detections, frame=frame)
    result = {}
    for track in tracks:
        if not track.is_confirmed():
            continue
        tid  = track.track_id
        ltrb = track.to_ltrb()
        result[tid] = [int(v) for v in ltrb]
        app_state["stats"]["unique_persons"].add(tid)
        cx = (ltrb[0] + ltrb[2]) // 2
        cy = (ltrb[1] + ltrb[3]) // 2
        app_state["track_history"][tid].append((int(cx), int(cy)))
    return result


def draw_tracks(frame: np.ndarray, track_map: dict) -> np.ndarray:
    for tid, (x1, y1, x2, y2) in track_map.items():
        n = int(tid)
        c = ((n * 47) % 256, (n * 83) % 256, (n * 131) % 256)
        cv2.rectangle(frame, (x1, y1), (x2, y2), c, 2)
        cv2.rectangle(frame, (x1, y1 - 22), (x1 + 70, y1), c, -1)
        cv2.putText(frame, f"ID:{n}", (x1 + 4, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        hist = list(app_state["track_history"][tid])
        for i in range(1, len(hist)):
            alpha = i / len(hist)
            cv2.line(frame, hist[i - 1], hist[i],
                     tuple(int(v * alpha) for v in c), 2)
    return frame


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN FRAME PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════
def process_frame(frame: np.ndarray, cam_id: int = 0) -> dict:
    global _obj_last_spoken
    cfg  = app_state["config"]
    h, w = frame.shape[:2]
    now  = time.time()

    danger = fall = wet = ppe_viol = crowd_alert = False
    person_boxes: list = []
    detected_objects: set = set()

    # 1. YOLO
    results   = yolo_model.predict(frame, conf=cfg["conf_threshold"],
                                    imgsz=cfg["imgsz"], verbose=False)
    annotated = results[0].plot()
    boxes_data: list = []
    person_count = 0

    if results[0].boxes is not None:
        for box in results[0].boxes:
            label = yolo_model.names[int(box.cls[0])]
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            conf_val = float(box.conf[0])
            boxes_data.append((x1, y1, x2, y2, conf_val, int(box.cls[0])))
            if label == "person":
                person_count += 1
                person_boxes.append((x1, y1, x2, y2))
            detected_objects.add(label)
            update_heatmap((x1 + x2) // 2, (y1 + y2) // 2, w, h)

        app_state["stats"]["persons_detected"] = max(
            app_state["stats"]["persons_detected"], person_count)

    # 2. Tracking
    track_map = {}
    if cfg["enable_tracking"] and DEEPSORT_AVAILABLE:
        track_map = run_tracking(boxes_data, frame)
        annotated = draw_tracks(annotated, track_map)

    # 3. Wet floor
    if cfg["enable_wet"]:
        spills = detect_wet_floor(frame)
        if spills:
            wet = True
            annotated = draw_slip_zones(annotated, spills)
            for (x1, y1, x2, y2) in spills:
                update_heatmap((x1 + x2) // 2, (y1 + y2) // 2, w, h, weight=2)
            if now - _obj_last_spoken.get("wet_floor", 0) > SPEAK_COOLDOWN:
                speak("Wet floor hazard! Slip risk detected!", priority=True)
                _obj_last_spoken["wet_floor"] = now
                log_event(SLIP_ZONE_LABEL, "center", "very close", "WET",
                          person_count, cfg["zone_label"])
                db_log_incident("WET_FLOOR",
                                f"Wet floor — {len(spills)} zone(s) — Cam {cam_id}", "HIGH")
                fire_alerts(f"💧 WET FLOOR [{datetime.now().strftime('%H:%M:%S')}] Cam {cam_id}")
                app_state["recent_alerts"].appendleft({
                    "type": "wet", "msg": "Wet floor detected",
                    "time": datetime.now().strftime("%H:%M:%S")
                })

    # 4. Fall detection
    if cfg["enable_pose"] and MEDIAPIPE_AVAILABLE:
        fall, annotated = detect_fall_pose(annotated)
    if not fall and results[0].boxes is not None:
        for box in results[0].boxes:
            if yolo_model.names[int(box.cls[0])] == "person":
                if is_fallen_bbox(box, w, h):
                    fall = True
                    break
    if fall and now - _obj_last_spoken.get("fall", 0) > SPEAK_COOLDOWN:
        speak("Fall detected! Person is on the ground!", priority=True)
        _obj_last_spoken["fall"] = now
        log_event("person", "center", "very close", "FALL", person_count, cfg["zone_label"])
        db_log_incident("FALL", f"Person fall detected — Cam {cam_id}", "CRITICAL")
        fire_alerts(f"🆘 FALL DETECTED [{datetime.now().strftime('%H:%M:%S')}] Cam {cam_id}")
        app_state["recent_alerts"].appendleft({
            "type": "fall", "msg": "Fall detected!",
            "time": datetime.now().strftime("%H:%M:%S")
        })

    # 5. PPE
    if cfg["enable_ppe"] and ppe_model:
        violations, annotated = detect_ppe(annotated)
        if violations:
            ppe_viol = True
            for v in violations:
                key = f"ppe_{v['label']}"
                if now - _obj_last_spoken.get(key, 0) > SPEAK_COOLDOWN * 2:
                    speak("PPE violation! Missing protective equipment!", priority=True)
                    _obj_last_spoken[key] = now
                    log_event(v["label"], "center", "near", "PPE",
                              person_count, cfg["zone_label"])
                    db_log_incident("PPE_VIOLATION", f"{v['desc']} Cam {cam_id}", "MEDIUM")

    # 6. Crowd
    if cfg["enable_crowd"] and person_boxes:
        crowd_list = check_crowd(person_boxes, w, h)
        if crowd_list:
            crowd_alert = True
            annotated = draw_crowd(annotated, crowd_list, w, h)
            if now - _obj_last_spoken.get("crowd", 0) > SPEAK_COOLDOWN * 2:
                speak("Crowd density alert! Too many people in zone!", priority=True)
                _obj_last_spoken["crowd"] = now
                for ca in crowd_list:
                    log_event("crowd", ca["zone"], "zone", "CROWD", ca["count"], ca["zone"])
                    db_log_incident("CROWD_DENSITY",
                                    f"{ca['count']} in {ca['zone']} Cam {cam_id}", "MEDIUM")

    # 7. Dangerous objects
    if results[0].boxes is not None:
        for box in results[0].boxes:
            label    = yolo_model.names[int(box.cls[0])]
            conf_val = float(box.conf[0])
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
            cx = (x1 + x2) // 2
            direction = get_direction(cx, w)
            distance  = get_distance((x2 - x1) * (y2 - y1), w * h)
            is_danger = label in DANGEROUS_OBJECTS
            if is_danger:
                danger = True
            log_event(label, direction, distance,
                      "DANGER" if is_danger else "SAFE",
                      person_count, cfg["zone_label"], confidence=conf_val)
            if is_danger and now - _obj_last_spoken.get(label, 0) > SPEAK_COOLDOWN:
                speak(f"Warning! {label} detected!", priority=True)
                _obj_last_spoken[label] = now
                db_log_incident("DANGEROUS_OBJECT", f"{label} detected Cam {cam_id}", "HIGH")
                fire_alerts(f"⚠️ DANGER: {label} [{datetime.now().strftime('%H:%M:%S')}]")
                app_state["recent_alerts"].appendleft({
                    "type": "danger", "msg": f"{label} detected",
                    "time": datetime.now().strftime("%H:%M:%S")
                })

    app_state["detection_history"].append({
        "time":    datetime.now().strftime("%H:%M:%S"),
        "count":   len(detected_objects),
        "persons": person_count,
        "danger":  int(danger),
        "fall":    int(fall),
        "wet":     int(wet),
        "ppe":     int(ppe_viol),
        "crowd":   int(crowd_alert),
    })

    # Encode annotated frame as base64 JPEG for WebSocket
    _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
    frame_b64 = base64.b64encode(buf).decode()

    return {
        "frame":        frame_b64,
        "danger":       danger,
        "fall":         fall,
        "wet":          wet,
        "ppe":          ppe_viol,
        "crowd":        crowd_alert,
        "person_count": person_count,
        "objects":      list(detected_objects),
        "tracks":       len(track_map),
        "stats":        _get_stats_json(),
        "heatmap":      app_state["heatmap_grid"].tolist(),
        "recent_alerts": list(app_state["recent_alerts"])[:5],
    }


def _get_stats_json() -> dict:
    s = app_state["stats"]
    return {
        "total_detections":  s["total_detections"],
        "danger_events":     s["danger_events"],
        "fall_events":       s["fall_events"],
        "wet_floor_events":  s["wet_floor_events"],
        "ppe_violations":    s["ppe_violations"],
        "crowd_alerts":      s["crowd_alerts"],
        "persons_detected":  s["persons_detected"],
        "alerts_sent":       s["alerts_sent"],
        "unique_persons":    len(s["unique_persons"]),
        "session_start":     s["session_start"].strftime("%Y-%m-%d %H:%M:%S"),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  WEBSOCKET — MAIN VIDEO STREAM
# ═══════════════════════════════════════════════════════════════════════════
@app.websocket("/ws/stream")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    print("📡 WebSocket client connected")

    source = _video_source if _video_source is not None else 0
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        await websocket.send_json({"error": "Cannot open video source"})
        await websocket.close()
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                # Loop video file
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    break

            # Run detection in thread-pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            payload = await loop.run_in_executor(None, process_frame, frame)

            await websocket.send_json(payload)
            await asyncio.sleep(0.03)   # ~30 fps

    except WebSocketDisconnect:
        print("📡 WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        cap.release()


# ═══════════════════════════════════════════════════════════════════════════
#  REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

# ── Health check ────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok", "version": "2.0",
            "message": "Hospital Safety API running"}


# ── Stats ────────────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats():
    return _get_stats_json()


# ── Heatmap ──────────────────────────────────────────────────────────────────
@app.get("/api/heatmap")
def get_heatmap():
    return {"heatmap": app_state["heatmap_grid"].tolist()}


@app.delete("/api/heatmap")
def reset_heatmap():
    app_state["heatmap_grid"] = np.zeros((10, 10), dtype=np.float32)
    return {"status": "reset"}


# ── Detection history ─────────────────────────────────────────────────────────
@app.get("/api/history")
def get_history():
    return {"history": list(app_state["detection_history"])}


# ── Incidents ─────────────────────────────────────────────────────────────────
@app.get("/api/incidents")
def get_incidents(limit: int = 100, severity: str = ""):
    conn = sqlite3.connect(DB_FILE)
    if severity:
        df = pd.read_sql(
            "SELECT * FROM incidents WHERE severity=? ORDER BY id DESC LIMIT ?",
            conn, params=(severity.upper(), limit)
        )
    else:
        df = pd.read_sql(
            "SELECT * FROM incidents ORDER BY id DESC LIMIT ?",
            conn, params=(limit,)
        )
    conn.close()
    return df.to_dict(orient="records")


# ── Detection log ─────────────────────────────────────────────────────────────
@app.get("/api/detections")
def get_detections(limit: int = 500, status: str = ""):
    conn = sqlite3.connect(DB_FILE)
    if status:
        df = pd.read_sql(
            "SELECT * FROM detections WHERE status=? ORDER BY id DESC LIMIT ?",
            conn, params=(status.upper(), limit)
        )
    else:
        df = pd.read_sql(
            "SELECT * FROM detections ORDER BY id DESC LIMIT ?",
            conn, params=(limit,)
        )
    conn.close()
    return df.to_dict(orient="records")


# ── Download CSV ──────────────────────────────────────────────────────────────
@app.get("/api/download/csv")
def download_csv():
    if not os.path.exists(LOG_FILE):
        raise HTTPException(status_code=404, detail="No log file yet")
    return FileResponse(LOG_FILE, media_type="text/csv",
                        filename=f"safety_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")


# ── Recent alerts ─────────────────────────────────────────────────────────────
@app.get("/api/alerts/recent")
def get_recent_alerts():
    return {"alerts": list(app_state["recent_alerts"])}


# ── Config GET / POST ─────────────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    safe = {k: v for k, v in app_state["config"].items()
            if "password" not in k and "token" not in k and "key" not in k}
    return safe


class ConfigUpdate(BaseModel):
    key:   str
    value: object


@app.post("/api/config")
def update_config(update: ConfigUpdate):
    if update.key in app_state["config"]:
        app_state["config"][update.key] = update.value
        return {"status": "updated", "key": update.key, "value": update.value}
    raise HTTPException(status_code=400, detail=f"Unknown config key: {update.key}")


# ── Video source ──────────────────────────────────────────────────────────────
class SourcePayload(BaseModel):
    source: str   # "0" for webcam, or file path / RTSP URL


@app.post("/api/source")
def set_source(payload: SourcePayload):
    global _video_source
    _video_source = int(payload.source) if payload.source.isdigit() else payload.source
    return {"status": "source set", "source": _video_source}


# ── Video upload ──────────────────────────────────────────────────────────────
from fastapi import UploadFile, File as FastFile


@app.post("/api/upload")
async def upload_video(file: UploadFile = FastFile(...)):
    global _video_source
    suffix = os.path.splitext(file.filename)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(await file.read())
    tmp.flush()
    _video_source = tmp.name
    return {"status": "uploaded", "path": tmp.name, "filename": file.filename}


# ── Clear session stats ───────────────────────────────────────────────────────
@app.delete("/api/stats")
def clear_stats():
    app_state["stats"] = {
        "total_detections": 0, "danger_events": 0, "fall_events": 0,
        "wet_floor_events": 0, "ppe_violations": 0, "crowd_alerts": 0,
        "persons_detected": 0, "alerts_sent":   0,
        "unique_persons":   set(),
        "session_start":    datetime.now(),
    }
    app_state["detection_history"].clear()
    app_state["object_counts"].clear()
    app_state["incident_log"].clear()
    app_state["recent_alerts"].clear()
    return {"status": "cleared"}


# ── AI Incident Report ────────────────────────────────────────────────────────
@app.post("/api/ai-report")
async def ai_report():
    key = app_state["config"]["anthropic_key"]
    if not key:
        raise HTTPException(status_code=400,
                            detail="Anthropic API key not configured. POST /api/config first.")

    incidents = app_state["incident_log"]
    if not incidents:
        return {"report": "No incidents recorded yet. Start detection to collect data."}

    try:
        client   = anthropic.Anthropic(api_key=key)
        stats    = _get_stats_json()
        prompt   = f"""You are a hospital safety officer. Generate a professional incident report.

DETECTION STATISTICS:
{json.dumps(stats, indent=2)}

RECENT INCIDENTS (last 20):
{json.dumps(incidents[-20:], indent=2)}

Write a concise professional hospital safety incident report:
1. Executive Summary
2. Key Findings
3. High-Priority Incidents
4. Risk Assessment
5. Recommended Actions

Max 400 words. Use clear medical/safety language."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"report": response.content[0].text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI report error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)