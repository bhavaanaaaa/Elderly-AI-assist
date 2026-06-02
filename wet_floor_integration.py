"""
Integration example: Using wet_floor_detector in your backend/main.py
or streamlit_app.py

This shows how to add wet floor detection to your existing system
"""

from ultralytics import YOLO
import cv2
import numpy as np
from typing import Dict, List, Tuple
import time

class WetFloorIntegration:
    """Minimal wet floor detector for integration with existing code"""
    
    def __init__(self, model_path: str = "backend/wet_floor.pt"):
        """Initialize detector"""
        self.model = YOLO(model_path)
        self.confidence_threshold = 0.5
        self.min_area = 100
        
    def detect(self, frame: np.ndarray) -> Dict:
        """
        Detect wet areas in a single frame
        
        Args:
            frame: OpenCV frame/image
            
        Returns:
            {
                "wet_detected": bool,
                "num_boxes": int,
                "confidence": float,
                "detections": [{"bbox": (x1,y1,x2,y2), "confidence": float}],
                "annotated_frame": frame with boxes drawn
            }
        """
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        annotated = frame.copy()
        
        detections = []
        wet_detected = False
        confidences = []
        
        if results[0].boxes is not None:
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                area = (x2 - x1) * (y2 - y1)
                
                confidences.append(conf)
                
                if area >= self.min_area:
                    wet_detected = True
                    detections.append({
                        "bbox": (x1, y1, x2, y2),
                        "confidence": conf,
                        "area": area
                    })
                
                # Draw box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(annotated, f"WET {conf:.2f}", (x1, y1-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        return {
            "wet_detected": wet_detected,
            "num_boxes": len(detections),
            "confidence": np.mean(confidences) if confidences else 0.0,
            "detections": detections,
            "annotated_frame": annotated
        }


# ═══════════════════════════════════════════════════════════════════════════
#  EXAMPLE USAGE IN FASTAPI (for backend/main.py)
# ═══════════════════════════════════════════════════════════════════════════

"""
# Add to your FastAPI main.py:

from fastapi import WebSocket
import asyncio

# Initialize at startup
wet_floor_detector = WetFloorIntegration()

# In your WebSocket handler or endpoint:
@app.websocket("/ws/wet-detection")
async def websocket_wet_detection(websocket: WebSocket):
    await websocket.accept()
    cap = cv2.VideoCapture(0)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect wet areas
            result = wet_floor_detector.detect(frame)
            
            # Send to frontend
            await websocket.send_json({
                "wet_detected": result["wet_detected"],
                "num_detections": result["num_boxes"],
                "confidence": float(result["confidence"]),
            })
            
            # If wet detected, log and alert
            if result["wet_detected"]:
                print(f"⚠️ WET FLOOR ALERT! Boxes: {result['num_boxes']}")
                # Send alert to all connected clients
                for client in manager.active_connections:
                    await client.send_json({"alert": "WET_FLOOR"})
            
            await asyncio.sleep(0.05)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cap.release()
"""

# ═══════════════════════════════════════════════════════════════════════════
#  EXAMPLE USAGE IN STREAMLIT (for streamlit_app.py)
# ═══════════════════════════════════════════════════════════════════════════

"""
# Add to streamlit_app.py:

import streamlit as st

# Initialize detector in session state
if "wet_detector" not in st.session_state:
    st.session_state.wet_detector = WetFloorIntegration()

# In your camera/video processing loop:
if st.checkbox("Enable Wet Floor Detection"):
    stframe = st.empty()
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Detect wet areas
        result = st.session_state.wet_detector.detect(frame)
        
        # Display annotated frame
        stframe.image(result["annotated_frame"], channels="BGR")
        
        # Show alert if needed
        if result["wet_detected"]:
            st.error(f"⚠️ WET FLOOR! {result['num_boxes']} wet area(s) detected!")
            st.audio("alert.mp3")  # Play sound
    
    cap.release()
"""

# ═══════════════════════════════════════════════════════════════════════════
#  SIMPLE STANDALONE TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing wet floor integration...")
    
    detector = WetFloorIntegration()
    cap = cv2.VideoCapture(0)
    
    print("Processing webcam feed...")
    print("Press 'q' to quit\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize for speed
        frame = cv2.resize(frame, (640, 480))
        
        # Detect
        result = detector.detect(frame)
        
        # Display
        cv2.imshow("Wet Floor Detection", result["annotated_frame"])
        
        # Print stats every 10 frames
        if cv2.getTickCount() % 10 == 0:
            status = "🔴 WET!" if result["wet_detected"] else "✅ Dry"
            print(f"{status} Conf: {result['confidence']:.2f} Boxes: {result['num_boxes']}")
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
