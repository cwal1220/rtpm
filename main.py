"""
FastAPI 기반 RTPM 웹 서버

기존 PySide6 데스크톱 애플리케이션을 웹 기반으로 변환
Vision Protocol 통신 로직은 그대로 유지
"""

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
import logging
from typing import Dict, Any

# 기존 코드들을 수정 없이 그대로 import
from models.vision_protocol import VisionProtocol
from models.post_processor import PostProcessor
from models.workers.file_reader import RtpmFileReader
from models.workers.data_updater import RtpmDataUpdater
from data_structures.enums import PerformanceDataType, ResultType
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="RTPM Web API", description="TCC7500 NPU Real-Time Performance Monitor")

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")

# 전역 인스턴스들 (기존 MainViewModel과 동일한 구조)
vision_protocol_instance = None
post_processor_instance = None
file_reader_instance = None
data_updater_instance = None

# 프레임 및 결과 데이터를 위한 큐
frame_queue = queue.Queue(maxsize=30)
result_queue = queue.Queue(maxsize=100)

# 애플리케이션 상태
app_state = {
    "connected": False,
    "running": False,
    "mode": 0,  # 0=projection(receive), 1=injection(send)
    "input_path": "",
    "output_path": "",
    "fps": 0,
    "cpu_usage": 0,
    "memory_usage": 0,
    "npu_usage": [0, 0]
}

