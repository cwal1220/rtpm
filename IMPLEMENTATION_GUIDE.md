# Step-by-Step Implementation Guide

## Phase 1: Project Setup (30 minutes)

### Step 1.1: Create new project structure
```bash
# Create new folders
mkdir rtpm-web
cd rtpm-web
mkdir static
```

### Step 1.2: Copy existing code (DO NOT MODIFY)
```bash
# Copy these folders EXACTLY as they are:
cp -r ../rtpm/models ./
cp -r ../rtpm/third_party ./
cp -r ../rtpm/data_structures ./
cp -r ../rtpm/config ./
cp -r ../rtpm/utils ./
```

### Step 1.3: Create requirements.txt
```python
# Copy all lines from original requirements.txt
# Then ADD these lines:
fastapi==0.104.1
uvicorn==0.24.0
websockets==12.0
python-multipart==0.0.6
```

## Phase 2: Create FastAPI Server (2 hours)

### Step 2.1: Create main.py
```python
# File: main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import cv2
import base64
import json
from threading import Thread
import queue

# IMPORTANT: Import existing code WITHOUT any modifications
from models.vision_protocol import VisionProtocol
from models.post_processor import PostProcessor
from models.workers.file_reader import RtpmFileReader
from models.workers.data_updater import RtpmDataUpdater
from config import settings

app = FastAPI(title="RTPM Web API")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global instances (like MainViewModel had)
vision_protocol_instance = None
post_processor_instance = None
file_reader_instance = None
data_updater_instance = None

# Queues for frame and result data
frame_queue = queue.Queue(maxsize=30)
result_queue = queue.Queue(maxsize=100)

# Application state
app_state = {
    "connected": False,
    "running": False,
    "mode": 0,  # 0=projection, 1=injection
    "input_path": "",
    "output_path": "",
    "fps": 0,
    "cpu_usage": 0,
    "memory_usage": 0,
    "npu_usage": [0, 0]
}
```

### Step 2.2: Add connection endpoints
```python
@app.get("/")
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/connect")
async def connect_board():
    global vision_protocol_instance, post_processor_instance
    global file_reader_instance, data_updater_instance

    try:
        # Use EXACT same initialization as MainViewModel.__init__
        vision_protocol_instance = VisionProtocol(
            inputMode=app_state["mode"],
            frameWidth=settings.INJECTION['width'],
            frameHeight=settings.INJECTION['height'],
            frameChannel=settings.INJECTION['channel']
        )

        post_processor_instance = PostProcessor(
            frame_width=settings.INJECTION['width'],
            frame_height=settings.INJECTION['height'],
            label_path=settings.LABEL_PATH
        )

        # Start VisionProtocol thread (it inherits from QThread)
        vision_protocol_instance.start()

        # Initialize workers (exact same as MainViewModel)
        file_reader_instance = RtpmFileReader(
            vision_protocol_instance,
            (settings.INJECTION['height'],
             settings.INJECTION['width'],
             settings.INJECTION['channel'])
        )

        data_updater_instance = RtpmDataUpdater(vision_protocol_instance)

        app_state["connected"] = True
        return {"status": "success", "message": "Board connected"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/disconnect")
async def disconnect_board():
    global vision_protocol_instance

    if vision_protocol_instance:
        vision_protocol_instance.stop()
        vision_protocol_instance = None

    app_state["connected"] = False
    app_state["running"] = False
    return {"status": "success", "message": "Board disconnected"}
```

