"""
Quick start script for wet floor detection
Run this to test the wet_floor.pt model immediately
"""

import cv2
from ultralytics import YOLO
import os

def quick_test_webcam():
    """Quick test of wet floor model with webcam"""
    
    model_path = "backend/wet_floor.pt"
    
    # Check if model exists
    if not os.path.exists(model_path):
        print(f"❌ Error: {model_path} not found!")
        print("   Make sure wet_floor.pt is in the backend/ folder")
        return
    
    print("🔄 Loading wet floor model...")
    model = YOLO(model_path)
    print("✅ Model loaded!")
    
    print("🎥 Starting webcam... Press 'q' to quit")
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Resize for faster processing
        frame = cv2.resize(frame, (640, 480))
        
        # Run detection
        results = model(frame, conf=0.5, verbose=False)
        
        # Draw results
        if results[0].boxes is not None:
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                
                # Draw red box for wet areas
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"WET {conf:.2f}", (x1, y1-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # Alert banner
                h, w = frame.shape[:2]
                cv2.rectangle(frame, (0, 0), (w, 60), (0, 0, 255), -1)
                cv2.putText(frame, "⚠️ WET FLOOR DETECTED!", (20, 40),
                           cv2.FONT_HERSHEY_BOLD, 1, (255, 255, 255), 2)
        
        # Show frame
        cv2.imshow("Wet Floor Detection", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    quick_test_webcam()
