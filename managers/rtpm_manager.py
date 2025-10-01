"""
RTPM 매니저 클래스
TCC7500 NPU 모니터링을 위한 상태 및 로직 관리
"""

import queue
import logging
from threading import Thread
import time
from fastapi import HTTPException
import cv2

# 기존 코드들을 수정 없이 그대로 import
from models.vision_protocol import VisionProtocol
from models.post_processor import PostProcessor
from models.workers.file_reader import RtpmFileReader
from models.workers.data_updater import RtpmDataUpdater
from data_structures.enums import PerformanceDataType
from config import settings


# 로깅 설정 
logger = logging.getLogger(__name__)


class RTPMManager:
    """RTPM 애플리케이션의 모든 상태와 로직을 관리하는 클래스"""
    
    def __init__(self):
        # 인스턴스들
        self.vision_protocol_instance = None
        self.post_processor_instance = None
        self.file_reader_instance = None
        self.data_updater_instance = None
        
        # 프레임 및 결과 데이터를 위한 큐 (단순한 방식)
        self.frame_queue = queue.Queue(maxsize=30)
        self.result_queue = queue.Queue(maxsize=100)

        # 결과 데이터 저장을 위한 컬렉션
        self.session_results = []  # 현재 세션의 모든 결과 저장
        self.performance_data = []  # 성능 데이터 저장
        self.current_session_id = None  # 현재 세션 ID

        # 시퀀스 번호 기반 프레임-결과 동기화를 위한 딕셔너리
        self.sent_frames_info = {}  # {sequence_number: {"file_name": "...", "timestamp": ..., "frame": ...}}
        
        # 애플리케이션 상태
        self.app_state = {
            "connected": False,
            "running": False,
            "mode": 0,  # 0=projection(receive), 1=injection(send)
            "input_path": "",
            "output_path": "",
            "fps": 0,
            "cpu_usage": 0,
            "memory_usage": 0,
            "npu_usage": [0, 0],
            "test_completed": False,  # 테스트 완료 상태
            "total_images": 0,        # 전체 이미지 수
            "processed_images": 0,    # 처리된 이미지 수
            "progress_percentage": 0  # 진행률 (0-100)
        }
    
    async def connect_board(self, mode: int = 0):
        """TCC7500 보드에 연결 (모드 포함)"""
        try:
            # 모드 설정
            self.app_state["mode"] = mode
            logger.info(f"보드 연결 시작... (mode: {mode})")

            # 기존 MainViewModel.__init__과 동일한 초기화
            self.vision_protocol_instance = VisionProtocol(
                inputMode=mode,
                frameWidth=settings.INJECTION['width'],
                frameHeight=settings.INJECTION['height'],
                frameChannel=settings.INJECTION['channel']
            )

            self.post_processor_instance = PostProcessor(
                frame_width=settings.INJECTION['width'],
                frame_height=settings.INJECTION['height'],
                label_path=settings.LABEL_PATH
            )

            # VisionProtocol 스레드 시작 (threading.Thread 상속)
            self.vision_protocol_instance.start()

            # 워커 인스턴스들 초기화 (기존과 동일)
            self.file_reader_instance = RtpmFileReader(
                self.vision_protocol_instance,
                (settings.INJECTION['height'], 
                 settings.INJECTION['width'],
                 settings.INJECTION['channel'])
            )

            self.data_updater_instance = RtpmDataUpdater(self.vision_protocol_instance)

            self.app_state["connected"] = True
            logger.info("보드 연결 성공")
            return {"status": "success", "message": "Board connected successfully"}

        except Exception as e:
            logger.error(f"보드 연결 실패: {str(e)}")
            return {"status": "error", "message": f"Connection failed: {str(e)}"}
    
    async def disconnect_board(self):
        """TCC7500 보드 연결 해제"""
        try:
            # VisionProtocol 스레드 종료
            if self.vision_protocol_instance:
                if hasattr(self.vision_protocol_instance, '_stop_event'):
                    self.vision_protocol_instance._stop_event.set()
                
                if self.vision_protocol_instance.is_alive():
                    self.vision_protocol_instance.join(timeout=3.0)
                    if self.vision_protocol_instance.is_alive():
                        logger.warning("VisionProtocol 스레드가 정상 종료되지 않았습니다")
                
                self.vision_protocol_instance = None

            # FileReader 스레드 정리
            if self.file_reader_instance:
                if hasattr(self.file_reader_instance, 'is_running'):
                    self.file_reader_instance.is_running = False
                if self.file_reader_instance.is_alive():
                    self.file_reader_instance.join(timeout=1.0)
                self.file_reader_instance = None

            # DataUpdater 스레드 정리
            if self.data_updater_instance:
                if hasattr(self.data_updater_instance, 'is_running'):
                    self.data_updater_instance.is_running = False
                if self.data_updater_instance.is_alive():
                    self.data_updater_instance.join(timeout=1.0)
                self.data_updater_instance = None

            # PostProcessor 인스턴스 정리 (스레드 아님)
            self.post_processor_instance = None

            self.app_state["connected"] = False
            self.app_state["running"] = False
            logger.info("보드 연결 해제 - 모든 인스턴스 정리 완료")
            return {"status": "success", "message": "Board disconnected"}

        except Exception as e:
            logger.error(f"보드 연결 해제 실패: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def start_test(self, input_path: str = None, output_path: str = None):
        """테스트 시작 (입력/출력 경로 포함)"""
        if not self.app_state["connected"]:
            raise HTTPException(status_code=400, detail="Board not connected")

        # 경로 설정
        if input_path is not None:
            self.app_state["input_path"] = input_path
            logger.info(f"입력 경로 설정: {input_path}")

        if output_path is not None:
            self.app_state["output_path"] = output_path
            logger.info(f"출력 경로 설정: {output_path}")

        try:
            if self.vision_protocol_instance:
                # VisionProtocol은 이미 실행 중이므로 running 상태만 변경
                self.app_state["running"] = True
                
                # 새로운 세션 시작 - 결과 데이터 초기화
                import uuid
                self.current_session_id = str(uuid.uuid4())[:8]
                self.session_results = []
                self.performance_data = []
                self.sent_frames_info = {}  # 시퀀스 매핑 초기화

                # 테스트 진행 상태 초기화
                self.app_state["test_completed"] = False
                self.app_state["processed_images"] = 0
                self.app_state["total_images"] = 0
                self.app_state["progress_percentage"] = 0
                
                logger.info(f"새로운 테스트 세션 시작: {self.current_session_id}")
                
                # Injection Mode용 모든 상태 변수 초기화
                injection_vars = [
                    '_injection_frame_index', '_last_frame_send_time',
                    '_injection_simple_index', '_simple_injection_logged',
                    '_debug_logged', '_injection_debug_logged',
                    '_frames_processed', '_processed_count', '_waiting_logged',
                    '_debug_count'
                ]
                for var in injection_vars:
                    if hasattr(self, var):
                        delattr(self, var)
                        logger.debug(f"상태 변수 초기화: {var}")
                
                logger.info("✅ Injection Mode 상태 변수 모두 초기화 완료")

                # Injection Mode인 경우 파일 읽기 시작
                logger.info(f"테스트 시작 조건 확인 - mode: {self.app_state['mode']}, input_path: '{self.app_state['input_path']}'")
                
                if self.app_state["mode"] == 1 and self.app_state["input_path"]:
                    logger.info(f"Injection Mode - 새로운 파일 리더 생성 및 시작: {self.app_state['input_path']}")
                    
                    # 매번 새로운 FileReader 인스턴스 생성 (Thread는 재시작할 수 없으므로)
                    if self.file_reader_instance and self.file_reader_instance.is_alive():
                        logger.info("기존 파일 리더 중지 중...")
                        self.file_reader_instance.stop_reader()
                        self.file_reader_instance.join(timeout=1.0)  # 1초 대기
                    
                    # 새로운 인스턴스 생성
                    self.file_reader_instance = RtpmFileReader(
                        self.vision_protocol_instance,
                        (settings.INJECTION['height'], 
                         settings.INJECTION['width'],
                         settings.INJECTION['channel'])
                    )
                    
                    # 파일 경로 설정
                    self.file_reader_instance.file_path = self.app_state["input_path"]
                    frame_list = []  # 프레임 리스트 (UI용)
                    frame_list_max = 100  # 최대 프레임 수
                    self.file_reader_instance.start_reader(
                        self.app_state["input_path"], 
                        frame_list, 
                        frame_list_max
                    )
                    
                    # 파일 개수를 가져오기 위해 잠시 대기 (file_reader가 파일을 스캔할 시간)
                    import time
                    time.sleep(0.1)  # 100ms 대기
                    if hasattr(self.file_reader_instance, 'total_files'):
                        self.app_state["total_images"] = self.file_reader_instance.total_files
                        logger.info(f"전체 이미지 수 설정: {self.app_state['total_images']}개")
                elif self.app_state["mode"] == 1:
                    logger.warning(f"Injection Mode이지만 입력 경로가 없습니다: '{self.app_state['input_path']}'")
                else:
                    logger.info("Projection Mode - 파일 읽기 건너뜀")

                # 기존 백그라운드 스레드가 있다면 정리
                if hasattr(self, '_background_thread') and self._background_thread and self._background_thread.is_alive():
                    logger.info("기존 백그라운드 스레드 종료 대기...")
                    # 스레드가 자연스럽게 종료될 때까지 잠시 대기
                    self._background_thread.join(timeout=1.0)
                
                # 새로운 백그라운드 스레드 시작
                self._background_thread = Thread(target=self._collect_frames_background, daemon=True)
                self._background_thread.start()
                logger.info("백그라운드 데이터 수집 스레드 시작")
                
                logger.info("테스트 시작")
                return {"status": "success", "message": "Test started"}

        except Exception as e:
            logger.error(f"테스트 시작 실패: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def stop_test(self):
        """테스트 중지"""
        try:
            # running 상태 변경 (VisionProtocol 자체는 연결 유지)
            self.app_state["running"] = False
            
            # Injection Mode에서 파일 리더 중지
            if self.app_state["mode"] == 1 and self.file_reader_instance:
                logger.info("Injection Mode - 파일 읽기 중지")
                self.file_reader_instance.stop_reader()
            
            # 백그라운드 스레드 정리 (자연 종료 대기)
            if hasattr(self, '_background_thread') and self._background_thread and self._background_thread.is_alive():
                logger.debug("백그라운드 스레드 자연 종료 대기...")
                self._background_thread.join(timeout=2.0)  # 2초 대기
                if self._background_thread.is_alive():
                    logger.warning("백그라운드 스레드가 아직 실행 중 - daemon 모드로 계속 실행")
                else:
                    logger.debug("백그라운드 스레드 정상 종료")
                
            logger.info("테스트 중지")
            return {"status": "success", "message": "Test stopped"}

        except Exception as e:
            logger.error(f"테스트 중지 실패: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _collect_frames_background(self):
        """백그라운드에서 VisionProtocol로부터 데이터 수집"""
        
        while self.app_state["running"]:
            try:
                if self.vision_protocol_instance:
                    current_mode = self.app_state["mode"]
                    
                    if current_mode == 0:  # Projection Mode (수신)
                        # 프레임 데이터 수신
                        frame_data = self.vision_protocol_instance.getFrame()
                        if frame_data is not None:
                            
                            # 프레임 데이터 검증 및 reshape
                            if hasattr(frame_data, 'shape'):
                                if len(frame_data.shape) == 1:
                                    # 1차원 Raw RGB 데이터를 이미지 형태로 reshape
                                    expected_size = settings.INJECTION['width'] * settings.INJECTION['height'] * settings.INJECTION['channel']
                                    if frame_data.shape[0] == expected_size:
                                        frame_data = frame_data.reshape(
                                            settings.INJECTION['height'], 
                                            settings.INJECTION['width'], 
                                            settings.INJECTION['channel']
                                        )
                                    else:
                                        logger.warning(f"예상과 다른 프레임 크기: {frame_data.shape[0]} != {expected_size}")
                                        continue
                                elif len(frame_data.shape) < 2:
                                    logger.warning(f"유효하지 않은 프레임 차원: {frame_data.shape}")
                                    continue
                                
                                # 큐가 가득 차면 오래된 프레임 제거
                                if self.frame_queue.full():
                                    try:
                                        self.frame_queue.get_nowait()
                                    except queue.Empty:
                                        pass
                                self.frame_queue.put(frame_data)
                            else:
                                logger.warning(f"유효하지 않은 프레임 데이터: {type(frame_data)}")

                    elif current_mode == 1:  # Injection Mode (송신) - 기존 간단한 방식 사용
                        # ✅ 수정된 로직: file_reader 완료 상태 확인
                        if (self.file_reader_instance and 
                            hasattr(self.file_reader_instance, 'frame_list') and 
                            len(self.file_reader_instance.frame_list) > 0):
                            
                            frame_list = self.file_reader_instance.frame_list
                            
                            # 첫 실행 시 로그
                            if not hasattr(self, '_simple_injection_logged'):
                                logger.info(f"✅ [수정된 로직] Injection Mode - {len(frame_list)}개 이미지 현재 로드됨, file_reader 진행 중...")
                                self._simple_injection_logged = True
                            
                            # 🔧 수정: frame_list에서 첫 번째 프레임을 꺼내서 처리 (FIFO 방식)
                            if len(frame_list) > 0:
                                # 첫 번째 프레임 꺼내기
                                frame_info = frame_list.pop(0)  # 🔥 핵심: 처리된 프레임을 리스트에서 제거!

                                if frame_info and len(frame_info) >= 2:
                                    frame_data = frame_info[0]  # [이미지, 타임스탬프, 파일명]
                                    timestamp = frame_info[1]  # 시퀀스 번호
                                    file_name = frame_info[2] if len(frame_info) > 2 else None

                                    if frame_data is not None:
                                        # 시퀀스 번호로 프레임 정보 저장 (결과 매칭용)
                                        # 프레임 데이터를 복사하여 저장 (바운딩 박스 그리기 전 원본)
                                        self.sent_frames_info[timestamp] = {
                                            "file_name": file_name,
                                            "timestamp": timestamp,
                                            "frame": frame_data.copy()  # 원본 프레임 복사
                                        }

                                        # 진행 상황 업데이트
                                        if not hasattr(self, '_processed_count'):
                                            self._processed_count = 0
                                        self._processed_count += 1

                                        self.app_state["processed_images"] = self._processed_count
                                        if self.app_state["total_images"] > 0:
                                            self.app_state["progress_percentage"] = int(
                                                (self.app_state["processed_images"] / self.app_state["total_images"]) * 100
                                            )

                                        logger.info(f"🚀 [Injection] 프레임 #{self._processed_count}/{self.app_state['total_images']} "
                                                  f"(seq:{timestamp}, file:{file_name}) 웹 표시용 큐 추가 "
                                                  f"(진행률: {self.app_state['progress_percentage']}%, 대기 중: {len(frame_list)}개)")

                                        # 🎯 참고: NPU 전송은 FileReader에서 이미 완료됨 (file_reader.py:76)
                        elif self.file_reader_instance:
                            # file_reader는 있지만 frame_list가 아직 비어있거나 완료된 경우
                            if not hasattr(self, '_waiting_logged'):
                                logger.info("⏳ file_reader 진행 중... frame_list 로딩 대기")
                                self._waiting_logged = True
                        
                        # 🔥 핵심 수정: 테스트 완료 조건 체크를 frame_list 확인 밖으로 이동!
                        if self.file_reader_instance:
                            # file_reader 완료 상태와 전체 파일 수 확인
                            file_reader_completed = not self.file_reader_instance.is_running
                            all_files_processed = (self.app_state["total_images"] > 0 and 
                                                 self.app_state["processed_images"] >= self.app_state["total_images"])
                            
                            # 디버깅 로그 (주기적으로 출력)
                            if not hasattr(self, '_debug_count'):
                                self._debug_count = 0
                            self._debug_count += 1
                            
                            if self._debug_count % 50 == 0:  # 50번마다 출력
                                frame_list_len = len(self.file_reader_instance.frame_list) if hasattr(self.file_reader_instance, 'frame_list') else 0
                                logger.info(f"📊 [디버그] file_reader 상태: running={self.file_reader_instance.is_running}, "
                                          f"frame_list_len={frame_list_len}, "
                                          f"processed={self.app_state['processed_images']}, "
                                          f"total={self.app_state['total_images']}, "
                                          f"completed={file_reader_completed}, all_processed={all_files_processed}")
                            
                            # 테스트 완료 조건: file_reader가 완료되고 모든 결과를 수신했을 때
                            frames_sent = self.app_state["processed_images"]
                            results_received = len(self.session_results)

                            if file_reader_completed and all_files_processed and not self.app_state["test_completed"]:
                                # 전송한 프레임 수와 받은 결과 수 비교
                                if results_received >= frames_sent:
                                    self.app_state["test_completed"] = True
                                    self.app_state["running"] = False
                                    self.app_state["progress_percentage"] = 100
                                    logger.info(f"✅ [완료] 모든 {frames_sent}개 파일 처리 및 결과 수신 완료 (결과: {results_received}개)")
                                else:
                                    # 아직 결과를 기다리는 중
                                    if self._debug_count % 50 == 0:
                                        logger.info(f"⏳ 결과 대기 중: {results_received}/{frames_sent} (남은 결과: {frames_sent - results_received}개)")
                            elif file_reader_completed and self.app_state["total_images"] == 0:
                                # 예외 상황: 파일이 없는 경우
                                logger.warning("⚠️ file_reader 완료되었지만 처리할 파일이 없습니다")
                                self.app_state["test_completed"] = True
                                self.app_state["running"] = False
                        
                    # 모든 모드에서 공통: 추론 결과 수집
                    result_data = self.vision_protocol_instance.getDetectionResult()
                    if result_data is not None:
                        # 큐에 추가 (WebSocket 전송용)
                        if self.result_queue.full():
                            try:
                                self.result_queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.result_queue.put(result_data)
                        
                        # 세션 결과에 저장 (파일 저장용)
                        from datetime import datetime
                        result_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "result": result_data,
                            "mode": self.app_state["mode"],
                            "image_info": {
                                "shape": [settings.INJECTION['height'], settings.INJECTION['width']],
                                "file_name": None
                            }
                        }

                        # 시퀀스 번호 기반 프레임-결과 매칭
                        if self.app_state["mode"] == 1:  # Injection Mode
                            # 결과 데이터에서 시퀀스 번호 추출
                            sequence_number = None
                            if isinstance(result_data, dict) and "info" in result_data:
                                # result_data["info"] = [시퀀스번호]
                                if isinstance(result_data["info"], list) and len(result_data["info"]) > 0:
                                    sequence_number = result_data["info"][0]

                            # 시퀀스 번호로 프레임 정보 매칭
                            if sequence_number is not None and sequence_number in self.sent_frames_info:
                                frame_info = self.sent_frames_info[sequence_number]
                                result_entry["image_info"]["file_name"] = frame_info["file_name"]
                                logger.debug(f"✅ 결과 매칭 성공: seq={sequence_number}, file={frame_info['file_name']}")

                                # 프레임에 바운딩 박스 그리기
                                frame_with_boxes = frame_info["frame"].copy()

                                if self.post_processor_instance and isinstance(result_data, dict):
                                    detection_results = []
                                    if 'cluster1' in result_data and 'od' in result_data['cluster1']:
                                        detection_results = result_data['cluster1']['od']

                                    if detection_results:
                                        # 좌표 스케일 계산
                                        current_height, current_width = frame_with_boxes.shape[:2]
                                        npu_width = settings.INJECTION['width']
                                        npu_height = settings.INJECTION['height']
                                        scale_x = current_width / npu_width
                                        scale_y = current_height / npu_height

                                        # 바운딩 박스 그리기
                                        frame_with_boxes = self.post_processor_instance.draw_object_detection_boxes(
                                            frame_with_boxes, detection_results, 0, [scale_x, scale_y]
                                        )
                                        logger.debug(f"🎨 바운딩 박스 그리기 완료: seq={sequence_number}, 검출 수={len(detection_results)}")

                                # 프레임 전처리: 리사이징 + JPEG 인코딩
                                jpeg_bytes = self._prepare_frame_for_streaming(frame_with_boxes)

                                # JPEG 바이트를 웹 표시용 큐에 추가
                                if jpeg_bytes:
                                    if self.frame_queue.full():
                                        try:
                                            self.frame_queue.get_nowait()
                                        except queue.Empty:
                                            pass
                                    self.frame_queue.put(jpeg_bytes)

                                # 메모리 절약을 위해 매칭된 프레임 정보 삭제
                                del self.sent_frames_info[sequence_number]
                            else:
                                if sequence_number is not None:
                                    logger.warning(f"⚠️ 시퀀스 번호 {sequence_number}에 해당하는 프레임 정보를 찾을 수 없습니다")
                                else:
                                    logger.warning("⚠️ 결과 데이터에서 시퀀스 번호를 추출할 수 없습니다")

                        self.session_results.append(result_entry)
                        logger.debug(f"추론 결과 추가: {type(result_data)} (세션 결과: {len(self.session_results)}개)")

            except Exception as e:
                logger.error(f"데이터 수집 오류: {str(e)}")
                
            # CPU 사용량 조절을 위한 짧은 대기
            time.sleep(0.01)
    
    async def get_status(self):
        """현재 상태 및 성능 메트릭 반환"""
        try:
            if self.vision_protocol_instance and self.app_state["connected"]:
                # 성능 데이터 가져오기
                perf_data = self.vision_protocol_instance.gerPerformanceData()  # 실제 메소드명
                if perf_data:
                    from datetime import datetime
                    
                    # 성능 데이터 파싱 (실제 구조에 따라 조정 필요)
                    data_type = perf_data[0] if len(perf_data) > 0 else None
                    
                    # 성능 데이터 저장 (파일 저장용)
                    perf_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "data_type": str(data_type) if data_type else "unknown",
                        "raw_data": perf_data
                    }
                    
                    if data_type == PerformanceDataType.FPS and len(perf_data) > 2:
                        self.app_state["fps"] = perf_data[2]
                        perf_entry["fps"] = perf_data[2]
                    elif data_type == PerformanceDataType.CPU_PERFORMANCE and len(perf_data) > 2:
                        self.app_state["cpu_usage"] = perf_data[2]
                        perf_entry["cpu_usage"] = perf_data[2]
                    elif data_type == PerformanceDataType.MEMORY and len(perf_data) > 2:
                        self.app_state["memory_usage"] = perf_data[2]
                        perf_entry["memory_usage"] = perf_data[2]
                    elif data_type == PerformanceDataType.NPU_USAGE and len(perf_data) > 3:
                        self.app_state["npu_usage"] = [perf_data[2], perf_data[3]]
                        perf_entry["npu_usage"] = [perf_data[2], perf_data[3]]
                    
                    # 세션 성능 데이터에 추가
                    if self.current_session_id:  # 테스트 실행 중일 때만 저장
                        self.performance_data.append(perf_entry)

            return self.app_state

        except Exception as e:
            logger.error(f"상태 조회 오류: {str(e)}")
            return self.app_state
    
    async def set_mode(self, mode: int):
        """동작 모드 설정 (0=projection, 1=injection)"""
        try:
            self.app_state["mode"] = mode
            logger.info(f"모드 변경: {mode}")
            return {"status": "success", "mode": mode}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def set_input_file(self, file_path: str):
        """입력 파일 경로 설정"""
        try:
            self.app_state["input_path"] = file_path
            
            # 파일 경로가 설정되면 자동으로 injection mode로 변경
            if file_path:
                self.app_state["mode"] = 1  # injection mode
                logger.info("모드를 Injection Mode(송신)로 자동 변경")
                
                # 출력 경로 자동 생성: 입력 경로 + "_results"
                auto_output_path = file_path + "_results"
                self.app_state["output_path"] = auto_output_path
                logger.info(f"출력 경로 자동 설정: {auto_output_path}")
            else:
                self.app_state["mode"] = 0  # projection mode
                logger.info("모드를 Projection Mode(수신)로 자동 변경")
                
                # 입력 경로가 비어있으면 출력 경로도 기본값으로 설정
                self.app_state["output_path"] = "./results"
            
            if self.file_reader_instance:
                self.file_reader_instance.file_path = file_path
                
            logger.info(f"입력 파일 경로 설정: {file_path}")
            return {
                "status": "success", 
                "path": file_path,
                "output_path": self.app_state["output_path"]  # 자동 생성된 출력 경로도 반환
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def set_output_path(self, output_path: str):
        """출력 경로 설정"""
        try:
            self.app_state["output_path"] = output_path
            logger.info(f"출력 파일 경로 설정: {output_path}")
            return {"status": "success", "path": output_path}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _serialize_data(self, obj):
        """JSON 직렬화를 위해 enum과 다른 특수 객체들을 변환"""
        from enum import Enum
        import numpy as np
        from datetime import datetime
        
        if isinstance(obj, Enum):
            return obj.name  # enum의 이름 반환
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._serialize_data(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_data(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self._serialize_data(item) for item in obj]
        else:
            return obj

    async def save_results(self):
        """현재 세션의 결과 데이터를 파일로 저장"""
        try:
            import os
            import json
            from datetime import datetime
            
            if not self.app_state["output_path"]:
                return {"status": "error", "message": "출력 경로가 설정되지 않았습니다"}
            
            # 출력 디렉토리 생성
            output_dir = self.app_state["output_path"]
            os.makedirs(output_dir, exist_ok=True)
            
            # 타임스탬프를 포함한 파일명 생성
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 🔧 데이터 직렬화 (enum 등 특수 객체 변환)
            serialized_session_results = self._serialize_data(self.session_results)
            serialized_performance_data = self._serialize_data(self.performance_data)
            
            # 1. 검출 결과 JSON 저장
            results_file = os.path.join(output_dir, f"detection_results_{timestamp}.json")
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "session_id": self.current_session_id,
                    "timestamp": timestamp,
                    "mode": self.app_state["mode"],
                    "input_path": self.app_state["input_path"],
                    "results": serialized_session_results
                }, f, indent=2, ensure_ascii=False)
            
            # 2. 성능 데이터 저장
            performance_file = os.path.join(output_dir, f"performance_data_{timestamp}.json")
            with open(performance_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "session_id": self.current_session_id,
                    "timestamp": timestamp,
                    "performance_data": serialized_performance_data
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"결과 데이터 저장 완료: {results_file}, {performance_file}")
            return {
                "status": "success", 
                "message": f"결과 데이터 저장 완료 ({len(self.session_results)}개 결과)",
                "files": [results_file, performance_file]
            }
            
        except Exception as e:
            logger.error(f"결과 저장 오류: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def export_coco_annotations(self):
        """COCO 형식으로 annotation 내보내기"""
        try:
            import os
            import json
            from datetime import datetime
            
            if not self.app_state["output_path"]:
                return {"status": "error", "message": "출력 경로가 설정되지 않았습니다"}
            
            if not self.session_results:
                return {"status": "error", "message": "저장할 결과 데이터가 없습니다"}
            
            # COCO 데이터 구조 생성
            coco_data = {
                "info": {
                    "description": "RTPM Detection Results",
                    "version": "1.0",
                    "year": datetime.now().year,
                    "date_created": datetime.now().isoformat()
                },
                "licenses": [],
                "images": [],
                "annotations": [],
                "categories": []
            }
            
            # PostProcessor에서 카테고리 정보 가져오기
            if self.post_processor_instance and hasattr(self.post_processor_instance, 'categories'):
                coco_data["categories"] = self.post_processor_instance.categories
            
            annotation_id = 1
            
            # 결과 데이터를 COCO 형식으로 변환
            for idx, result_entry in enumerate(self.session_results):
                if "result" in result_entry and "image_info" in result_entry:
                    result = result_entry["result"]
                    image_info = result_entry["image_info"]
                    
                    # 이미지 엔트리 생성
                    if self.post_processor_instance:
                        image_entry = self.post_processor_instance.create_image_entry(
                            image_info.get("file_name", f"image_{idx}.jpg"),
                            image_info.get("shape", [720, 1280]),
                            result
                        )
                        coco_data["images"].append(image_entry)
                        
                        # Annotation 생성
                        annotations = self.post_processor_instance.create_prediction_annotations(
                            result, image_info.get("shape", [720, 1280])
                        )
                        
                        for annotation in annotations:
                            annotation["id"] = annotation_id
                            annotation_id += 1
                            coco_data["annotations"].append(annotation)
            
            # COCO JSON 파일 저장
            output_dir = self.app_state["output_path"]
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            coco_file = os.path.join(output_dir, f"coco_annotations_{timestamp}.json")
            
            with open(coco_file, 'w', encoding='utf-8') as f:
                json.dump(coco_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"COCO annotation 저장 완료: {coco_file}")
            return {
                "status": "success",
                "message": f"COCO annotation 내보내기 완료 ({len(coco_data['annotations'])}개 annotation)",
                "file": coco_file,
                "stats": {
                    "images": len(coco_data["images"]),
                    "annotations": len(coco_data["annotations"]),
                    "categories": len(coco_data["categories"])
                }
            }
            
        except Exception as e:
            logger.error(f"COCO 내보내기 오류: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _prepare_frame_for_streaming(self, frame) -> bytes:
        """프레임을 웹 스트리밍용으로 전처리 (리사이징 + JPEG 인코딩)"""
        try:
            if frame is None or frame.size == 0 or len(frame.shape) < 2:
                return None

            # 최대 해상도 제한
            height, width = frame.shape[:2]
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
            success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

            if success:
                return buffer.tobytes()
            else:
                logger.error("JPEG 인코딩 실패")
                return None

        except Exception as e:
            logger.error(f"프레임 전처리 오류: {e}")
            return None
