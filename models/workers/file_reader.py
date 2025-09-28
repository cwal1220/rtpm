import os
import time
import threading

import cv2
from numpy import asarray, ravel
from PIL import Image

import logging
logger = logging.getLogger(__name__)


class RtpmFileReader(threading.Thread):
    def __init__(self, vision_protocol, base_size_tuple):
        super().__init__()
        self.vision_protocol = vision_protocol
        self.base_size = base_size_tuple
        self.is_running = False
        self.file_path = ''
        self.image_ext = ['.jpg', '.jpeg', '.png', '.bmp']
        self.video_ext = ['.mp4', '.avi']
        self.frame_list = None
        self.frame_list_max = 0
        self.total_files = 0  # 총 파일 수

    def run(self):
        self.is_running = True

        if os.path.isdir(self.file_path):
            self._read_folder()
        else:
            self._read_file()

        # 🔥 핵심 수정: 모든 파일 처리 완료 시 is_running을 False로 설정!
        self.is_running = False
        logger.info("파일 읽기 중지됨")

    def _read_folder(self):
        file_list = [f for f in os.listdir(self.file_path) if f.lower().endswith(tuple(self.image_ext))]
        file_num = len(file_list)
        self.total_files = file_num  # 총 파일 수 저장
        logger.info(f"폴더에서 {file_num}개 파일 발견")
        logger.info(f"[DEBUG] frame_list_max: {self.frame_list_max}, is_running: {self.is_running}")

        for idx, file_name in enumerate(file_list):
            logger.info(f"[DEBUG] 파일 {idx+1}/{file_num} 처리 중: {file_name}, is_running: {self.is_running}")
            
            if not self.is_running:
                logger.warning(f"[DEBUG] is_running=False로 인해 파일 읽기 중단됨 ({idx}/{file_num})")
                break
            
            # 큐 대기 로그 추가
            wait_count = 0
            while len(self.frame_list) >= self.frame_list_max:
                time.sleep(0.001)
                wait_count += 1
                if wait_count % 1000 == 0:  # 1초마다 로그
                    logger.warning(f"[DEBUG] frame_list 가득참 - 대기 중... ({len(self.frame_list)}/{self.frame_list_max})")

            full_path = os.path.join(self.file_path, file_name)
            logger.debug(f"[DEBUG] 이미지 로드 시도: {full_path}")
            try:
                image = cv2.imread(full_path)
                if image is None:
                    logger.warning(f"Could not read image file: {full_path}")
                    continue
                
                logger.info(f"[DEBUG] 이미지 로드 성공: {file_name}, 크기: {image.shape}")
                
                time_stamp = idx + 1
                frame_raw = self._resize_image(image)
                logger.info(f"[DEBUG] frame_raw 준비 완료: shape={frame_raw.shape}, dtype={frame_raw.dtype}")
                
                # NPU 전송 시도
                try:
                    ret = self.vision_protocol.sendFrame([frame_raw, time_stamp])
                    logger.info(f"[DEBUG] sendFrame 결과: {ret}, timestamp: {time_stamp}")
                    
                    if ret:
                        logger.info(f"✅ 파일 읽기 및 NPU 전송 성공: {file_name} ({time_stamp}/{file_num})")
                        self.frame_list.append([image, time_stamp, file_name])
                    else:
                        logger.error(f"❌ NPU 전송 실패: {full_path}")
                except Exception as e:
                    logger.error(f"❌ sendFrame 호출 오류: {full_path}, 오류: {e}")
                    ret = False
            except Exception as e:
                logger.error(f"Error reading file {full_path}: {e}", exc_info=True)

    def _read_file(self):
        file_ext = os.path.splitext(self.file_path)[1].lower()
        if file_ext in self.video_ext:
            self._read_video()
        elif file_ext in self.image_ext:
            self._read_image()
        else:
            logger.error(f"파일을 열 수 없습니다: {self.file_path}")

    def _read_image(self):
        try:
            image = cv2.imread(self.file_path)
            logger.info("이미지 파일 읽기 완료")
            frame_raw = self._resize_image(image)
            ret = self.vision_protocol.sendFrame([frame_raw, 0])
            if ret:
                self.frame_list.append([image, 0])
            else:
                logger.warning(f'Failed to send frame: {self.file_path}')
        except Exception as e:
            logger.error(f"Error reading image {self.file_path}: {e}", exc_info=True)

    def _read_video(self):
        video_obj = cv2.VideoCapture(self.file_path)
        if not video_obj.isOpened():
            logger.error(f"비디오 파일을 열 수 없습니다: {self.file_path}")
            return

        total_frame_count = int(video_obj.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = video_obj.get(cv2.CAP_PROP_FPS)
        fps_time = 1.0 / video_fps if video_fps > 0 else 0
        prev_time = 0
        current_frame_count = 0

        while self.is_running:
            if time() - prev_time < fps_time:
                time.sleep(0.001)
                continue
            
            prev_time = time()
            ret, frame = video_obj.read()
            if not ret:
                break

            current_frame_count += 1
            logger.debug(f"비디오 진행: {current_frame_count}/{total_frame_count}")

            if len(self.frame_list) < self.frame_list_max:
                frame_raw = self._resize_image(frame, use_pil=True)
                time_stamp = int((1000.0 / video_fps) * (current_frame_count - 1))
                ret = self.vision_protocol.sendFrame([frame_raw, time_stamp])
                if ret:
                    self.frame_list.append([frame, time_stamp])
                else:
                    logger.warning(f'Video Frame: {current_frame_count} / ret: {ret}')
        
        video_obj.release()

    def _resize_image(self, image, use_pil=False):
        if image.shape[:2] == (self.base_size[0], self.base_size[1]):
            return ravel(image[..., ::-1], order='C')

        if use_pil:
            img = Image.fromarray(image[..., ::-1])  # BGR -> RGB
            img_resize = img.resize((self.base_size[1], self.base_size[0]), Image.LANCZOS)
            r_image = asarray(img_resize)
            return ravel(r_image, order='C')
        else:
            r_image = cv2.resize(image, (self.base_size[1], self.base_size[0]))
            return ravel(r_image[..., ::-1], order='C')

    def start_reader(self, filePath, frameList, frameListMax):
        self.file_path = filePath
        self.is_running = True
        self.frame_list = frameList
        self.frame_list_max = frameListMax
        self.start()

    def stop_reader(self):
        self.is_running = False
