# FastAPI Refactoring Requirements for RTPM System

## Project Overview
Convert the existing PySide6-based RTPM (Real-Time Performance Monitor) desktop application to a FastAPI-based web application for monitoring TCC7500 NPU chip performance.

## CRITICAL REQUIREMENTS
1. **DO NOT MODIFY** any Vision Protocol communication logic
2. **REUSE ALL EXISTING** Vision Protocol, PostProcessor, and Worker classes without changes
3. **NO SECURITY FEATURES** required (internal network use only)
4. **SIMPLE IMPLEMENTATION** - maintainable by junior developers
5. **NO DOCKER** - must run with just `pip install -r requirements.txt`

## Project Structure

```
rtpm-web/
├── main.py                          # NEW: FastAPI server
├── models/                          # COPY AS-IS from existing project
│   ├── vision_protocol.py           # DO NOT MODIFY
│   ├── post_processor.py            # DO NOT MODIFY
│   └── workers/                     # DO NOT MODIFY
│       ├── processing_worker.py
│       ├── file_reader.py
│       ├── image_saver.py
│       ├── video_recorder.py
│       └── data_updater.py
├── third_party/                     # COPY AS-IS from existing project
│   └── visionprotocol/
│       └── cython_visionprotocol/
│           └── vision_api.py        # C library bindings - DO NOT MODIFY
├── data_structures/                 # COPY AS-IS from existing project
│   ├── msginfo.py
│   ├── packet.py
│   ├── cpu_utilization.py
│   ├── sdk_npu_usage.py
│   └── sdk_mem_usage.py
├── config/
│   └── settings.py                  # COPY AS-IS from existing project
├── utils/
│   └── logger.py                    # COPY AS-IS from existing project
├── static/
│   └── index.html                   # NEW: Simple web UI (single file)
└── requirements.txt                 # UPDATE: Add FastAPI dependencies

## Files to DELETE from existing project
- views/*.py (all PySide6 UI files)
- view_models/main_view_model.py
- main.py (old PySide6 main)
- Any *.ui or *.qrc files

## Implementation Tasks

### Task 1: Setup FastAPI Server (main.py)
Create a new main.py file that:
1. Imports existing VisionProtocol and PostProcessor classes
2. Creates FastAPI app instance
3. Serves static files (HTML/JS/CSS)
4. Manages VisionProtocol instance lifecycle

### Task 2: Implement REST API Endpoints
Required endpoints:
- `POST /api/connect` - Connect to TCC7500 board (calls VisionProtocol.start())
- `POST /api/disconnect` - Disconnect from board (calls VisionProtocol.stop())
- `POST /api/start` - Start test (calls VisionProtocol.startControl())
- `POST /api/stop` - Stop test (calls VisionProtocol.stopControl())
- `GET /api/status` - Get current status and metrics
- `POST /api/mode` - Set injection/projection mode
- `POST /api/file/input` - Set input file path

### Task 3: Implement WebSocket Streaming
- `WS /ws/stream` - Stream video frames
  - Get frames using VisionProtocol.getFrameData()
  - Get results using VisionProtocol.getResultData()
  - Draw bounding boxes using PostProcessor.draw_object_detection_boxes()
  - Encode as JPEG and send as base64

### Task 4: Create Simple Web UI (static/index.html)
Single HTML file with embedded CSS and JavaScript:
- Connection control buttons
- Test start/stop buttons
- Canvas for video display
- Status indicators for FPS, CPU, Memory, NPU usage
- NO frameworks (React/Vue) - use vanilla JavaScript only

## Code Examples

### main.py structure:
```python
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import existing classes WITHOUT modification
from models.vision_protocol import VisionProtocol
from models.post_processor import PostProcessor
from config import settings

app = FastAPI()

# Global instances
vision_protocol_instance = None
post_processor_instance = None

@app.post("/api/connect")
async def connect_board():
    global vision_protocol_instance
    # Initialize using existing VisionProtocol class
    vision_protocol_instance = VisionProtocol(
        inputMode=0,  # from settings
        frameWidth=settings.INJECTION['width'],
        frameHeight=settings.INJECTION['height'],
        frameChannel=settings.INJECTION['channel']
    )
    vision_protocol_instance.start()  # Use existing method
    return {"status": "connected"}

# ... other endpoints ...

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### WebSocket streaming:
```python
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    while True:
        # Use existing methods
        frame = vision_protocol_instance.getFrameData()
        result = vision_protocol_instance.getResultData()

        # Use existing PostProcessor
        if result:
            frame = post_processor_instance.draw_object_detection_boxes(
                frame, result, 0
            )

        # Convert and send
        _, buffer = cv2.imencode('.jpg', frame)
        await websocket.send_text(base64.b64encode(buffer).decode())
```

## Requirements.txt additions:
```
# Keep all existing dependencies
# Add these new ones:
fastapi==0.104.1
uvicorn==0.24.0
websockets==12.0
python-multipart==0.0.6
```

## Testing Instructions
1. Copy required folders from existing project
2. Create new main.py and static/index.html
3. Update requirements.txt
4. Run: `pip install -r requirements.txt`
5. Run: `python main.py`
6. Open browser: http://localhost:8000

## Important Notes
- Vision Protocol MUST work exactly as before - no modifications
- Keep using existing C library bindings through third_party folder
- Raw RGB888 data handling must remain unchanged
- Board communication (ports 9998, 9999) must remain unchanged
- All existing data structures must be preserved

## Success Criteria
1. Board connection/disconnection works
2. Live video streaming displays in browser
3. Test start/stop controls work
4. Performance metrics (FPS, CPU, NPU) display correctly
5. No modifications to Vision Protocol code
6. Single command installation and execution