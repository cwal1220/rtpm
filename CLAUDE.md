# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RTPM (Real-Time Performance Monitor) is a FastAPI-based web application for monitoring TCC7500 NPU (Neural Processing Unit) performance in real-time. It provides a web interface for viewing object detection results, streaming video with bounding boxes, and collecting performance metrics.

**Key Technology**: This project uses Vision Protocol, a proprietary communication protocol from Telechips for TCC7500 board communication over Ethernet.

## Architecture

### Core Components

**1. FastAPI Web Server** ([main.py](main.py))
- Entry point for the application
- Provides REST API endpoints and MJPEG video streaming
- Single-instance design: uses a global `RTPMService` instance to manage all board operations

**2. RTPMService** ([services/rtpm_service.py](services/rtpm_service.py))
- Central orchestrator that manages all NPU communication and data flow
- Coordinates multiple threaded components (VisionProtocol, FileReader, DataUpdater)
- Implements sequence number-based frame-result synchronization for accurate bounding box overlay
- Manages two operational modes: Projection (receive frames from board) and Injection (send frames to board)
- Collects detection results and performance metrics for session-based storage

**3. VisionProtocol** ([services/vision_protocol.py](services/vision_protocol.py))
- Threading.Thread subclass that handles low-level board communication
- Uses Telechips Vision Protocol C library (via Cython bindings in third_party/)
- Manages two separate connections: MESSAGE_MODE (port 9999) for results/metrics, STREAM_MODE (port 9998) for frame data
- Maintains internal queues for frames, detection results, and performance data
- Includes FrameReader thread for receiving frames in Projection mode

**4. PostProcessor** ([services/post_processor.py](services/post_processor.py))
- Draws bounding boxes and labels on frames using OpenCV
- Creates COCO-format annotations from detection results
- Loads category labels from [labels/coco.txt](labels/coco.txt)

**5. Worker Threads**
- **RtpmFileReader** ([services/workers/file_reader.py](services/workers/file_reader.py)): Reads images/videos from disk and sends to NPU in Injection mode
- **RtpmDataUpdater** ([services/workers/data_updater.py](services/workers/data_updater.py)): Polls for performance data updates

### Data Flow

**Injection Mode (mode=1)**: Image folder → FileReader → VisionProtocol.sendFrame() → NPU → Results via MESSAGE_MODE → RTPMService → PostProcessor → MJPEG stream

**Projection Mode (mode=0)**: NPU → STREAM_MODE → FrameReader → RTPMService → Results via MESSAGE_MODE → PostProcessor → MJPEG stream

### Critical Synchronization Pattern

The codebase uses **sequence numbers** to match frames with their detection results:
1. When sending/receiving a frame, store it in `sent_frames_info[sequence_number]` with metadata
2. When detection results arrive with matching sequence number, retrieve the original frame
3. Draw bounding boxes on the matched frame
4. Clean up the entry to prevent memory leaks

This ensures bounding boxes are drawn on the correct frames even with async processing.

## Common Development Commands

### Running the Application

```bash
# Start the web server (default port 8000)
python main.py
```

Access the web interface at `http://localhost:8000`

### Installing Dependencies

```bash
# Create virtual environment (recommended)
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Building Vision Protocol Library

The Vision Protocol Cython extension must be built before first use:

```bash
cd third_party/visionprotocol/cython_visionprotocol

# Linux
python setup.py build_ext --inplace

# Windows
python setup.py build_ext --inplace --plat-name win-amd64
```

**Note**: Pre-built wheels are available in [third_party/visionprotocol/](third_party/visionprotocol/) for macOS ARM64.

## Configuration

### Network Settings

Vision Protocol uses hardcoded network settings in [services/vision_protocol.py](services/vision_protocol.py):
- IP: `0.0.0.0` (listens on all interfaces)
- Message port: `9999`
- Stream port: `9998`

### Frame Dimensions

Edit [config/settings.py](config/settings.py) to change frame resolution:
```python
INJECTION = {
    "width": 1280,
    "height": 720,
    "channel": 3,
}
```

**Important**: PROJECTION and INJECTION settings must match the NPU's expected dimensions.

## API Endpoints

- `POST /api/connect` - Connect to TCC7500 board (requires `{"mode": 0 or 1}`)
- `POST /api/disconnect` - Disconnect from board
- `POST /api/start` - Start test (requires `{"input_path": "...", "output_path": "..."}`)
- `POST /api/stop` - Stop test
- `GET /api/status` - Get current status and performance metrics
- `GET /video/mjpeg` - MJPEG video stream endpoint
- `POST /api/save/results` - Save detection results to JSON
- `POST /api/export/coco` - Export COCO-format annotations

## Thread Management Guidelines

1. **VisionProtocol** starts automatically when instantiated and runs until `_stop_event` is set
2. **FileReader** cannot be restarted after stopping (Python Thread limitation) - create a new instance for each test run
3. Background collection thread in RTPMService is daemon=True for clean shutdown
4. Always join threads with timeout to prevent indefinite blocking

## Testing Workflow

1. Connect to board: `POST /api/connect` with mode (0=projection, 1=injection)
2. Start test: `POST /api/start` with input/output paths (injection mode) or empty (projection mode)
3. Monitor video stream: `GET /video/mjpeg`
4. Check status: `GET /api/status` (polls every second in web UI)
5. Stop test: `POST /api/stop`
6. Save results: `POST /api/save/results` or `POST /api/export/coco`
7. Disconnect: `POST /api/disconnect`

## MacOS Support

Recent commits added macOS compatibility. The project includes pre-built Vision Protocol wheels for macOS ARM64 (Apple Silicon) in [third_party/visionprotocol/](third_party/visionprotocol/).

## Logging

All modules use Python's `logging` module with DEBUG level enabled by default. Check console output for detailed execution traces, including:
- Frame send/receive events with sequence numbers
- Detection result matching
- Thread lifecycle events
- Performance metrics updates
