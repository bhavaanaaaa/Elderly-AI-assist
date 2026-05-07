import cv2
from ultralytics import YOLO
import time
import threading
from gtts import gTTS
import pygame
import os
import urllib.request
import csv
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client

# ================================================================
# SETTINGS
# ================================================================
LANGUAGE = "kn"  # "en" or "kn"

# Email settings
NURSE_EMAIL = "nurse@hospital.com"
SENDER_EMAIL = "youremail@gmail.com"
SENDER_PASSWORD = "your_app_password"
ENABLE_EMAIL_ALERT = False

# Twilio SMS settings
TWILIO_SID = "your_twilio_account_sid"
TWILIO_TOKEN = "your_twilio_auth_token"
TWILIO_FROM = "+1234567890"   # your Twilio number
NURSE_PHONE = "+919876543210" # nurse phone number
ENABLE_SMS_ALERT = False      # set True after adding credentials

LOG_FILE = "detection_log.csv"

# ================================================================
# OBJECT CATEGORIES
# ================================================================
SAFE_OBJECTS = ["person", "chair", "bed", "couch", "sofa", "cup",
                "bottle", "tv", "laptop", "cell phone", "book"]
DANGEROUS_OBJECTS = ["knife", "scissors"]
ALL_TRACKED = SAFE_OBJECTS + DANGEROUS_OBJECTS

KANNADA_MAP = {
    "person":     "ವ್ಯಕ್ತಿ",
    "chair":      "ಕುರ್ಚಿ",
    "bed":        "ಹಾಸಿಗೆ",
    "couch":      "ಸೋಫಾ",
    "sofa":       "ಸೋಫಾ",
    "cup":        "ಕಪ್",
    "bottle":     "ಬಾಟಲ್",
    "tv":         "ಟಿವಿ",
    "laptop":     "ಲ್ಯಾಪ್‌ಟಾಪ್",
    "cell phone": "ಮೊಬೈಲ್",
    "book":       "ಪುಸ್ತಕ",
    "knife":      "ಚಾಕು",
    "scissors":   "ಕತ್ತರಿ",
}
DIRECTION_KN = {"left": "ಎಡಭಾಗದಲ್ಲಿ", "right": "ಬಲಭಾಗದಲ್ಲಿ", "front": "ಮುಂದೆ"}
DISTANCE_KN  = {"very close": "ತುಂಬಾ ಹತ್ತಿರ", "near": "ಹತ್ತಿರ", "far": "ದೂರದಲ್ಲಿ"}

# ================================================================
# INIT
# ================================================================
pygame.mixer.init()
model = YOLO("yolov8n.pt")

object_last_spoken = {}
SPEAK_COOLDOWN = 4
alert_sent_time = 0

# ================================================================
# CSV LOGGER
# ================================================================
def init_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["Timestamp", "Object", "Direction",
                                    "Distance", "Status", "PersonCount"])

def log_event(label, direction, distance, danger, person_count):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            label, direction, distance,
            "DANGER" if danger else "SAFE",
            person_count
        ])

# ================================================================
# EMAIL ALERT
# ================================================================
def send_email_alert(message):
    if not ENABLE_EMAIL_ALERT:
        return
    try:
        msg = MIMEText(message)
        msg["Subject"] = "HOSPITAL SAFETY ALERT"
        msg["From"] = SENDER_EMAIL
        msg["To"] = NURSE_EMAIL
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, NURSE_EMAIL, msg.as_string())
        print("Email alert sent!")
    except Exception as e:
        print("Email error:", e)

# ================================================================
# SMS ALERT (Twilio)
# ================================================================
def send_sms_alert(message):
    if not ENABLE_SMS_ALERT:
        return
    global alert_sent_time
    if time.time() - alert_sent_time < 30:
        return
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_FROM,
            to=NURSE_PHONE
        )
        print("SMS alert sent to nurse!")
        alert_sent_time = time.time()
    except Exception as e:
        print("SMS error:", e)

