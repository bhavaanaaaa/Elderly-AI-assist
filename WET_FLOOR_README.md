# 🌊 WET FLOOR DETECTION SYSTEM

Detects wet areas and slip hazards in real-time using your trained `wet_floor.pt` YOLOv8 model.

## 📋 Quick Start

### 1️⃣ Install Dependencies
```bash
pip install -r requirements_wet_floor.txt
```

### 2️⃣ Quick Test (5 seconds to see it working)
```bash
python quick_wet_floor_test.py
```
- Opens your webcam
- Detects wet areas in real-time
- Shows red bounding boxes around detected wet zones
- Press 'q' to quit

### 3️⃣ Full System with Logging & Alerts
```bash
python wet_floor_detector.py
```

## 🎯 Features

✅ **Real-time Detection** - Detects wet areas from webcam or video  
✅ **Audio Alerts** - Speaks warnings when wet floor detected  
✅ **CSV Logging** - Records all detections with timestamps  
✅ **Visual Feedback** - Red bounding boxes + alert banner  
✅ **Statistics** - Tracks detection metrics  
✅ **Video Processing** - Batch process video files  

## 🎮 How to Use

### Webcam Mode (Live Detection)
```bash
python wet_floor_detector.py
```
- Press `q` to quit
- Press `s` to save current frame

### Video File Mode (Batch Processing)
```bash
python wet_floor_detector.py path/to/video.mp4
```
Creates an annotated output video with all detections marked.

## 📊 Output Files

- `wet_floor_detections.csv` - Detection log with timestamps
- `wet_floor_output_*.mp4` - Annotated video (when processing video)
- `wet_floor_detection_*.jpg` - Saved frames from webcam

## ⚙️ Configuration

Edit settings in `wet_floor_detector.py`:

```python
CONFIDENCE_THRESHOLD = 0.5        # Minimum detection confidence (0-1)
SPEAK_COOLDOWN = 5                # Seconds between voice alerts
MIN_DETECTION_AREA = 100          # Min pixel area to trigger alert
ALERT_ZONE_HEIGHT_RATIO = 0.7     # Alert if wet in bottom 70% of frame
```

## 📡 Integration with Backend

The detector can be integrated into your `backend/main.py`:

```python
from wet_floor_detector import WetFloorDetector

detector = WetFloorDetector()
detections, annotated_frame = detector.detect_wet_areas(frame)

if detections:
    # Handle wet floor alert
    print(f"⚠️ {len(detections)} wet area(s) detected!")
```

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Model not found | Ensure `backend/wet_floor.pt` exists |
| No detections | Lower `CONFIDENCE_THRESHOLD` in settings |
| Audio not working | Check pyttsx3 installation: `pip install pyttsx3` |
| Slow performance | Reduce frame resolution or confidence threshold |

## 📝 CSV Log Format

```
Timestamp,Wet_Area_Detected,Confidence,Number_of_Boxes,Total_Detection_Area,Frame_Position,Alert_Triggered
2024-01-15 10:30:45,YES,0.92,2,15000,ALERT ZONE,YES
2024-01-15 10:30:46,NO,0.00,0,0,safe zone,NO
```

## 🎓 Model Training (if needed)

If you need to retrain the model:

```bash
# In your training environment
yolo detect train data=dataset/data.yaml model=yolov8n.pt epochs=100 imgsz=640
```

---

**Created for:** Hospital Safety & Wet Floor Detection System  
**Model:** `wet_floor.pt` (YOLOv8)  
**Status:** ✅ Ready to deploy
