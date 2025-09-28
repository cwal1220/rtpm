"""
FastAPI 기반 RTPM 웹 서버

TCC7500 NPU 모니터링을 위한 웹 기반 애플리케이션
Vision Protocol 통신 로직은 그대로 유지
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import cv2
import base64
import json
import queue
import logging
from typing import Dict, Any

# RTPM 매니저 및 설정 import
from managers import RTPMManager
from config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="RTPM Web API", description="TCC7500 NPU Real-Time Performance Monitor")

# 정적 파일 서빙
app.mount("/static", StaticFiles(directory="static"), name="static")


# 전역 매니저 인스턴스 (단일 인스턴스)
rtpm_manager = RTPMManager()

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
    return await rtpm_manager.connect_board()

@app.post("/api/disconnect") 
async def disconnect_board():
    """TCC7500 보드 연결 해제"""
    return await rtpm_manager.disconnect_board()

@app.post("/api/start")
async def start_test():
    """테스트 시작"""
    return await rtpm_manager.start_test()

@app.post("/api/stop")
async def stop_test():
    """테스트 중지"""
    return await rtpm_manager.stop_test()


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket을 통한 비디오 스트리밍"""
    await websocket.accept()
    logger.info("WebSocket 연결됨")

    try:
        frame_count = 0
        empty_queue_count = 0
        
        while True:
            frame = None
            
            if not rtpm_manager.frame_queue.empty():
                # 큐에서 프레임 가져오기
                frame = rtpm_manager.frame_queue.get_nowait()
                frame_count += 1
                
                # 10번마다 전송 상태 로그
                if frame_count % 10 == 0:
                    logger.info(f"프레임 전송 중: #{frame_count}개 전송")
                
                # 🔧 디버깅: 프레임 정보 로그
                if frame_count <= 3:  # 처음 3개 프레임만
                    logger.info(f"🖼️ [WebSocket] 프레임 #{frame_count} 수신: shape={frame.shape if hasattr(frame, 'shape') else 'N/A'}, dtype={frame.dtype if hasattr(frame, 'dtype') else 'N/A'}")

                # 검출 결과가 있으면 바운딩 박스 그리기
                result_queue_empty = rtpm_manager.result_queue.empty()
                
                # 🔧 디버깅: 결과 큐 상태 로그
                if frame_count <= 3:  # 처음 3개 프레임만
                    logger.info(f"🎯 [WebSocket] 프레임 #{frame_count} 결과 큐 상태: empty={result_queue_empty}")
                
                if rtpm_manager.post_processor_instance and not result_queue_empty:
                    try:
                        result = rtpm_manager.result_queue.get_nowait()
                        logger.info(f"📋 [WebSocket] 결과 데이터 수신: type={type(result)}")
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
                                    # 좌표 스케일링 비율 계산
                                    # NPU 해상도: settings.INJECTION → 웹 표시 해상도: 현재 프레임 크기
                                    current_height, current_width = frame.shape[:2]
                                    npu_width = settings.INJECTION['width']
                                    npu_height = settings.INJECTION['height']
                                    
                                    scale_x = current_width / npu_width
                                    scale_y = current_height / npu_height
                                    
                                    logger.info(f"🎨 [WebSocket] Bounding box 그리기 시작: {len(detection_results)}개 객체, scale=({scale_x:.2f}, {scale_y:.2f})")
                                    
                                    frame = rtpm_manager.post_processor_instance.draw_object_detection_boxes(
                                        frame, detection_results, 0, [scale_x, scale_y]
                                    )
                                    logger.info(f"✅ [WebSocket] Bounding box 그리기 완료")
                                else:
                                    logger.info("❌ [WebSocket] 검출된 객체 없음")
                            else:
                                logger.warning(f"❌ [WebSocket] 처리할 수 없는 결과 데이터 형태: {type(result)}")
                    except queue.Empty:
                        pass
                    except Exception as result_error:
                        logger.warning(f"결과 데이터 처리 오류: {result_error}. Result type: {type(result) if 'result' in locals() else 'Unknown'}")
                        # 오류가 발생해도 프레임은 그대로 전송

                # 프레임 크기 검증 및 리사이징
                if frame is not None and frame.size > 0:
                    # 프레임 차원 확인
                    if len(frame.shape) < 2:
                        logger.error(f"유효하지 않은 프레임 차원: {frame.shape}")
                        continue
                    elif len(frame.shape) == 2:
                        # 그레이스케일 이미지
                        height, width = frame.shape
                    else:
                        # 컬러 이미지 (3차원 이상)
                        height, width = frame.shape[:2]
                    
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
                        
                        # 첫 번째 리사이징에서만 로그 출력
                        if frame_count == 1:
                            logger.info(f"프레임 리사이징: {width}x{height} → {new_width}x{new_height}")
                    
                    # 프레임을 JPEG로 인코딩 (품질 향상)
                    success, buffer = cv2.imencode('.jpg', frame, 
                                                 [cv2.IMWRITE_JPEG_QUALITY, 90])
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
            else:
                # 🔧 디버깅: 큐가 비어있을 때 로그 (주기적으로만)
                empty_queue_count += 1
                
                if empty_queue_count % 100 == 0:  # 100번마다 로그
                    logger.info(f"⏳ [WebSocket] 프레임 큐 비어있음 (연속 {empty_queue_count}회)")
                
                await asyncio.sleep(0.033)

            # ~15 FPS 유지 (테어링 방지)
            # await asyncio.sleep(0.066)

    except WebSocketDisconnect:
        logger.info("WebSocket 클라이언트가 연결을 해제했습니다")
    except Exception as e:
        # WebSocket 연결 종료 관련 에러는 일반적이므로 로그 레벨 조정
        if "1005" in str(e) or "no status received" in str(e):
            logger.info(f"WebSocket 연결이 정상적으로 종료됨: {e}")
        elif "websocket" in str(e).lower() and ("closed" in str(e).lower() or "disconnect" in str(e).lower()):
            logger.info(f"WebSocket 클라이언트 연결 해제: {e}")
        else:
            logger.error(f"WebSocket 오류: {e}")
    finally:
        try:
            logger.info("WebSocket 연결 종료")
            # WebSocket 상태를 안전하게 확인하고 종료
            if hasattr(websocket, 'client_state') and websocket.client_state.name != "DISCONNECTED":
                await websocket.close()
        except Exception as close_error:
            # 종료 과정에서의 에러는 무시 (이미 연결이 끊어진 상태)
            logger.debug(f"WebSocket 종료 과정에서 무시되는 에러: {close_error}")

@app.get("/api/status")
async def get_status():
    """현재 상태 및 성능 메트릭 반환"""
    return await rtpm_manager.get_status()

@app.post("/api/mode")
async def set_mode(request: Dict[str, Any]):
    """동작 모드 설정 (0=projection, 1=injection)"""
    mode = request.get("mode", 0)
    return await rtpm_manager.set_mode(mode)

@app.post("/api/file/input")
async def set_input_file(request: Dict[str, Any]):
    """입력 파일 경로 설정"""
    file_path = request.get("file_path", "")
    return await rtpm_manager.set_input_file(file_path)

@app.post("/api/output/path")
async def set_output_path(request: Dict[str, Any]):
    """출력 경로 설정"""
    output_path = request.get("output_path", "")
    return await rtpm_manager.set_output_path(output_path)

@app.post("/api/save/results")
async def save_results():
    """현재 세션의 결과 데이터 저장"""
    return await rtpm_manager.save_results()

@app.post("/api/export/coco")
async def export_coco_annotations():
    """COCO 형식으로 annotation 내보내기"""
    return await rtpm_manager.export_coco_annotations()

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