### Step 2.3: Add control endpoints
```python
@app.post("/api/start")
async def start_test():
    if not app_state["connected"]:
        raise HTTPException(status_code=400, detail="Board not connected")

    if vision_protocol_instance:
        vision_protocol_instance.startControl()
        app_state["running"] = True

        # Start background frame collection
        Thread(target=collect_frames_background, daemon=True).start()

    return {"status": "success", "message": "Test started"}

@app.post("/api/stop")
async def stop_test():
    if vision_protocol_instance:
        vision_protocol_instance.stopControl()
        app_state["running"] = False
    return {"status": "success", "message": "Test stopped"}

def collect_frames_background():
    """Background thread to collect frames from VisionProtocol"""
    while app_state["running"]:
        if vision_protocol_instance:
            # Use existing methods from VisionProtocol
            frame_data = vision_protocol_instance.getFrameData()
            if frame_data is not None:
                frame_queue.put(frame_data)

            result_data = vision_protocol_instance.getResultData()
            if result_data is not None:
                result_queue.put(result_data)
```

### Step 2.4: Add WebSocket streaming
```python
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            if not frame_queue.empty():
                # Get frame from queue
                frame = frame_queue.get_nowait()

                # Apply detection results if available
                if post_processor_instance and not result_queue.empty():
                    result = result_queue.get_nowait()
                    # Use existing PostProcessor method
                    frame = post_processor_instance.draw_object_detection_boxes(
                        frame, result, 0
                    )

                # Encode frame as JPEG
                _, buffer = cv2.imencode('.jpg', frame,
                                        [cv2.IMWRITE_JPEG_QUALITY, 80])
                jpg_base64 = base64.b64encode(buffer).decode('utf-8')

                # Send frame data
                await websocket.send_json({
                    "type": "frame",
                    "data": jpg_base64
                })

            # Maintain ~30 FPS
            await asyncio.sleep(0.033)

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()
```

### Step 2.5: Add status endpoint
```python
@app.get("/api/status")
async def get_status():
    if vision_protocol_instance:
        # Update metrics using existing VisionProtocol methods
        app_state["fps"] = vision_protocol_instance.getCurrentFps()
        app_state["cpu_usage"] = vision_protocol_instance.getCpuUsage()
        app_state["memory_usage"] = vision_protocol_instance.getMemoryUsage()
        app_state["npu_usage"] = vision_protocol_instance.getNpuUsage()

    return app_state

@app.post("/api/mode")
async def set_mode(mode: int):
    app_state["mode"] = mode
    return {"status": "success", "mode": mode}

@app.post("/api/file/input")
async def set_input_file(file_path: str):
    app_state["input_path"] = file_path
    if file_reader_instance:
        file_reader_instance.setFilePath(file_path)
    return {"status": "success", "path": file_path}
```

### Step 2.6: Add main entry point
```python
if __name__ == "__main__":
    print("Starting RTPM Web Server...")
    print("Open browser at: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
```

## Phase 3: Create Web UI (1 hour)

