"""
FastAPI 기반 RTPM 웹 서버

TCC7500 NPU 모니터링을 위한 웹 기반 애플리케이션
Vision Protocol 통신 로직은 그대로 유지
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn
import asyncio
import cv2
import json
import queue
import logging
from typing import Dict, Any

# RTPM 매니저 및 설정 import
from managers import RTPMManager
from config import settings

# 로깅 설정 (DEBUG 레벨로 상세 로그 출력)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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


@app.get("/video/mjpeg")
async def mjpeg_stream():
    """MJPEG 스트리밍 (multipart/x-mixed-replace)"""

    async def generate_frames():
        """프레임 생성기 - MJPEG 형식으로 연속 전송"""
        frame_count = 0
        empty_count = 0

        logger.info("MJPEG 스트림 시작")

        try:
            while True:
                # 프레임 큐에서 가져오기
                if not rtpm_manager.frame_queue.empty():
                    frame = rtpm_manager.frame_queue.get_nowait()
                    frame_count += 1
                    empty_count = 0

                    # 10프레임마다 로그
                    if frame_count % 10 == 0:
                        logger.info(f"MJPEG 프레임 전송 중: #{frame_count}개")

                    # 검출 결과가 있으면 바운딩 박스 그리기
                    if rtpm_manager.post_processor_instance and not rtpm_manager.result_queue.empty():
                        try:
                            result = rtpm_manager.result_queue.get_nowait()

                            # 결과 데이터 처리
                            if result is not None:
                                # 문자열이면 JSON 파싱
                                if isinstance(result, str):
                                    try:
                                        result = json.loads(result)
                                    except json.JSONDecodeError:
                                        logger.warning(f"JSON 파싱 실패: {result}")
                                        result = None

                                # 검출 결과 추출
                                if isinstance(result, dict):
                                    detection_results = []
                                    if 'cluster1' in result and 'od' in result['cluster1']:
                                        detection_results = result['cluster1']['od']

                                    # 바운딩 박스 그리기
                                    if detection_results:
                                        current_height, current_width = frame.shape[:2]
                                        npu_width = settings.INJECTION['width']
                                        npu_height = settings.INJECTION['height']

                                        scale_x = current_width / npu_width
                                        scale_y = current_height / npu_height

                                        frame = rtpm_manager.post_processor_instance.draw_object_detection_boxes(
                                            frame, detection_results, 0, [scale_x, scale_y]
                                        )
                        except queue.Empty:
                            pass
                        except Exception as e:
                            logger.warning(f"검출 결과 처리 오류: {e}")

                    # 프레임 크기 검증 및 리사이징
                    if frame is not None and frame.size > 0:
                        # 프레임 차원 확인
                        if len(frame.shape) < 2:
                            logger.error(f"유효하지 않은 프레임 차원: {frame.shape}")
                            continue

                        height, width = frame.shape[:2]

                        # 최대 해상도 제한
                        max_dimension = 1920
                        if width > max_dimension or height > max_dimension:
                            if width > height:
                                new_width = max_dimension
                                new_height = int(height * (max_dimension / width))
                            else:
                                new_height = max_dimension
                                new_width = int(width * (max_dimension / height))

                            frame = cv2.resize(frame, (new_width, new_height))

                        # JPEG 인코딩 (품질 85)
                        success, buffer = cv2.imencode('.jpg', frame,
                                                     [cv2.IMWRITE_JPEG_QUALITY, 85])

                        if success:
                            # MJPEG 형식으로 전송
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' +
                                   buffer.tobytes() + b'\r\n')
                        else:
                            logger.error("JPEG 인코딩 실패")

                    # FPS 제한 (약 30 FPS)
                    await asyncio.sleep(0.033)

                else:
                    # 큐가 비어있으면 대기
                    empty_count += 1
                    if empty_count % 100 == 0:
                        logger.debug(f"프레임 큐 비어있음 (연속 {empty_count}회)")

                    await asyncio.sleep(0.033)

        except Exception as e:
            logger.error(f"MJPEG 스트림 오류: {e}", exc_info=True)
        finally:
            logger.info(f"MJPEG 스트림 종료 (총 {frame_count}프레임 전송)")

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


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