@app.get("/")
async def read_index():
    """메인 페이지 제공"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Web UI not found. Please create static/index.html</h1>")

@app.post("/api/connect")
async def connect_board():
    """TCC7500 보드에 연결"""
    global vision_protocol_instance, post_processor_instance
    global file_reader_instance, data_updater_instance

    try:
        logger.info("보드 연결 시작...")
        
        # 기존 MainViewModel.__init__과 동일한 초기화
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

        # VisionProtocol 스레드 시작 (QThread 상속)
        vision_protocol_instance.start()

        # 워커 인스턴스들 초기화 (기존과 동일)
        file_reader_instance = RtpmFileReader(
            vision_protocol_instance,
            (settings.INJECTION['height'], 
             settings.INJECTION['width'],
             settings.INJECTION['channel'])
        )

        data_updater_instance = RtpmDataUpdater(vision_protocol_instance)

        app_state["connected"] = True
        logger.info("보드 연결 성공")
        return {"status": "success", "message": "Board connected successfully"}

    except Exception as e:
        logger.error(f"보드 연결 실패: {str(e)}")
        return {"status": "error", "message": f"Connection failed: {str(e)}"}

@app.post("/api/disconnect") 
async def disconnect_board():
    """TCC7500 보드 연결 해제"""
    global vision_protocol_instance

    try:
        if vision_protocol_instance:
            vision_protocol_instance.stop()
            vision_protocol_instance = None

        app_state["connected"] = False
        app_state["running"] = False
        logger.info("보드 연결 해제")
        return {"status": "success", "message": "Board disconnected"}

    except Exception as e:
        logger.error(f"보드 연결 해제 실패: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.post("/api/start")
async def start_test():
    """테스트 시작"""
    if not app_state["connected"]:
        raise HTTPException(status_code=400, detail="Board not connected")

    try:
        if vision_protocol_instance:
            # VisionProtocol은 이미 실행 중이므로 running 상태만 변경
            app_state["running"] = True

            # 백그라운드에서 프레임 수집 시작
            Thread(target=collect_frames_background, daemon=True).start()
            
            logger.info("테스트 시작")
            return {"status": "success", "message": "Test started"}

    except Exception as e:
        logger.error(f"테스트 시작 실패: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.post("/api/stop")
async def stop_test():
    """테스트 중지"""
    try:
        if vision_protocol_instance:
            # running 상태만 변경 (VisionProtocol 자체는 연결 유지)
            app_state["running"] = False
            
        logger.info("테스트 중지")
        return {"status": "success", "message": "Test stopped"}

    except Exception as e:
        logger.error(f"테스트 중지 실패: {str(e)}")
        return {"status": "error", "message": str(e)}

def collect_frames_background():
    """백그라운드에서 VisionProtocol로부터 프레임 수집"""
    logger.info("프레임 수집 백그라운드 스레드 시작")
    
    while app_state["running"]:
        try:
            if vision_protocol_instance:
                # 실제 VisionProtocol 메소드 사용
                frame_data = vision_protocol_instance.getFrame()
                if frame_data is not None:
                    logger.debug(f"백그라운드에서 프레임 수집: type={type(frame_data)}, shape={frame_data.shape if hasattr(frame_data, 'shape') else 'No shape'}")
                    
                    # 프레임 데이터 검증 및 reshape
                    if hasattr(frame_data, 'shape'):
                        if len(frame_data.shape) == 1:
                            # 1차원 Raw RGB 데이터를 이미지 형태로 reshape
                            expected_size = settings.INJECTION['width'] * settings.INJECTION['height'] * settings.INJECTION['channel']
                            if frame_data.shape[0] == expected_size:
                                # (2764800,) → (720, 1280, 3) 형태로 reshape
                                frame_data = frame_data.reshape(
                                    settings.INJECTION['height'], 
                                    settings.INJECTION['width'], 
                                    settings.INJECTION['channel']
                                )
                                logger.debug(f"프레임 reshape 완료: {frame_data.shape}")
                            else:
                                logger.warning(f"예상과 다른 프레임 크기: {frame_data.shape[0]} != {expected_size}")
                                continue
                        elif len(frame_data.shape) < 2:
                            logger.warning(f"유효하지 않은 프레임 차원: {frame_data.shape}")
                            continue
                        
                        # 큐가 가득 차면 오래된 프레임 제거
                        if frame_queue.full():
                            try:
                                frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        frame_queue.put(frame_data)
                    else:
                        logger.warning(f"유효하지 않은 프레임 데이터: {type(frame_data)}")
                else:
                    logger.debug("getFrame()에서 None 반환됨")

                result_data = vision_protocol_instance.getDetectionResult()
                if result_data is not None:
                    if result_queue.full():
                        try:
                            result_queue.get_nowait()
                        except queue.Empty:
                            pass
                    result_queue.put(result_data)

        except Exception as e:
            logger.error(f"프레임 수집 오류: {str(e)}")
            
        # CPU 사용량 조절을 위한 짧은 대기
        import time
        time.sleep(0.01)

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket을 통한 비디오 스트리밍"""
    await websocket.accept()
    logger.info("WebSocket 연결됨")

    try:
        while True:
            if not frame_queue.empty():
                # 큐에서 프레임 가져오기
                frame = frame_queue.get_nowait()

                # 검출 결과가 있으면 바운딩 박스 그리기
                if post_processor_instance and not result_queue.empty():
                    try:
                        result = result_queue.get_nowait()
                        # 실제 결과 데이터 구조 확인 및 처리
                        if result is not None:
                            logger.debug(f"Result data type: {type(result)}, content: {result}")
                            
                            # 결과 데이터가 문자열인 경우 JSON 파싱 시도
                            if isinstance(result, str):
                                try:
                                    result = json.loads(result)
                                    logger.debug(f"Parsed JSON result: {result}")
                                except json.JSONDecodeError:
                                    logger.warning(f"결과 데이터가 JSON 형식이 아닙니다: {result}")
                                    continue
                            
                            # 실제 VisionProtocol 결과 데이터 구조에 맞게 변환
                            detection_results = []
                            if isinstance(result, dict):
                                # cluster1의 od (object detection) 배열 추출
                                if 'cluster1' in result and 'od' in result['cluster1']:
                                    detection_results = result['cluster1']['od']
                                    logger.debug(f"추출된 검출 결과: {detection_results}")
                                
                                # 검출 결과가 있을 때만 PostProcessor 호출
                                if detection_results:
                                    frame = post_processor_instance.draw_object_detection_boxes(
                                        frame, detection_results, 0
                                    )
                                else:
                                    logger.debug("검출된 객체 없음")
                            else:
                                logger.debug(f"처리할 수 없는 결과 데이터 형태: {type(result)}")
                    except queue.Empty:
                        pass
                    except Exception as result_error:
                        logger.warning(f"결과 데이터 처리 오류: {result_error}. Result type: {type(result) if 'result' in locals() else 'Unknown'}")
                        # 오류가 발생해도 프레임은 그대로 전송

                # 프레임 크기 검증 및 리사이징
                if frame is not None and frame.size > 0:
                    logger.debug(f"프레임 shape: {frame.shape}, dtype: {frame.dtype}")
                    
                    # 프레임 차원 확인
                    if len(frame.shape) < 2:
                        logger.error(f"유효하지 않은 프레임 차원: {frame.shape}")
                        continue
                    elif len(frame.shape) == 2:
                        # 그레이스케일 이미지
                        height, width = frame.shape
                        logger.debug(f"그레이스케일 프레임: {width}x{height}")
                    else:
                        # 컬러 이미지 (3차원 이상)
                        height, width = frame.shape[:2]
                        logger.debug(f"컬러 프레임: {width}x{height}, channels: {frame.shape[2] if len(frame.shape) > 2 else 'N/A'}")
                    
                    # OpenCV 최대 크기 제한 (65500 픽셀)을 고려하여 리사이징
                    max_dimension = 1920  # 최대 해상도 제한
                    if width > max_dimension or height > max_dimension:
                        if width > height:
                            new_width = max_dimension
                            new_height = int(height * (max_dimension / width))
                        else:
                            new_height = max_dimension
                            new_width = int(width * (max_dimension / height))
                        
                        frame = cv2.resize(frame, (new_width, new_height))
                        logger.debug(f"리사이징된 프레임 크기: {new_width}x{new_height}")
                    
                    # 프레임을 JPEG로 인코딩
                    success, buffer = cv2.imencode('.jpg', frame, 
                                                 [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if success:
                        jpg_base64 = base64.b64encode(buffer).decode('utf-8')
                    else:
                        logger.error("JPEG 인코딩 실패")
                        continue
                else:
                    logger.warning("유효하지 않은 프레임 데이터")
                    continue

                # 프레임 데이터 전송
                await websocket.send_json({
                    "type": "frame",
                    "data": jpg_base64
                })

            # ~30 FPS 유지
            await asyncio.sleep(0.033)

    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
    finally:
        logger.info("WebSocket 연결 종료")
        await websocket.close()

@app.get("/api/status")
async def get_status():
    """현재 상태 및 성능 메트릭 반환"""
    try:
        if vision_protocol_instance and app_state["connected"]:
            # 성능 데이터 가져오기
            perf_data = vision_protocol_instance.gerPerformanceData()  # 실제 메소드명
            if perf_data:
                # 성능 데이터 파싱 (실제 구조에 따라 조정 필요)
                data_type = perf_data[0] if len(perf_data) > 0 else None
                if data_type == PerformanceDataType.FPS and len(perf_data) > 2:
                    app_state["fps"] = perf_data[2]
                elif data_type == PerformanceDataType.CPU_PERFORMANCE and len(perf_data) > 2:
                    app_state["cpu_usage"] = perf_data[2]
                elif data_type == PerformanceDataType.MEMORY and len(perf_data) > 2:
                    app_state["memory_usage"] = perf_data[2]
                elif data_type == PerformanceDataType.NPU_USAGE and len(perf_data) > 3:
                    app_state["npu_usage"] = [perf_data[2], perf_data[3]]

        return app_state

    except Exception as e:
        logger.error(f"상태 조회 오류: {str(e)}")
        return app_state

@app.post("/api/mode")
async def set_mode(request: Dict[str, Any]):
    """동작 모드 설정 (0=projection, 1=injection)"""
    try:
        mode = request.get("mode", 0)
        app_state["mode"] = mode
        logger.info(f"모드 변경: {mode}")
        return {"status": "success", "mode": mode}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/file/input")
async def set_input_file(request: Dict[str, Any]):
    """입력 파일 경로 설정"""
    try:
        file_path = request.get("file_path", "")
        app_state["input_path"] = file_path
        
        if file_reader_instance:
            file_reader_instance.setFilePath(file_path)
            
        logger.info(f"입력 파일 경로 설정: {file_path}")
        return {"status": "success", "path": file_path}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("=" * 50)
    print("RTPM Web Server 시작")
    print("브라우저에서 다음 주소로 접속하세요:")
    print("http://localhost:8000")
    print("=" * 50)
    
    # 서버 실행
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        reload=False,
        log_level="info"
    )