### Step 3.1: Create static/index.html
```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>RTPM Web Monitor</title>
    <style>
        /* Reset and base styles */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f0f2f5;
            padding: 20px;
        }

        /* Layout */
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        /* Control Panel */
        .control-panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        .control-group {
            margin: 15px 0;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }

        /* Buttons */
        button {
            padding: 10px 24px;
            margin: 0 5px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }

        button.primary {
            background: #0066cc;
            color: white;
        }

        button.danger {
            background: #dc3545;
            color: white;
        }

        button.success {
            background: #28a745;
            color: white;
        }

        button:hover { opacity: 0.9; }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            opacity: 0.6;
        }

        /* Video Container */
        .video-container {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        #videoCanvas {
            width: 100%;
            max-width: 1280px;
            height: auto;
            border: 2px solid #ddd;
            border-radius: 8px;
            background: #000;
        }

        /* Status */
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        }

        .status-badge.connected {
            background: #d4edda;
            color: #155724;
        }

        .status-badge.disconnected {
            background: #f8d7da;
            color: #721c24;
        }

        /* Metrics */
        .metrics-bar {
            display: flex;
            gap: 20px;
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }

        .metric-item {
            flex: 1;
            text-align: center;
        }

        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #0066cc;
        }

        .metric-label {
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }

        /* Input fields */
        input[type="text"] {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            width: 400px;
            margin: 0 10px;
        }

        select {
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            margin: 0 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>RTPM - Real-Time Performance Monitor</h1>
            <p style="color: #666; margin-top: 8px;">TCC7500 NPU Board Testing System</p>
        </div>

        <!-- Control Panel -->
        <div class="control-panel">
            <h2 style="margin-bottom: 20px;">Control Panel</h2>

            <!-- Connection Status -->
            <div class="control-group">
                <strong>Connection Status:</strong>
                <span id="connectionStatus" class="status-badge disconnected">Disconnected</span>
            </div>

            <!-- Control Buttons -->
            <div class="control-group">
                <button id="connectBtn" class="primary" onclick="connectBoard()">
                    Connect Board
                </button>
                <button id="disconnectBtn" class="danger" onclick="disconnectBoard()" disabled>
                    Disconnect
                </button>
                <button id="startBtn" class="success" onclick="startTest()" disabled>
                    Start Test
                </button>
                <button id="stopBtn" class="danger" onclick="stopTest()" disabled>
                    Stop Test
                </button>
            </div>

            <!-- Mode Selection -->
            <div class="control-group">
                <strong>Mode:</strong>
                <select id="modeSelect" onchange="setMode(this.value)">
                    <option value="0">Projection (Receive)</option>
                    <option value="1">Injection (Send)</option>
                </select>
            </div>

            <!-- File Path -->
            <div class="control-group">
                <strong>Input File:</strong>
                <input type="text" id="inputPath" placeholder="Enter file path">
                <button onclick="setInputPath()">Set Path</button>
            </div>
        </div>

        <!-- Video Display -->
        <div class="video-container">
            <h2>Live Stream</h2>
            <canvas id="videoCanvas" width="1280" height="720"></canvas>

            <!-- Metrics Display -->
            <div class="metrics-bar">
                <div class="metric-item">
                    <div class="metric-value" id="fps">0</div>
                    <div class="metric-label">FPS</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value" id="cpu">0</div>
                    <div class="metric-label">CPU %</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value" id="memory">0</div>
                    <div class="metric-label">Memory %</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value" id="npu0">0</div>
                    <div class="metric-label">NPU0 %</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value" id="npu1">0</div>
                    <div class="metric-label">NPU1 %</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let ws = null;
        let statusInterval = null;
        const canvas = document.getElementById('videoCanvas');
        const ctx = canvas.getContext('2d');

        // API helper function
        async function apiCall(endpoint, method = 'POST', body = null) {
            try {
                const options = { method };
                if (body) {
                    options.headers = { 'Content-Type': 'application/json' };
                    options.body = JSON.stringify(body);
                }
                const response = await fetch(endpoint, options);
                return await response.json();
            } catch (error) {
                console.error('API Error:', error);
                alert('API Error: ' + error.message);
                return null;
            }
        }

        // Connect to board
        async function connectBoard() {
            const result = await apiCall('/api/connect');
            if (result && result.status === 'success') {
                updateConnectionStatus(true);
                startStatusPolling();
                console.log('Board connected successfully');
            } else {
                alert('Failed to connect: ' + (result?.message || 'Unknown error'));
            }
        }

        // Disconnect from board
        async function disconnectBoard() {
            const result = await apiCall('/api/disconnect');
            if (result && result.status === 'success') {
                updateConnectionStatus(false);
                stopStatusPolling();
                if (ws) {
                    ws.close();
                    ws = null;
                }
                console.log('Board disconnected');
            }
        }

        // Start test
        async function startTest() {
            const result = await apiCall('/api/start');
            if (result && result.status === 'success') {
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = false;
                startVideoStream();
                console.log('Test started');
            } else {
                alert('Failed to start test: ' + (result?.message || 'Unknown error'));
            }
        }

        // Stop test
        async function stopTest() {
            const result = await apiCall('/api/stop');
            if (result && result.status === 'success') {
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
                if (ws) {
                    ws.close();
                    ws = null;
                }
                console.log('Test stopped');
            }
        }

        // Start video streaming
        function startVideoStream() {
            if (ws) ws.close();

            ws = new WebSocket('ws://localhost:8000/ws/stream');

            ws.onopen = () => {
                console.log('WebSocket connected');
            };

            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                if (message.type === 'frame') {
                    const img = new Image();
                    img.onload = () => {
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    };
                    img.src = 'data:image/jpeg;base64,' + message.data;
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
            };
        }

        // Update connection status UI
        function updateConnectionStatus(connected) {
            const statusEl = document.getElementById('connectionStatus');
            const connectBtn = document.getElementById('connectBtn');
            const disconnectBtn = document.getElementById('disconnectBtn');
            const startBtn = document.getElementById('startBtn');

            if (connected) {
                statusEl.textContent = 'Connected';
                statusEl.className = 'status-badge connected';
                connectBtn.disabled = true;
                disconnectBtn.disabled = false;
                startBtn.disabled = false;
            } else {
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'status-badge disconnected';
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
                startBtn.disabled = true;
                document.getElementById('stopBtn').disabled = true;
            }
        }

        // Start polling for status updates
        function startStatusPolling() {
            statusInterval = setInterval(async () => {
                const status = await fetch('/api/status').then(r => r.json());
                if (status) {
                    document.getElementById('fps').textContent = Math.round(status.fps || 0);
                    document.getElementById('cpu').textContent = Math.round(status.cpu_usage || 0);
                    document.getElementById('memory').textContent = Math.round(status.memory_usage || 0);
                    document.getElementById('npu0').textContent = Math.round(status.npu_usage?.[0] || 0);
                    document.getElementById('npu1').textContent = Math.round(status.npu_usage?.[1] || 0);
                }
            }, 1000);
        }

        // Stop polling
        function stopStatusPolling() {
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
        }

        // Set mode
        async function setMode(value) {
            await apiCall('/api/mode', 'POST', { mode: parseInt(value) });
        }

        // Set input file path
        async function setInputPath() {
            const path = document.getElementById('inputPath').value;
            if (path) {
                const result = await apiCall('/api/file/input', 'POST', { file_path: path });
                if (result && result.status === 'success') {
                    console.log('Input path set:', path);
                }
            }
        }

        // Initialize on page load
        window.onload = () => {
            updateConnectionStatus(false);
            console.log('RTPM Web Monitor loaded');
        };
    </script>
</body>
</html>
```