# ================================================================
# VOICE
# ================================================================
def speak(text):
    def run():
        try:
            tts = gTTS(text=text, lang=LANGUAGE)
            tts.save("voice.mp3")
            pygame.mixer.music.load("voice.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            os.remove("voice.mp3")
        except Exception as e:
            print("Voice error:", e)
    threading.Thread(target=run, daemon=True).start()

# ================================================================
# DIRECTION + DISTANCE
# ================================================================
def get_direction(box, frame_width):
    x1, y1, x2, y2 = box.xyxy[0]
    cx = (x1 + x2) / 2
    third = frame_width / 3
    if cx < third:
        return "left"
    elif cx > 2 * third:
        return "right"
    else:
        return "front"

def get_distance(box, frame_width, frame_height):
    x1, y1, x2, y2 = box.xyxy[0]
    ratio = ((x2 - x1) * (y2 - y1)) / (frame_width * frame_height)
    if ratio > 0.3:
        return "very close"
    elif ratio > 0.1:
        return "near"
    else:
        return "far"

# ================================================================
# DASHBOARD OVERLAY
# ================================================================
def draw_dashboard(frame, detections, danger, person_count):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

    status = "DANGER DETECTED!" if danger else "System Active"
    color  = (0, 0, 255) if danger else (0, 255, 100)

    cv2.putText(frame, f"Hospital Safety System | {status}",
                (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"Objects: {', '.join(detections) if detections else 'None'}",
                (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    # Person count shown in yellow
    cv2.putText(frame, f"Persons in frame: {person_count}",
                (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    return frame

# ================================================================
# MAIN FRAME PROCESSOR
# ================================================================
def process_frame(frame):
    global object_last_spoken

    h, w = frame.shape[:2]
    results = model.predict(frame, conf=0.40, imgsz=320, verbose=False)
    annotated = results[0].plot()

    current_objects = set()
    danger_detected = False
    current_time = time.time()

    # ---- Person count (Upgrade 2) ----
    person_count = 0
    if results[0].boxes is not None:
        person_count = sum(1 for box in results[0].boxes
                          if model.names[int(box.cls[0])] == "person")

    if results[0].boxes is not None:
        for box in results[0].boxes:
            cls   = int(box.cls[0])
            label = model.names[cls]
            if label not in ALL_TRACKED:
                continue

            direction = get_direction(box, w)
            distance  = get_distance(box, w, h)
            is_danger = label in DANGEROUS_OBJECTS

            current_objects.add(label)
            if is_danger:
                danger_detected = True

            log_event(label, direction, distance, is_danger, person_count)

            # Speak per object with cooldown
            last_time = object_last_spoken.get(label, 0)
            if current_time - last_time > SPEAK_COOLDOWN:
                if LANGUAGE == "kn":
                    kn_label = KANNADA_MAP.get(label, label)
                    kn_dir   = DIRECTION_KN.get(direction, direction)
                    kn_dist  = DISTANCE_KN.get(distance, distance)
                    msg = f"ಎಚ್ಚರಿಕೆ {kn_label} {kn_dir} {kn_dist}" if is_danger else f"{kn_label} {kn_dir} {kn_dist}"
                else:
                    msg = f"Warning! {label} on {direction}, {distance}" if is_danger else f"{label} on {direction}, {distance}"

                print(f"Speaking: {msg}")
                speak(msg)
                object_last_spoken[label] = current_time

    # Speak person count if changed
    prev_count = getattr(process_frame, "last_person_count", -1)
    if person_count != prev_count:
        if LANGUAGE == "kn":
            count_msg = f"{person_count} ವ್ಯಕ್ತಿಗಳು ಕಂಡುಬಂದಿದ್ದಾರೆ"
        else:
            count_msg = f"{person_count} person{'s' if person_count != 1 else ''} detected in frame"
        speak(count_msg)
        process_frame.last_person_count = person_count

    # Clean up disappeared objects
    for obj in list(object_last_spoken.keys()):
        if obj not in current_objects:
            del object_last_spoken[obj]

    # SMS + Email alert for danger
    if danger_detected:
        alert_msg = f"DANGER: {', '.join(current_objects)} detected at {datetime.now().strftime('%H:%M:%S')}"
        threading.Thread(target=send_sms_alert, args=(alert_msg,), daemon=True).start()
        threading.Thread(target=send_email_alert, args=(alert_msg,), daemon=True).start()

    annotated = draw_dashboard(annotated, current_objects, danger_detected, person_count)
    return annotated

# ================================================================
# RUN MODES
# ================================================================
def run_camera():
    cap = cv2.VideoCapture(0)
    print("Webcam started. Press ESC to exit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = process_frame(frame)
        cv2.imshow("Hospital Safety System", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyAllWindows()

def run_video(path):
    cap = cv2.VideoCapture(path)
    print("Video started. Press ESC to exit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = process_frame(frame)
        cv2.imshow("Hospital Safety System", frame)
        if cv2.waitKey(25) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyAllWindows()

def download_video(url):
    filename = "cloud_video.mp4"
    print("Downloading video...")
    urllib.request.urlretrieve(url, filename)
    print("Download complete!")
    return filename

# ================================================================
# MAIN MENU
# ================================================================
init_log()

print("\n====================================")
print("   HOSPITAL SAFETY SYSTEM v3.0")
print("   Upgrades: Count + SMS + WebUI")
print("====================================")
print("1 - Live Webcam")
print("2 - Local Video File")
print("3 - Cloud Video (URL)")
print("4 - Web UI Dashboard (Streamlit)")
print("====================================")

choice = input("Enter choice (1/2/3/4): ").strip()

if choice == "1":
    run_camera()
elif choice == "2":
    path = input("Enter video file path: ").strip()
    run_video(path)
elif choice == "3":
    url = input("Enter video URL: ").strip()
    run_video(download_video(url))
elif choice == "4":
    print("\nStarting Web UI...")
    os.system("streamlit run streamlit_app.py")
else:
    print("Invalid choice.")