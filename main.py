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
async def connect_board(request: Dict[str, Any]):
    """TCC7500 보드에 연결 (모드 포함)"""
    mode = request.get("mode", 0)
    return await rtpm_manager.connect_board(mode)

@app.post("/api/disconnect") 
async def disconnect_board():
    """TCC7500 보드 연결 해제"""
    return await rtpm_manager.disconnect_board()

@app.post("/api/start")
async def start_test(request: Dict[str, Any]):
    """테스트 시작 (입력/출력 경로 포함)"""
    input_path = request.get("input_path", "")
    output_path = request.get("output_path", "")

    return await rtpm_manager.start_test(input_path, output_path)

@app.post("/api/stop")
async def stop_test():
    """테스트 중지"""
    return await rtpm_manager.stop_test()


@app.get("/video/mjpeg")
async def mjpeg_stream():
    """MJPEG 스트리밍 (multipart/x-mixed-replace)"""

    async def generate_frames():
        """프레임 생성기 - MJPEG 형식으로 연속 전송"""
        logger.info("MJPEG 스트림 시작")

        try:
            while True:
                # JPEG 바이트 큐에서 가져오기 (이미 인코딩된 바이트)
                try:
                    jpeg_bytes = rtpm_manager.frame_queue.get_nowait()

                    # MJPEG 형식으로 전송
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' +
                           jpeg_bytes + b'\r\n')

                except queue.Empty:
                    await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"MJPEG 스트림 오류: {e}")
        finally:
            logger.info("MJPEG 스트림 종료")

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/status")
async def get_status():
    """현재 상태 및 성능 메트릭 반환"""
    return await rtpm_manager.get_status()


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