## Phase 4: Testing Checklist

### Basic Tests
- [ ] Server starts with `python main.py`
- [ ] Web page loads at http://localhost:8000
- [ ] Connect button triggers board connection
- [ ] Disconnect button works
- [ ] Start/Stop test buttons work
- [ ] Mode selection works

### Streaming Tests
- [ ] Video displays after starting test
- [ ] FPS counter updates
- [ ] CPU/Memory/NPU metrics update
- [ ] Bounding boxes appear on detected objects

### Integration Tests
- [ ] VisionProtocol communicates with board
- [ ] Raw RGB888 data is received
- [ ] PostProcessor draws detection results
- [ ] File paths can be set

## Common Issues and Solutions

### Issue 1: ImportError for VisionProtocol
**Solution:** Make sure you copied all folders including third_party

### Issue 2: QThread errors
**Solution:** Keep PySide6 in requirements.txt even though UI is not used

### Issue 3: Video not displaying
**Solution:** Check WebSocket connection in browser console (F12)

### Issue 4: Board connection fails
**Solution:** Verify board IP and ports (9998, 9999) are correct

## Final Directory Structure
```
rtpm-web/
├── main.py                    # ✅ Created
├── static/
│   └── index.html            # ✅ Created
├── models/                   # ✅ Copied from original
├── third_party/              # ✅ Copied from original
├── data_structures/          # ✅ Copied from original
├── config/                   # ✅ Copied from original
├── utils/                    # ✅ Copied from original
└── requirements.txt          # ✅ Updated
```

## Run Instructions
```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python main.py

# Open browser
# Navigate to: http://localhost:8000
```