"""
╔══════════════════════════════════════════════════════════════╗
║        WET FLOOR / WET AREA DETECTION SYSTEM                 ║
║        Using YOLOv8 wet_floor.pt Model                       ║
║        Detects wet areas in real-time from camera/video      ║
╚══════════════════════════════════════════════════════════════╝
"""

import cv2
import os
import csv
import threading
import time
from datetime import datetime
from collections import deque
from typing import Optional, Tuple
import numpy as np
from ultralytics import YOLO
import pyttsx3

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
MODEL_PATH = "backend/wet_floor.pt"  # Path to trained wet floor model
LOG_FILE = "wet_floor_detections.csv"
CONFIDENCE_THRESHOLD = 0.5
VIDEO_SOURCE = 0  # 0 for webcam, or video file path

# Alert settings
SPEAK_COOLDOWN = 5  # seconds between voice alerts
MIN_DETECTION_AREA = 100  # minimum bounding box area to trigger alert
ALERT_ZONE_HEIGHT_RATIO = 0.7  # alert if wet area in bottom 70% of frame

# ═══════════════════════════════════════════════════════════════════════════
#  GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════════
class WetFloorDetector:
    def __init__(self, model_path: str = MODEL_PATH):
        """Initialize the wet floor detector."""
        self.model = None
        self.model_path = model_path
        self.last_alert_time = 0
        self.detection_history = deque(maxlen=100)
        self.stats = {
            "total_frames": 0,
            "wet_areas_detected": 0,
            "alerts_triggered": 0,
            "start_time": datetime.now(),
        }
        
        # Text-to-speech engine
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty('rate', 150)
        self.tts_queue = []
        self.tts_thread = None
        
        # Load model
        self._load_model()
        
        # Initialize logging
        self._init_log()
        
    def _load_model(self):
        """Load the wet floor detection model."""
        if not os.path.exists(self.model_path):
            print(f"❌ Model not found at {self.model_path}")
            print("   Make sure wet_floor.pt exists in the backend/ folder")
            raise FileNotFoundError(f"Model file {self.model_path} not found")
        
        print(f"🔄 Loading wet floor model from {self.model_path}...")
        try:
            self.model = YOLO(self.model_path)
            print("✅ Model loaded successfully!")
            print(f"   Model info: {self.model.names}")
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            raise
    
    def _init_log(self):
        """Initialize CSV logging file."""
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "Timestamp",
                    "Wet_Area_Detected",
                    "Confidence",
                    "Number_of_Boxes",
                    "Total_Detection_Area",
                    "Frame_Position",
                    "Alert_Triggered"
                ])
        print(f"📋 Logging to {LOG_FILE}")
    
    def _log_detection(self, wet_detected: bool, confidence: float,
                       num_boxes: int, total_area: int,
                       frame_pos: str, alert_triggered: bool):
        """Log detection to CSV file."""
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "YES" if wet_detected else "NO",
                f"{confidence:.2f}",
                num_boxes,
                total_area,
                frame_pos,
                "YES" if alert_triggered else "NO"
            ])
    
    def speak_alert(self, text: str):
        """Queue a text-to-speech alert (non-blocking)."""
        if time.time() - self.last_alert_time < SPEAK_COOLDOWN:
            return  # Skip if in cooldown period
        
        self.last_alert_time = time.time()
        
        def speak():
            try:
                print(f"🔊 Alert: {text}")
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except Exception as e:
                print(f"⚠️  TTS error: {e}")
        
        # Run in separate thread to avoid blocking
        thread = threading.Thread(target=speak, daemon=True)
        thread.start()
    
    def detect_wet_areas(self, frame: np.ndarray) -> Tuple[list, np.ndarray]:
        """
        Detect wet areas in a frame.
        
        Returns:
            detections: List of detection dictionaries
            annotated_frame: Frame with bounding boxes drawn
        """
        if self.model is None:
            return [], frame
        
        self.stats["total_frames"] += 1
        
        # Run inference
        results = self.model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        
        detections = []
        annotated_frame = frame.copy()
        
        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes
            
            if boxes is not None and len(boxes) > 0:
                h, w = frame.shape[:2]
                alert_zone_y = int(h * ALERT_ZONE_HEIGHT_RATIO)
                total_area = 0
                alert_triggered = False
                
                # Process each detection
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = self.model.names.get(class_id, "wet_floor")
                    
                    # Calculate bounding box area
                    bbox_area = (x2 - x1) * (y2 - y1)
                    total_area += bbox_area
                    
                    # Check if in alert zone (bottom of frame)
                    if y2 >= alert_zone_y and bbox_area >= MIN_DETECTION_AREA:
                        alert_triggered = True
                    
                    # Determine position in frame
                    frame_center_x = w / 2
                    if x1 < frame_center_x:
                        position = "LEFT"
                    elif x2 > frame_center_x:
                        position = "RIGHT"
                    else:
                        position = "CENTER"
                    
                    detection = {
                        "class": class_name,
                        "confidence": confidence,
                        "bbox": (x1, y1, x2, y2),
                        "area": bbox_area,
                        "position": position,
                    }
                    detections.append(detection)
                    
                    # Draw bounding box (red for wet areas)
                    color = (0, 0, 255)  # Red for wet floor
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                    
                    # Add label
                    label = f"{class_name} {confidence:.2f}"
                    cv2.putText(
                        annotated_frame,
                        label,
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2
                    )
                
                # Log detection
                frame_pos = "ALERT ZONE" if alert_triggered else "safe zone"
                self._log_detection(
                    wet_detected=True,
                    confidence=np.mean([d["confidence"] for d in detections]),
                    num_boxes=len(detections),
                    total_area=total_area,
                    frame_pos=frame_pos,
                    alert_triggered=alert_triggered
                )
                
                # Trigger alert if needed
                if alert_triggered and len(detections) > 0:
                    self.stats["wet_areas_detected"] += 1
                    self.stats["alerts_triggered"] += 1
                    self.speak_alert(f"⚠️ WET FLOOR DETECTED! {len(detections)} wet area(s) in alert zone!")
                    
                    # Draw alert banner
                    cv2.rectangle(annotated_frame, (0, 0), (w, 60), (0, 0, 255), -1)
                    cv2.putText(
                        annotated_frame,
                        "🚨 WET FLOOR ALERT! 🚨",
                        (20, 40),
                        cv2.FONT_HERSHEY_BOLD,
                        1.2,
                        (255, 255, 255),
                        2
                    )
        
        # Draw stats
        self._draw_stats(annotated_frame)
        
        return detections, annotated_frame
    
    def _draw_stats(self, frame: np.ndarray):
        """Draw statistics on the frame."""
        h, w = frame.shape[:2]
        stats_text = [
            f"Frames: {self.stats['total_frames']}",
            f"Wet Areas: {self.stats['wet_areas_detected']}",
            f"Alerts: {self.stats['alerts_triggered']}",
        ]
        
        y_offset = h - 70
        for i, text in enumerate(stats_text):
            cv2.putText(
                frame,
                text,
                (10, y_offset + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                1
            )
    
    def run_from_webcam(self):
        """Run wet floor detection from webcam."""
        print("🎥 Starting webcam detection...")
        print("   Press 'q' to quit, 's' to save frame")
        
        cap = cv2.VideoCapture(VIDEO_SOURCE)
        
        if not cap.isOpened():
            print("❌ Failed to open video source")
            return
        
        frame_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("❌ Failed to read frame")
                    break
                
                # Resize for faster processing
                frame = cv2.resize(frame, (640, 480))
                
                # Detect wet areas
                detections, annotated_frame = self.detect_wet_areas(frame)
                
                # Display frame
                cv2.imshow("Wet Floor Detection", annotated_frame)
                
                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n✅ Exiting...")
                    break
                elif key == ord('s'):
                    filename = f"wet_floor_detection_{frame_count}.jpg"
                    cv2.imwrite(filename, annotated_frame)
                    print(f"📸 Frame saved as {filename}")
                
                frame_count += 1
                
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self._print_summary()
    
    def run_from_video(self, video_path: str):
        """Run wet floor detection from video file."""
        if not os.path.exists(video_path):
            print(f"❌ Video file not found: {video_path}")
            return
        
        print(f"🎬 Processing video: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print("❌ Failed to open video file")
            return
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"   Resolution: {width}x{height}")
        print(f"   FPS: {fps}")
        print(f"   Total frames: {total_frames}")
        
        # Setup output video
        output_path = f"wet_floor_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        frame_count = 0
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Detect wet areas
                detections, annotated_frame = self.detect_wet_areas(frame)
                
                # Write to output video
                out.write(annotated_frame)
                
                # Progress
                frame_count += 1
                if frame_count % 30 == 0:
                    progress = (frame_count / total_frames) * 100
                    print(f"   Progress: {progress:.1f}% ({frame_count}/{total_frames})")
                
        finally:
            cap.release()
            out.release()
            print(f"\n✅ Output video saved: {output_path}")
            self._print_summary()
    
    def _print_summary(self):
        """Print detection summary."""
        duration = datetime.now() - self.stats["start_time"]
        print("\n" + "="*60)
        print("📊 DETECTION SUMMARY")
        print("="*60)
        print(f"Total frames processed: {self.stats['total_frames']}")
        print(f"Wet areas detected: {self.stats['wet_areas_detected']}")
        print(f"Alerts triggered: {self.stats['alerts_triggered']}")
        print(f"Duration: {duration}")
        print(f"Log file: {LOG_FILE}")
        print("="*60 + "\n")


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   WET FLOOR DETECTION SYSTEM                              ║")
    print("║   Usage:                                                   ║")
    print("║   - python wet_floor_detector.py           (webcam)       ║")
    print("║   - python wet_floor_detector.py video.mp4 (video file)   ║")
    print("╚════════════════════════════════════════════════════════════╝\n")
    
    try:
        # Initialize detector
        detector = WetFloorDetector()
        
        # Choose source
        if len(sys.argv) > 1:
            # Video file mode
            video_file = sys.argv[1]
            detector.run_from_video(video_file)
        else:
            # Webcam mode
            detector.run_from_webcam()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
